"""
Painel da Aba 2: Restauração no MySQL do iDSecure e Integração via API.
Permite selecionar a pasta de backup, testar a conexão com o MySQL (porta 3306),
injetar diretamente nas tabelas Users, Cards, Groups e Devices, ou gerar o ZIP e sincronizar fotos via API.
"""

from pathlib import Path
import threading
import flet as ft
from backend.models.backup_models import MySQLConnectionConfig, iDSecureAPIConfig
from backend.services.sqlite_storage import SQLiteStorage
from backend.services.mysql_idsecure_service import MySQLIDSecureService
from backend.services.idsecure_api_restorer import IDSecureAPIRestorer
from frontend.styles.theme import (
    create_card_container,
    COLOR_BG_TERTIARY,
    COLOR_BORDER,
    COLOR_ACCENT,
    COLOR_SUCCESS,
    COLOR_WARNING,
    COLOR_DANGER,
    COLOR_TEXT_PRIMARY,
    COLOR_TEXT_SECONDARY,
)


class RestoreMySQLPanel(ft.Column):
    """Componente visual para restauração no MySQL e API do iDSecure."""

    def __init__(self, page: ft.Page):
        super().__init__(spacing=16)
        self.app_page = page

        # Seletor de pasta de backup
        self.folder_input = ft.TextField(
            label="Caminho da Pasta do Backup",
            hint_text="Ex: G:\\Meu Drive\\Projetos\\Bot Backup Catraca\\backups\\backup_20261016_150000",
            bgcolor=COLOR_BG_TERTIARY,
            border_color=COLOR_BORDER,
            focused_border_color=COLOR_ACCENT,
            color=COLOR_TEXT_PRIMARY,
            text_size=13,
            expand=True,
        )

        self.browse_folder_btn = ft.OutlinedButton(
            content="Escolher Pasta...",
            icon=ft.Icons.FOLDER_OPEN_ROUNDED,
            style=ft.ButtonStyle(
                side=ft.BorderSide(1, COLOR_BORDER),
                padding=ft.Padding.symmetric(horizontal=12, vertical=14),
            ),
            on_click=self._browse_folder_dialog,
        )

        # Campos de Configuração do MySQL
        self.host_input = ft.TextField(label="Host MySQL", value="localhost", width=140, bgcolor=COLOR_BG_TERTIARY, text_size=13)
        self.port_input = ft.TextField(label="Porta", value="3306", width=80, bgcolor=COLOR_BG_TERTIARY, text_size=13)
        self.user_input = ft.TextField(label="Usuário MySQL", value="root", width=120, bgcolor=COLOR_BG_TERTIARY, text_size=13)
        self.pass_input = ft.TextField(label="Senha MySQL", value="", password=True, can_reveal_password=True, width=140, bgcolor=COLOR_BG_TERTIARY, text_size=13)
        self.db_input = ft.TextField(label="Banco de Dados", value="idsecure", width=130, bgcolor=COLOR_BG_TERTIARY, text_size=13)

        # Campos de Configuração da API do iDSecure
        self.api_url_input = ft.TextField(label="URL API iDSecure", value="https://localhost:30443", width=220, bgcolor=COLOR_BG_TERTIARY, text_size=13)
        self.api_user_input = ft.TextField(label="Usuário API", value="admin", width=120, bgcolor=COLOR_BG_TERTIARY, text_size=13)
        self.api_pass_input = ft.TextField(label="Senha API", value="admin", password=True, can_reveal_password=True, width=120, bgcolor=COLOR_BG_TERTIARY, text_size=13)

        # Barra de Progresso e Indicador de Operação
        self.restore_progress_bar = ft.ProgressBar(value=0.0, height=8, bgcolor=COLOR_BG_TERTIARY, color=COLOR_ACCENT)
        self.restore_progress_text = ft.Text("0%", size=11, weight=ft.FontWeight.W_600, color=COLOR_ACCENT)
        self.restore_detail_text = ft.Text("Pronto", size=11, color=COLOR_TEXT_SECONDARY)

        # Console de Logs da Restauração
        self.log_view = ft.ListView(expand=True, spacing=4, auto_scroll=True)
        self.log_container = ft.Container(
            content=self.log_view,
            bgcolor="#070A0F",
            border_radius=6,
            border=ft.Border.all(1, COLOR_BORDER),
            padding=10,
            height=140,
        )

        self.status_label = ft.Text("Aguardando ação do técnico...", size=12, color=COLOR_TEXT_SECONDARY)

        self.controls = [
            # 1. Seletor de Pasta de Backup
            create_card_container(
                ft.Column(
                    spacing=10,
                    controls=[
                        ft.Row(
                            spacing=8,
                            controls=[
                                ft.Icon(ft.Icons.FOLDER_SPECIAL_ROUNDED, color=COLOR_ACCENT, size=20),
                                ft.Text(
                                    "1. Selecione a Pasta do Backup para Restauração",
                                    size=13,
                                    weight=ft.FontWeight.W_600,
                                    color=COLOR_TEXT_PRIMARY,
                                ),
                            ],
                        ),
                        ft.Row(
                            spacing=10,
                            vertical_alignment=ft.CrossAxisAlignment.CENTER,
                            controls=[
                                self.folder_input,
                                self.browse_folder_btn,
                                ft.Button(
                                    content="Gerar dump_idsecure_mysql.sql",
                                    icon=ft.Icons.CODE_ROUNDED,
                                    style=ft.ButtonStyle(bgcolor=COLOR_BG_TERTIARY, color=COLOR_TEXT_PRIMARY),
                                    on_click=self._generate_dump_clicked,
                                ),
                                ft.Button(
                                    content="Gerar ZIP de Importação",
                                    icon=ft.Icons.FOLDER_ZIP_ROUNDED,
                                    style=ft.ButtonStyle(bgcolor=COLOR_BG_TERTIARY, color=COLOR_TEXT_PRIMARY),
                                    on_click=self._generate_zip_clicked,
                                ),
                            ],
                        ),
                    ],
                ),
                padding=16,
            ),

            # 2. Configurações e Ações MySQL Direto
            create_card_container(
                ft.Column(
                    spacing=12,
                    controls=[
                        ft.Row(
                            spacing=8,
                            controls=[
                                ft.Icon(ft.Icons.DNS_ROUNDED, color=COLOR_ACCENT, size=20),
                                ft.Text(
                                    "2. Conexão Direta ao MySQL do iDSecure (Porta 3306)",
                                    size=13,
                                    weight=ft.FontWeight.W_600,
                                    color=COLOR_TEXT_PRIMARY,
                                ),
                            ],
                        ),
                        ft.Row(
                            spacing=10,
                            controls=[
                                self.host_input,
                                self.port_input,
                                self.user_input,
                                self.pass_input,
                                self.db_input,
                                ft.OutlinedButton(
                                    content="Testar Conexão",
                                    icon=ft.Icons.LAN_ROUNDED,
                                    on_click=self._test_mysql_clicked,
                                ),
                                ft.Button(
                                    content="Injetar no Banco MySQL",
                                    icon=ft.Icons.UPLOAD_ROUNDED,
                                    style=ft.ButtonStyle(bgcolor=COLOR_SUCCESS, color="#FFFFFF"),
                                    on_click=self._inject_mysql_clicked,
                                ),
                            ],
                        ),
                    ],
                ),
                padding=16,
            ),

            # 3. Sincronização via API Local do iDSecure (Fotos Faciais)
            create_card_container(
                ft.Column(
                    spacing=12,
                    controls=[
                        ft.Row(
                            spacing=8,
                            controls=[
                                ft.Icon(ft.Icons.FACE_ROUNDED, color=COLOR_ACCENT, size=20),
                                ft.Text(
                                    "3. Envio de Fotos via API Local do iDSecure (Porta 30443)",
                                    size=13,
                                    weight=ft.FontWeight.W_600,
                                    color=COLOR_TEXT_PRIMARY,
                                ),
                            ],
                        ),
                        ft.Row(
                            spacing=10,
                            controls=[
                                self.api_url_input,
                                self.api_user_input,
                                self.api_pass_input,
                                ft.OutlinedButton(
                                    content="Testar API",
                                    icon=ft.Icons.LINK_ROUNDED,
                                    on_click=self._test_api_clicked,
                                ),
                                ft.Button(
                                    content="Sincronizar Fotos na API",
                                    icon=ft.Icons.CLOUD_UPLOAD_ROUNDED,
                                    style=ft.ButtonStyle(bgcolor=COLOR_ACCENT, color="#FFFFFF"),
                                    on_click=self._sync_api_clicked,
                                ),
                            ],
                        ),
                    ],
                ),
                padding=16,
            ),

            # 4. Status, Progresso e Console de Logs
            create_card_container(
                ft.Column(
                    spacing=8,
                    controls=[
                        ft.Row(
                            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                            controls=[
                                ft.Text("Logs da Operação de Restauração:", size=12, weight=ft.FontWeight.W_500, color=COLOR_TEXT_SECONDARY),
                                self.status_label,
                            ],
                        ),
                        # Barra de progresso com porcentagem e detalhes da tabela
                        ft.Row(
                            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                            controls=[
                                self.restore_detail_text,
                                self.restore_progress_text,
                            ],
                        ),
                        self.restore_progress_bar,
                        self.log_container,
                    ],
                ),
                padding=16,
            ),
        ]

    def log(self, message: str):
        from backend.core.logger import logger
        logger.info(message)
        self.log_view.controls.append(
            ft.Text(f"• {message}", size=11, font_family="Consolas, monospace", color="#CBD5E1")
        )
        try:
            self.update()
        except Exception:
            pass

    def on_restore_progress(self, current: int, total: int, step_desc: str = ""):
        """Atualiza a barra de progresso visualmente."""
        if total > 0:
            frac = min(1.0, max(0.0, current / total))
            self.restore_progress_bar.value = frac
            self.restore_progress_text.value = f"{int(frac * 100)}% ({current}/{total})"
        if step_desc:
            self.restore_detail_text.value = step_desc
        try:
            self.update()
        except Exception:
            pass

    def _browse_folder_dialog(self, e):
        """Abre janela nativa do Windows para o técnico escolher a pasta de backup."""
        import threading
        def open_dialog():
            try:
                import tkinter as tk
                from tkinter import filedialog
                root = tk.Tk()
                root.withdraw()
                root.attributes("-topmost", True)
                initial_dir = self.folder_input.value.strip() or str(Path("backups").resolve())
                selected_dir = filedialog.askdirectory(
                    title="Selecione a Pasta do Backup para Restauração",
                    initialdir=initial_dir,
                )
                root.destroy()
                if selected_dir:
                    self.folder_input.value = str(Path(selected_dir).resolve())
                    self.update()
            except Exception:
                pass

        threading.Thread(target=open_dialog, daemon=True).start()

    def _get_services(self):
        folder = self.folder_input.value.strip()
        if not folder or not Path(folder).exists():
            self.log("ERRO: Selecione uma pasta de backup válida contendo 'backup_controlid.sqlite'.")
            return None, None, None

        sqlite_file = Path(folder) / "backup_controlid.sqlite"
        if not sqlite_file.exists():
            self.log(f"ERRO: Não foi encontrado o arquivo '{sqlite_file.name}' na pasta indicada.")
            return None, None, None

        storage = SQLiteStorage(str(sqlite_file))
        mysql_svc = MySQLIDSecureService(storage, folder)
        api_restorer = IDSecureAPIRestorer(storage, folder)
        return storage, mysql_svc, api_restorer

    def _test_mysql_clicked(self, e):
        _, mysql_svc, _ = self._get_services()
        if not mysql_svc:
            return

        cfg = MySQLConnectionConfig(
            host=self.host_input.value.strip(),
            port=int(self.port_input.value.strip() or 3306),
            user=self.user_input.value.strip(),
            password=self.pass_input.value.strip(),
            database=self.db_input.value.strip(),
        )

        self.log("Testando conexão com o servidor MySQL do iDSecure...")
        ok, msg = mysql_svc.test_connection(cfg)
        self.log(msg)
        if ok:
            self.status_label.value = "Conexão com o MySQL OK!"
            self.status_label.color = COLOR_SUCCESS
        else:
            self.status_label.value = "Falha ao conectar no MySQL."
            self.status_label.color = COLOR_DANGER
        self.update()

    def _generate_dump_clicked(self, e):
        _, mysql_svc, _ = self._get_services()
        if not mysql_svc:
            return

        self.log("Gerando arquivo dump_idsecure_mysql.sql...")
        dump_file = mysql_svc.generate_sql_dump()
        self.log(f"Script SQL gerado com sucesso em: {dump_file}")

    def _inject_mysql_clicked(self, e):
        _, mysql_svc, _ = self._get_services()
        if not mysql_svc:
            return

        cfg = MySQLConnectionConfig(
            host=self.host_input.value.strip(),
            port=int(self.port_input.value.strip() or 3306),
            user=self.user_input.value.strip(),
            password=self.pass_input.value.strip(),
            database=self.db_input.value.strip(),
        )

        self.log("Iniciando injeção direta de dados no banco MySQL...")
        self.on_restore_progress(0, 100, "Iniciando restauração no MySQL...")

        def run_restore():
            ok, msg = mysql_svc.restore_direct_mysql(
                cfg,
                on_log=self.log,
                on_progress=self.on_restore_progress,
            )
            if ok:
                self.status_label.value = "Restauração MySQL concluída com sucesso!"
                self.status_label.color = COLOR_SUCCESS
            else:
                self.status_label.value = "Falha na restauração MySQL."
                self.status_label.color = COLOR_DANGER
            try:
                self.update()
            except Exception:
                pass

        threading.Thread(target=run_restore, daemon=True).start()

    def _generate_zip_clicked(self, e):
        _, _, api_restorer = self._get_services()
        if not api_restorer:
            return

        self.log("Gerando pacote importacao_idsecure.zip (Planilha CSV + Fotos)...")
        zip_path = api_restorer.generate_import_zip()
        self.log(f"Pacote ZIP gerado com sucesso em: {zip_path}")

    def _test_api_clicked(self, e):
        _, _, api_restorer = self._get_services()
        if not api_restorer:
            return

        cfg = iDSecureAPIConfig(
            base_url=self.api_url_input.value.strip(),
            api_user=self.api_user_input.value.strip(),
            api_password=self.api_pass_input.value.strip(),
        )

        def run_test():
            import asyncio
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            self.log(f"Testando conexão com a API do iDSecure em {cfg.base_url}...")
            ok, msg = loop.run_until_complete(api_restorer.test_api_connection(cfg))
            loop.close()
            self.log(msg)
            if ok:
                self.status_label.value = "Conexão com a API do iDSecure OK!"
                self.status_label.color = COLOR_SUCCESS
            else:
                self.status_label.value = "Falha ao conectar na API."
                self.status_label.color = COLOR_DANGER
            self.update()

        threading.Thread(target=run_test, daemon=True).start()

    def _sync_api_clicked(self, e):
        _, _, api_restorer = self._get_services()
        if not api_restorer:
            return

        cfg = iDSecureAPIConfig(
            base_url=self.api_url_input.value.strip(),
            api_user=self.api_user_input.value.strip(),
            api_password=self.api_pass_input.value.strip(),
        )

        def run_sync():
            import asyncio
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            self.log("Iniciando envio de fotos faciais para o iDSecure via API...")
            self.on_restore_progress(0, 100, "Sincronizando fotos...")
            
            def progress_bridge(current, total):
                self.on_restore_progress(current, total, f"Fotos: {current}/{total}")

            success, fail = loop.run_until_complete(
                api_restorer.sync_faces_to_idsecure_api(
                    cfg,
                    on_progress=progress_bridge,
                    on_log=self.log,
                )
            )
            loop.close()
            self.log(f"Finalizado: {success} foto(s) enviada(s), {fail} falha(s).")
            if fail == 0:
                self.status_label.value = f"Fotos sincronizadas com sucesso ({success})!"
                self.status_label.color = COLOR_SUCCESS
            else:
                self.status_label.value = f"Fotos enviadas: {success} OK, {fail} falha(s)"
                self.status_label.color = COLOR_WARNING
            self.update()

        threading.Thread(target=run_sync, daemon=True).start()
