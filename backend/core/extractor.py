"""
Orquestrador central de extração de dados e fotos faciais dos terminais Control iD.
Coordena a extração sequencial e paralela por equipamento, aplicando deduplicação pré-download,
checkpoints no SQLite e semáforos para não sobrecarregar as catracas.
"""

import asyncio
from datetime import datetime
from pathlib import Path
import re
from typing import List, Callable, Optional, Dict, Any

from backend.models.device import ControlIdDevice
from backend.models.backup_models import BackupProgress, BackupAuditReport
from backend.core.idface_client import IDFaceClient
from backend.services.sqlite_storage import SQLiteStorage
from backend.core.merger import DataMerger


def sanitize_filename(name: str) -> str:
    """Remove caracteres inválidos para nomes de arquivos no Windows/Linux."""
    return re.sub(r'[\\/*?:"<>|]', "", name).strip().replace(" ", "_")


class BackupExtractor:
    """Orquestrador de extração completa de dados e biometrias faciais."""

    MAX_CONCURRENT_IMAGES_PER_DEVICE = 3

    def __init__(
        self,
        devices: List[ControlIdDevice],
        output_dir: str,
        login_user: str = "admin",
        login_password: str = "admin",
    ):
        self.devices = devices
        self.output_dir = Path(output_dir)
        self.login_user = login_user
        self.login_password = login_password
        
        # Garante diretórios
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.faces_dir = self.output_dir / "faces"
        self.faces_dir.mkdir(parents=True, exist_ok=True)

        self.db_path = self.output_dir / "backup_controlid.sqlite"
        self.storage = SQLiteStorage(str(self.db_path))
        self.merger = DataMerger(self.storage)

        self.progress = BackupProgress()
        self._is_paused = False
        self._is_cancelled = False

    def pause(self):
        self._is_paused = True
        self.progress.is_paused = True

    def resume(self):
        self._is_paused = False
        self.progress.is_paused = False

    def cancel(self):
        self._is_cancelled = True
        self.progress.is_cancelled = True

    async def _wait_if_paused(self):
        while self._is_paused and not self._is_cancelled:
            await asyncio.sleep(0.5)

    async def run(
        self,
        on_progress: Optional[Callable[[BackupProgress], None]] = None,
        on_log: Optional[Callable[[str], None]] = None,
    ) -> BackupAuditReport:
        """Executa o ciclo completo de extração dos equipamentos selecionados."""
        self.progress.start_time = datetime.now()
        report = BackupAuditReport(
            backup_id=self.output_dir.name,
            created_at=datetime.now().isoformat(),
            target_folder=str(self.output_dir),
            devices_scanned=len(self.devices),
        )

        selected_devices = [d for d in self.devices if d.selected_for_backup]
        if not selected_devices:
            if on_log:
                on_log("Nenhum equipamento selecionado para backup.")
            return report

        def log(msg: str):
            if on_log:
                on_log(msg)

        log(f"Iniciando backup de {len(selected_devices)} equipamento(s)...")

        # 1. ETAPA DE EXTRAÇÃO DE OBJETOS ESTRUTURADOS
        self.progress.current_phase = "Extraindo Objetos Estruturados"
        for dev in selected_devices:
            if self._is_cancelled:
                log("Operação cancelada pelo usuário.")
                break
            await self._wait_if_paused()

            self.progress.device_ip = dev.ip
            self.progress.device_serial = dev.serial
            if on_progress:
                on_progress(self.progress)

            log(f"Conectando a {dev.ip} ({dev.model})...")
            client = IDFaceClient(
                dev,
                login_user=self.login_user,
                login_password=self.login_password,
            )

            try:
                await client.login()
                await client.get_system_information()
                log(f"Equipamento {dev.ip} autenticado com sucesso! S/N: {dev.serial}")

                # Registra equipamento no banco SQLite
                self.storage.register_device(
                    serial=dev.serial,
                    ip=dev.ip,
                    port=dev.port,
                    model=dev.model,
                    version=dev.version,
                    raw_info=dev.raw_info,
                )

                # Extrai tabelas essenciais
                log(f"[{dev.ip}] Extraindo usuários...")
                users = await client.load_all_objects("users")
                self.storage.save_raw_objects(dev.serial, "users", users)
                self.merger.merge_users(dev.serial, users)

                log(f"[{dev.ip}] Extraindo cartões...")
                cards = await client.load_all_objects("cards")
                self.storage.save_raw_objects(dev.serial, "cards", cards)
                self.merger.merge_cards(dev.serial, cards)

                log(f"[{dev.ip}] Extraindo grupos e permissões...")
                groups = await client.load_all_objects("groups")
                user_groups = await client.load_all_objects("user_groups")
                self.storage.save_raw_objects(dev.serial, "groups", groups)
                self.storage.save_raw_objects(dev.serial, "user_groups", user_groups)
                self.merger.merge_groups(dev.serial, groups)
                self.merger.merge_user_groups(dev.serial, user_groups)

                # Regras e horários
                rules = await client.load_all_objects("access_rules")
                time_zones = await client.load_all_objects("time_zones")
                time_spans = await client.load_all_objects("time_spans")
                self.merger.merge_access_rules(dev.serial, rules, time_zones, time_spans)

                report.devices_backed_up += 1
                dev.stats.status = "Objetos OK"

            except Exception as e:
                err_msg = f"Erro ao extrair objetos de {dev.ip}: {str(e)}"
                log(err_msg)
                report.errors.append(err_msg)
                dev.stats.status = "Erro"
            finally:
                await client.close()

        # 2. ETAPA DE DOWNLOAD E DEDUPLICAÇÃO DE FOTOS FACIAIS
        self.progress.current_phase = "Baixando Fotos Faciais"
        log("Iniciando extração e deduplicação de fotos faciais...")

        # Carrega checkpoints prévios do SQLite
        already_downloaded_ids = self.storage.get_downloaded_face_ids()

        # Obtém lista de usuários consolidados
        with self.storage._get_connection() as conn:
            user_rows = conn.execute("SELECT id, registration, name, image_timestamp FROM users").fetchall()
            users_map = {row["id"]: row for row in user_rows}

        for dev in selected_devices:
            if self._is_cancelled:
                break
            await self._wait_if_paused()

            client = IDFaceClient(
                dev,
                login_user=self.login_user,
                login_password=self.login_password,
            )
            try:
                await client.login()
                face_list = await client.list_user_images()
                log(f"[{dev.ip}] Catraca possui {len(face_list)} fotos cadastradas.")
                self.progress.total_faces += len(face_list)

                semaphore = asyncio.Semaphore(self.MAX_CONCURRENT_IMAGES_PER_DEVICE)

                async def download_face_task(f_item: Dict[str, Any]):
                    if self._is_cancelled:
                        return
                    await self._wait_if_paused()

                    u_id = f_item["user_id"]
                    ts = f_item.get("timestamp", 0)

                    # Deduplicação Pré-Download: Verifica se já temos essa foto
                    if u_id in already_downloaded_ids:
                        existing_ts = self.storage.get_face_timestamp(u_id)
                        if ts <= existing_ts:
                            self.progress.skipped_faces += 1
                            report.total_faces_deduplicated += 1
                            if on_progress:
                                on_progress(self.progress)
                            return

                    async with semaphore:
                        if self._is_cancelled:
                            return
                        await self._wait_if_paused()

                        u_data = users_map.get(u_id)
                        name_str = sanitize_filename(u_data["name"]) if u_data else f"user_{u_id}"
                        reg_str = sanitize_filename(u_data["registration"]) if u_data and u_data["registration"] else "sem_matricula"
                        filename = f"{u_id}_{reg_str}_{name_str}.jpg"
                        file_path = self.faces_dir / filename

                        img_bytes = await client.download_user_image(u_id)
                        if img_bytes:
                            with open(file_path, "wb") as f_out:
                                f_out.write(img_bytes)

                            self.storage.register_user_image(
                                user_id=u_id,
                                timestamp=ts,
                                file_path=str(file_path),
                                file_size=len(img_bytes),
                                status="DOWNLOADED",
                                source_device_serial=dev.serial,
                            )
                            already_downloaded_ids.add(u_id)
                            self.progress.downloaded_faces += 1
                            report.total_faces_downloaded += 1
                        else:
                            self.storage.register_user_image(
                                user_id=u_id,
                                timestamp=ts,
                                status="FAILED",
                                source_device_serial=dev.serial,
                                error_message="Falha no download após retries",
                            )
                            self.progress.failed_faces += 1
                            report.total_faces_failed += 1

                        if on_progress:
                            on_progress(self.progress)

                tasks = [download_face_task(item) for item in face_list]
                await asyncio.gather(*tasks, return_exceptions=True)

            except Exception as e:
                err_msg = f"Erro ao baixar fotos de {dev.ip}: {str(e)}"
                log(err_msg)
                report.errors.append(err_msg)
            finally:
                await client.close()

        # 3. CONSOLIDAÇÃO FINAL E RELATÓRIO
        self.progress.current_phase = "Finalizado"
        stats = self.storage.get_stats_summary()
        report.total_users_consolidated = stats["users"]
        report.total_cards_consolidated = stats["cards"]
        report.total_groups_consolidated = stats["groups"]
        report.total_access_rules_consolidated = stats["access_rules"]
        report.conflicts_detected = self.merger.conflicts

        log("Extração concluída com sucesso!")
        if on_progress:
            on_progress(self.progress)

        return report
