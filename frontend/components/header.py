"""
Header principal da aplicação com identificação, badge de status e versão.
"""

import flet as ft
from frontend.styles.theme import (
    COLOR_BG_SECONDARY,
    COLOR_BORDER,
    COLOR_ACCENT,
    COLOR_TEXT_PRIMARY,
    COLOR_TEXT_SECONDARY,
)


def create_header() -> ft.Container:
    """Retorna o cabeçalho superior da aplicação."""
    return ft.Container(
        content=ft.Row(
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            controls=[
                ft.Row(
                    spacing=12,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    controls=[
                        ft.Icon(ft.Icons.SHIELD_ROUNDED, color=COLOR_ACCENT, size=32),
                        ft.Column(
                            spacing=2,
                            controls=[
                                ft.Row(
                                    spacing=8,
                                    controls=[
                                        ft.Text(
                                            "BOT BACKUP CATRACA",
                                            size=18,
                                            weight=ft.FontWeight.BOLD,
                                            color=COLOR_TEXT_PRIMARY,
                                        ),
                                        ft.Container(
                                            content=ft.Text(
                                                "v2.0 PRO",
                                                size=11,
                                                weight=ft.FontWeight.BOLD,
                                                color="#0369A1",
                                            ),
                                            bgcolor="#E0F2FE",
                                            border_radius=4,
                                            padding=ft.Padding.symmetric(horizontal=6, vertical=2),
                                        ),
                                    ],
                                ),
                                ft.Text(
                                    "Extração iDFace • Staging SQLite • Restauração MySQL / iDSecure",
                                    size=12,
                                    color=COLOR_TEXT_SECONDARY,
                                ),
                            ],
                        ),
                    ],
                ),
                ft.Row(
                    spacing=8,
                    controls=[
                        ft.Icon(ft.Icons.STORAGE_ROUNDED, color=COLOR_ACCENT, size=18),
                        ft.Text("Dual-Engine: SQLite + MySQL", size=12, color=COLOR_TEXT_SECONDARY),
                    ],
                ),
            ],
        ),
        bgcolor=COLOR_BG_SECONDARY,
        padding=ft.Padding.symmetric(horizontal=24, vertical=16),
        border=ft.Border.only(bottom=ft.BorderSide(1, COLOR_BORDER)),
    )
