"""
Resumo de Auditoria pós-backup com cartões de métricas (KPIs) e ações rápidas.
"""

import os
import subprocess
import flet as ft
from typing import Optional
from backend.models.backup_models import BackupAuditReport
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


class AuditSummary(ft.Container):
    """Componente para exibição dos resultados consolidados da extração."""

    def __init__(self):
        super().__init__(
            bgcolor=COLOR_BG_SECONDARY,
            border_radius=10,
            border=ft.Border.all(1, COLOR_BORDER),
            padding=16,
            visible=False,
        )
        self.report: Optional[BackupAuditReport] = None

        self.users_card = self._create_kpi_card("Usuários Consolidados", "0", ft.Icons.PEOPLE_ROUNDED, COLOR_ACCENT)
        self.faces_card = self._create_kpi_card("Fotos Extraídas", "0", ft.Icons.FACE_ROUNDED, COLOR_SUCCESS)
        self.dedup_card = self._create_kpi_card("Fotos Deduplicadas", "0", ft.Icons.FILTER_NONE_ROUNDED, COLOR_WARNING)
        self.cards_card = self._create_kpi_card("Cartões / Crachás", "0", ft.Icons.CREDIT_CARD_ROUNDED, "#8B5CF6")

        self.target_folder_text = ft.Text("Pasta do Backup: —", size=12, color=COLOR_TEXT_SECONDARY)

        self.open_folder_btn = ft.Button(
            content="Abrir Pasta do Backup",
            icon=ft.Icons.FOLDER_OPEN_ROUNDED,
            style=ft.ButtonStyle(
                bgcolor=COLOR_BG_TERTIARY,
                color=COLOR_TEXT_PRIMARY,
                side=ft.BorderSide(1, COLOR_BORDER),
            ),
            on_click=self._open_backup_folder,
        )

        self.content = ft.Column(
            spacing=12,
            controls=[
                ft.Row(
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    controls=[
                        ft.Row(
                            spacing=8,
                            controls=[
                                ft.Icon(ft.Icons.CHECK_CIRCLE_ROUNDED, color=COLOR_SUCCESS, size=20),
                                ft.Text(
                                    "Resumo de Auditoria & Integridade da Extração",
                                    size=13,
                                    weight=ft.FontWeight.W_600,
                                    color=COLOR_TEXT_PRIMARY,
                                ),
                            ],
                        ),
                        self.open_folder_btn,
                    ],
                ),
                ft.Row(
                    spacing=12,
                    controls=[
                        self.users_card,
                        self.faces_card,
                        self.dedup_card,
                        self.cards_card,
                    ],
                ),
                self.target_folder_text,
            ],
        )

    def _create_kpi_card(self, title: str, value: str, icon: str, color: str) -> ft.Container:
        return ft.Container(
            content=ft.Row(
                spacing=12,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                controls=[
                    ft.Icon(icon, color=color, size=28),
                    ft.Column(
                        spacing=2,
                        controls=[
                            ft.Text(title, size=11, color=COLOR_TEXT_SECONDARY),
                            ft.Text(value, size=18, weight=ft.FontWeight.BOLD, color=COLOR_TEXT_PRIMARY),
                        ],
                    ),
                ],
            ),
            bgcolor=COLOR_BG_TERTIARY,
            border_radius=8,
            border=ft.Border.all(1, COLOR_BORDER),
            padding=ft.Padding.symmetric(horizontal=16, vertical=12),
            expand=True,
        )

    def set_report(self, report: BackupAuditReport):
        self.report = report
        # Atualiza valores
        self.users_card.content.controls[1].controls[1].value = str(report.total_users_consolidated)
        self.faces_card.content.controls[1].controls[1].value = str(report.total_faces_downloaded)
        self.dedup_card.content.controls[1].controls[1].value = str(report.total_faces_deduplicated)
        self.cards_card.content.controls[1].controls[1].value = str(report.total_cards_consolidated)
        self.target_folder_text.value = f"Pasta do Backup: {report.target_folder}"
        self.visible = True
        self.update()

    def _open_backup_folder(self, e):
        if self.report and self.report.target_folder:
            folder = self.report.target_folder
            if os.name == "nt":
                os.startfile(folder)
            else:
                subprocess.run(["xdg-open", folder])
