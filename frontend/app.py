"""
Controlador principal da interface gráfica Flet (Desktop).
Gerencia a navegação entre as abas '1. Extração iDFace' e '2. Restauração MySQL / iDSecure',
comunicação assíncrona com os serviços do backend e orquestração dos componentes visuais.
"""

import asyncio
from datetime import datetime
from pathlib import Path
import threading
import flet as ft

from backend.models.device import ControlIdDevice
from backend.models.backup_models import BackupProgress, BackupAuditReport
from backend.core.scanner import NetworkScanner
from backend.core.idface_client import IDFaceClient
from backend.core.extractor import BackupExtractor
from backend.services.exporter_service import ExporterService

from frontend.styles.theme import (
    COLOR_BG_PRIMARY,
    COLOR_BG_SECONDARY,
    COLOR_ACCENT,
    COLOR_BORDER,
    COLOR_TEXT_PRIMARY,
    COLOR_TEXT_SECONDARY,
    create_card_container,
)
from frontend.components.header import create_header
from frontend.components.connection_panel import ConnectionPanel
from frontend.components.device_selector import DeviceSelector
from frontend.components.progress_panel import ProgressPanel
from frontend.components.audit_summary import AuditSummary
from frontend.components.restore_mysql_panel import RestoreMySQLPanel


class AppController:
    """Gerenciador de estado e eventos da aplicação Flet."""

    def __init__(self, page: ft.Page):
        self.page = page
        self.devices = []
        self.extractor = None
        self.scanner = None

        # Componentes Aba 1
        self.conn_panel = ConnectionPanel(
            on_scan_clicked=self.start_scan,
            on_cancel_clicked=self.cancel_scan,
        )
        self.device_selector = DeviceSelector(
            on_selection_changed=self.on_selection_changed,
        )
        self.progress_panel = ProgressPanel(
            on_start_backup=self.start_backup,
            on_pause_resume=self.pause_resume_backup,
            on_cancel=self.cancel_backup,
        )
        self.audit_summary = AuditSummary()

        # Componente Aba 2
        self.restore_panel = RestoreMySQLPanel(self.page)

    def on_selection_changed(self):
        self.page.update()

    def start_scan(self, targets: str, user: str, pwd: str):
        """Dispara varredura assíncrona em background thread."""
        self.progress_panel.add_log(f"Iniciando varredura nos alvos: {targets}")
        self.scanner = NetworkScanner(max_concurrency=40, timeout=1.5)

        def run_async_scan():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

            async def scan_coro():
                def on_dev_found(dev: ControlIdDevice):
                    self.devices.append(dev)
                    self.device_selector.set_devices(list(self.devices))
                    self.progress_panel.add_log(f"Terminal Control iD detectado em {dev.ip}!")

                await self.scanner.scan(
                    targets_input=targets,
                    ports=[80, 443],
                    on_device_found=on_dev_found,
                )

                # Pré-diagnóstico: consulta contagens de usuários e fotos em cada catraca encontrada
                for d in self.devices:
                    try:
                        client = IDFaceClient(d, login_user=user, login_password=pwd)
                        await client.login()
                        await client.get_system_information()
                        await client.count_users_and_faces()
                        await client.close()
                    except Exception as e:
                        d.stats.status = "Falha Auth"
                    self.device_selector.render_rows()
                    self.page.update()

                self.conn_panel.set_idle_state()
                self.progress_panel.add_log(f"Varredura concluída! {len(self.devices)} terminal(is) localizados.")
                self.page.update()

            loop.run_until_complete(scan_coro())
            loop.close()

        threading.Thread(target=run_async_scan, daemon=True).start()

    def cancel_scan(self):
        if self.scanner:
            self.scanner.cancel()
            self.progress_panel.add_log("Varredura de rede cancelada.")

    def start_backup(self):
        """Inicia o processo de extração e salvamento das catracas selecionadas."""
        selected = self.device_selector.get_selected_devices()
        if not selected:
            self.progress_panel.add_log("ERRO: Nenhum terminal selecionado com checkbox.")
            return

        # Obtém a pasta escolhida pelo usuário
        chosen_folder = self.progress_panel.folder_input.value.strip()
        timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")

        if chosen_folder:
            base_path = Path(chosen_folder)
            # Se a pasta já terminar com um nome de backup ou tiver subpasta
            backup_folder = base_path / f"backup_{timestamp_str}"
        else:
            backup_folder = Path("backups") / f"backup_{timestamp_str}"

        backup_folder.mkdir(parents=True, exist_ok=True)

        user = self.conn_panel.user_input.value.strip()
        pwd = self.conn_panel.password_input.value.strip()

        self.extractor = BackupExtractor(
            devices=selected,
            output_dir=str(backup_folder.resolve()),
            login_user=user,
            login_password=pwd,
        )

        self.progress_panel.set_running_state()

        def run_async_backup():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

            async def backup_coro():
                def on_prog(p: BackupProgress):
                    self.progress_panel.update_progress(p)

                def on_lg(msg: str):
                    self.progress_panel.add_log(msg)

                report = await self.extractor.run(on_progress=on_prog, on_log=on_lg)

                # Exporta backup_full.json e audit_report.json
                exporter = ExporterService(self.extractor.storage, str(backup_folder.resolve()))
                exporter.export_full_json()
                exporter.export_audit_report(report)

                # Atualiza painel de restauração com o caminho sugerido
                self.restore_panel.folder_input.value = str(backup_folder.resolve())

                self.progress_panel.set_finished_state()
                self.audit_summary.set_report(report)
                self.page.update()

            loop.run_until_complete(backup_coro())
            loop.close()

        threading.Thread(target=run_async_backup, daemon=True).start()

    def pause_resume_backup(self):
        if not self.extractor:
            return
        if self.extractor._is_paused:
            self.extractor.resume()
            self.progress_panel.set_paused_state(False)
            self.progress_panel.add_log("Backup retomado.")
        else:
            self.extractor.pause()
            self.progress_panel.set_paused_state(True)
            self.progress_panel.add_log("Backup pausado temporariamente.")

    def cancel_backup(self):
        if self.extractor:
            self.extractor.cancel()
            self.progress_panel.set_finished_state()
            self.progress_panel.add_log("Backup interrompido pelo usuário.")


def build_app(page: ft.Page):
    """Monta a hierarquia de widgets da tela principal."""
    controller = AppController(page)

    header = create_header()

    # Aba 1: Extração iDFace
    extraction_tab_content = ft.Column(
        spacing=16,
        controls=[
            controller.conn_panel,
            controller.device_selector,
            controller.progress_panel,
            controller.audit_summary,
        ],
        scroll=ft.ScrollMode.ADAPTIVE,
    )

    # Aba 2: Restauração MySQL / iDSecure
    restore_tab_content = ft.Column(
        spacing=16,
        controls=[
            controller.restore_panel,
        ],
        scroll=ft.ScrollMode.ADAPTIVE,
    )

    tab_bar = ft.TabBar(
        tabs=[
            ft.Tab(
                label="1. Extrair das Catracas (iDFace)",
                icon=ft.Icons.DOWNLOAD_ROUNDED,
            ),
            ft.Tab(
                label="2. Restaurar no iDSecure (MySQL / API)",
                icon=ft.Icons.RESTORE_PAGE_ROUNDED,
            ),
        ],
    )

    tab_view = ft.TabBarView(
        controls=[
            ft.Container(content=extraction_tab_content, padding=16),
            ft.Container(content=restore_tab_content, padding=16),
        ],
        expand=True,
    )

    tabs = ft.Tabs(
        length=2,
        selected_index=0,
        content=ft.Column(
            spacing=0,
            controls=[
                tab_bar,
                ft.Container(content=tab_view, expand=True),
            ],
            expand=True,
        ),
        expand=True,
    )

    page.add(
        ft.Column(
            spacing=0,
            expand=True,
            controls=[
                header,
                ft.Container(content=tabs, expand=True),
            ],
        )
    )
