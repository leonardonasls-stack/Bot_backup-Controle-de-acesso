"""
Painel de Progresso, Métricas e Console de Logs em tempo real durante a extração.
"""

from pathlib import Path
from typing import Callable, Optional
import flet as ft
from backend.models.backup_models import BackupProgress
from frontend.styles.theme import (
    COLOR_BG_SECONDARY,
    COLOR_BG_TERTIARY,
    COLOR_BORDER,
    COLOR_ACCENT,
    COLOR_SUCCESS,
    COLOR_WARNING,
    COLOR_TEXT_PRIMARY,
    COLOR_TEXT_SECONDARY,
)


class ProgressPanel(ft.Container):
    """Componente visual com barras de progresso e console de log."""

    def __init__(
        self,
        on_start_backup: Callable[[], None],
        on_pause_resume: Callable[[], None],
        on_cancel: Callable[[], None],
    ):
        super().__init__(
            bgcolor=COLOR_BG_SECONDARY,
            border_radius=10,
            border=ft.Border.all(1, COLOR_BORDER),
            padding=16,
        )
        self.on_start_backup = on_start_backup
        self.on_pause_resume = on_pause_resume
        self.on_cancel = on_cancel

        self.phase_label = ft.Text("Aguardando início...", size=13, weight=ft.FontWeight.BOLD, color=COLOR_ACCENT)
        self.details_label = ft.Text("Selecione os equipamentos acima e clique em 'Iniciar Backup Completo'.", size=12, color=COLOR_TEXT_SECONDARY)

        self.faces_progress_bar = ft.ProgressBar(
            value=0.0,
            bgcolor=COLOR_BG_TERTIARY,
            color=COLOR_ACCENT,
            height=10,
            border_radius=5,
        )

        self.faces_count_label = ft.Text("Fotos: 0 / 0", size=12, weight=ft.FontWeight.W_500, color=COLOR_TEXT_PRIMARY)

        default_backup_dir = str(Path("backups").resolve())
        self.folder_input = ft.TextField(
            label="Pasta de Destino do Backup",
            value=default_backup_dir,
            bgcolor=COLOR_BG_TERTIARY,
            border_color=COLOR_BORDER,
            focused_border_color=COLOR_ACCENT,
            color=COLOR_TEXT_PRIMARY,
            text_size=12,
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

        self.start_button = ft.Button(
            content="Iniciar Backup Completo",
            icon=ft.Icons.PLAY_ARROW_ROUNDED,
            style=ft.ButtonStyle(
                bgcolor=COLOR_SUCCESS,
                color="#FFFFFF",
                padding=ft.Padding.symmetric(horizontal=20, vertical=16),
            ),
            on_click=lambda e: self.on_start_backup(),
        )

        self.pause_resume_button = ft.OutlinedButton(
            content="Pausar",
            icon=ft.Icons.PAUSE_ROUNDED,
            visible=False,
            style=ft.ButtonStyle(
                side=ft.BorderSide(1, COLOR_WARNING),
                color=COLOR_WARNING,
                padding=ft.Padding.symmetric(horizontal=16, vertical=16),
            ),
            on_click=lambda e: self.on_pause_resume(),
        )

        self.cancel_button = ft.OutlinedButton(
            content="Cancelar",
            icon=ft.Icons.CANCEL_ROUNDED,
            visible=False,
            style=ft.ButtonStyle(
                side=ft.BorderSide(1, "#EF4444"),
                color="#EF4444",
                padding=ft.Padding.symmetric(horizontal=16, vertical=16),
            ),
            on_click=lambda e: self.on_cancel(),
        )

        self.log_view = ft.ListView(
            expand=True,
            spacing=4,
            auto_scroll=True,
        )

        self.log_container = ft.Container(
            content=self.log_view,
            bgcolor="#070A0F",
            border_radius=6,
            border=ft.Border.all(1, COLOR_BORDER),
            padding=10,
            height=150,
        )

        self.content = ft.Column(
            spacing=12,
            controls=[
                # Linha de Seleção da Pasta de Destino do Backup
                ft.Row(
                    spacing=10,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    controls=[
                        self.folder_input,
                        self.browse_folder_btn,
                    ],
                ),
                ft.Row(
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    controls=[
                        ft.Column(
                            spacing=2,
                            controls=[
                                self.phase_label,
                                self.details_label,
                            ],
                        ),
                        ft.Row(
                            spacing=10,
                            controls=[
                                self.start_button,
                                self.pause_resume_button,
                                self.cancel_button,
                            ],
                        ),
                    ],
                ),
                ft.Column(
                    spacing=6,
                    controls=[
                        ft.Row(
                            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                            controls=[
                                ft.Text("Progresso de Extração de Biometrias Faciais:", size=12, color=COLOR_TEXT_SECONDARY),
                                self.faces_count_label,
                            ],
                        ),
                        self.faces_progress_bar,
                    ],
                ),
                ft.Column(
                    spacing=4,
                    controls=[
                        ft.Text("Console de Execução:", size=12, weight=ft.FontWeight.W_500, color=COLOR_TEXT_SECONDARY),
                        self.log_container,
                    ],
                ),
            ],
        )

    def add_log(self, message: str):
        """Insere uma linha no console de logs com rolagem automática."""
        self.log_view.controls.append(
            ft.Text(f"• {message}", size=11, font_family="Consolas, monospace", color="#CBD5E1")
        )
        self.update()

    def update_progress(self, progress: BackupProgress):
        """Atualiza os indicadores gráficos conforme o progresso recebido."""
        self.phase_label.value = progress.current_phase
        if progress.device_ip:
            self.details_label.value = f"Processando terminal: {progress.device_ip} ({progress.device_serial})"
        
        pct = progress.percent_faces / 100.0
        self.faces_progress_bar.value = pct
        self.faces_count_label.value = (
            f"Fotos: {progress.downloaded_faces} baixadas | "
            f"{progress.skipped_faces} deduplicadas | "
            f"Total: {progress.total_faces} ({progress.percent_faces:.1f}%)"
        )
        self.update()

    def set_running_state(self):
        self.start_button.visible = False
        self.pause_resume_button.visible = True
        self.cancel_button.visible = True
        self.pause_resume_button.content = "Pausar"
        self.pause_resume_button.icon = ft.Icons.PAUSE_ROUNDED
        self.update()

    def set_paused_state(self, is_paused: bool):
        if is_paused:
            self.pause_resume_button.content = "Retomar"
            self.pause_resume_button.icon = ft.Icons.PLAY_ARROW_ROUNDED
        else:
            self.pause_resume_button.content = "Pausar"
            self.pause_resume_button.icon = ft.Icons.PAUSE_ROUNDED
        self.update()

    def set_finished_state(self):
        self.start_button.visible = True
        self.pause_resume_button.visible = False
        self.cancel_button.visible = False
        self.update()

    def _browse_folder_dialog(self, e):
        """Abre janela nativa do Windows para o técnico escolher a pasta de destino."""
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
                    title="Selecione a Pasta para Salvar o Backup",
                    initialdir=initial_dir,
                )
                root.destroy()
                if selected_dir:
                    self.folder_input.value = str(Path(selected_dir).resolve())
                    self.update()
            except Exception:
                pass

        threading.Thread(target=open_dialog, daemon=True).start()
