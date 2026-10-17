"""
Painel de Conexão e Descoberta de Rede para equipamentos Control iD.
"""

import flet as ft
from typing import Callable
from backend.core.network_utils import get_default_local_subnet
from frontend.styles.theme import (
    COLOR_BG_SECONDARY,
    COLOR_BG_TERTIARY,
    COLOR_BORDER,
    COLOR_ACCENT,
    COLOR_TEXT_PRIMARY,
    COLOR_TEXT_SECONDARY,
)


class ConnectionPanel(ft.Container):
    """Componente para inserção de alvos de rede e credenciais de login."""

    def __init__(
        self,
        on_scan_clicked: Callable[[str, str, str], None],
        on_cancel_clicked: Callable[[], None],
    ):
        super().__init__(
            bgcolor=COLOR_BG_SECONDARY,
            border_radius=10,
            border=ft.Border.all(1, COLOR_BORDER),
            padding=16,
        )
        self.on_scan_clicked = on_scan_clicked
        self.on_cancel_clicked = on_cancel_clicked

        # Auto-detecta sub-rede ativa da máquina (ex: 192.168.3.0/24)
        detected_subnet = get_default_local_subnet()

        self.targets_input = ft.TextField(
            label="IP / Faixa de IPs / Notação CIDR",
            hint_text="Ex: 192.168.3.0/24 ou 192.168.3.100-110 ou 192.168.3.201",
            value=detected_subnet,
            bgcolor=COLOR_BG_TERTIARY,
            border_color=COLOR_BORDER,
            focused_border_color=COLOR_ACCENT,
            color=COLOR_TEXT_PRIMARY,
            text_size=13,
            expand=True,
        )

        self.user_input = ft.TextField(
            label="Usuário Catraca",
            value="admin",
            width=150,
            bgcolor=COLOR_BG_TERTIARY,
            border_color=COLOR_BORDER,
            focused_border_color=COLOR_ACCENT,
            color=COLOR_TEXT_PRIMARY,
            text_size=13,
        )

        self.password_input = ft.TextField(
            label="Senha Catraca",
            value="admin",
            password=True,
            can_reveal_password=True,
            width=150,
            bgcolor=COLOR_BG_TERTIARY,
            border_color=COLOR_BORDER,
            focused_border_color=COLOR_ACCENT,
            color=COLOR_TEXT_PRIMARY,
            text_size=13,
        )

        self.scan_button = ft.Button(
            content="Buscar Equipamentos",
            icon=ft.Icons.SEARCH_ROUNDED,
            style=ft.ButtonStyle(
                bgcolor=COLOR_ACCENT,
                color="#FFFFFF",
                padding=ft.Padding.symmetric(horizontal=18, vertical=16),
            ),
            on_click=self._handle_scan,
        )

        self.cancel_button = ft.OutlinedButton(
            content="Cancelar",
            icon=ft.Icons.STOP_CIRCLE_ROUNDED,
            visible=False,
            style=ft.ButtonStyle(
                side=ft.BorderSide(1, "#EF4444"),
                color="#EF4444",
                padding=ft.Padding.symmetric(horizontal=16, vertical=16),
            ),
            on_click=self._handle_cancel,
        )

        self.content = ft.Column(
            spacing=12,
            controls=[
                ft.Row(
                    spacing=12,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    controls=[
                        ft.Icon(ft.Icons.ROUTER_ROUNDED, color=COLOR_ACCENT, size=20),
                        ft.Text(
                            "Descoberta de Terminais na Rede Local (iDFace / Control iD)",
                            size=14,
                            weight=ft.FontWeight.W_600,
                            color=COLOR_TEXT_PRIMARY,
                        ),
                    ],
                ),
                ft.Row(
                    spacing=12,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    controls=[
                        self.targets_input,
                        self.user_input,
                        self.password_input,
                        self.scan_button,
                        self.cancel_button,
                    ],
                ),
            ],
        )

    def _handle_scan(self, e):
        targets = self.targets_input.value.strip()
        user = self.user_input.value.strip()
        pwd = self.password_input.value.strip()
        if targets:
            self.scan_button.visible = False
            self.cancel_button.visible = True
            self.update()
            self.on_scan_clicked(targets, user, pwd)

    def _handle_cancel(self, e):
        self.set_idle_state()
        self.on_cancel_clicked()

    def set_idle_state(self):
        """Restaura os botões para o estado inicial de repouso."""
        self.scan_button.visible = True
        self.cancel_button.visible = False
        self.update()
