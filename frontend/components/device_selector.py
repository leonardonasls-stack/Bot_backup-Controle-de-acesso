"""
Tabela de seleção de terminais Control iD encontrados na rede.
Exibe checkbox para seleção individual, IP, Modelo, Serial, Usuários, Fotos e Status.
"""

import flet as ft
from typing import List, Callable
from backend.models.device import ControlIdDevice
from frontend.styles.theme import (
    COLOR_BG_SECONDARY,
    COLOR_BG_TERTIARY,
    COLOR_BORDER,
    COLOR_ACCENT,
    COLOR_SUCCESS,
    COLOR_WARNING,
    COLOR_DANGER,
    COLOR_TEXT_PRIMARY,
    COLOR_TEXT_SECONDARY,
)


class DeviceSelector(ft.Container):
    """Componente para listagem tabular dos dispositivos com pré-diagnóstico."""

    def __init__(self, on_selection_changed: Callable[[], None]):
        super().__init__(
            bgcolor=COLOR_BG_SECONDARY,
            border_radius=10,
            border=ft.Border.all(1, COLOR_BORDER),
            padding=16,
        )
        self.on_selection_changed = on_selection_changed
        self.devices: List[ControlIdDevice] = []

        self.table = ft.DataTable(
            columns=[
                ft.DataColumn(ft.Text("Sel.", size=12, weight=ft.FontWeight.BOLD, color=COLOR_TEXT_SECONDARY)),
                ft.DataColumn(ft.Text("Endereço IP", size=12, weight=ft.FontWeight.BOLD, color=COLOR_TEXT_SECONDARY)),
                ft.DataColumn(ft.Text("Modelo", size=12, weight=ft.FontWeight.BOLD, color=COLOR_TEXT_SECONDARY)),
                ft.DataColumn(ft.Text("Número de Série", size=12, weight=ft.FontWeight.BOLD, color=COLOR_TEXT_SECONDARY)),
                ft.DataColumn(ft.Text("Usuários", size=12, weight=ft.FontWeight.BOLD, color=COLOR_TEXT_SECONDARY)),
                ft.DataColumn(ft.Text("Fotos Faciais", size=12, weight=ft.FontWeight.BOLD, color=COLOR_TEXT_SECONDARY)),
                ft.DataColumn(ft.Text("Status", size=12, weight=ft.FontWeight.BOLD, color=COLOR_TEXT_SECONDARY)),
            ],
            rows=[],
            heading_row_height=36,
            data_row_min_height=42,
            border_radius=8,
        )

        self.empty_label = ft.Text(
            "Nenhum equipamento localizado. Digite a faixa de IPs acima e clique em 'Buscar Equipamentos'.",
            size=13,
            color=COLOR_TEXT_SECONDARY,
            italic=True,
        )

        self.total_label = ft.Text("Total: 0 terminal(is)", size=12, color=COLOR_TEXT_SECONDARY)

        self.content = ft.Column(
            spacing=10,
            controls=[
                ft.Row(
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    controls=[
                        ft.Row(
                            spacing=8,
                            controls=[
                                ft.Icon(ft.Icons.FORMAT_LIST_BULLETED_ROUNDED, color=COLOR_ACCENT, size=18),
                                ft.Text(
                                    "Terminais iDFace Selecionados para Backup",
                                    size=13,
                                    weight=ft.FontWeight.W_600,
                                    color=COLOR_TEXT_PRIMARY,
                                ),
                            ],
                        ),
                        self.total_label,
                    ],
                ),
                ft.Column(
                    controls=[self.empty_label, self.table],
                    scroll=ft.ScrollMode.ADAPTIVE,
                ),
            ],
        )

    def set_devices(self, devices: List[ControlIdDevice]):
        """Atualiza a lista de terminais e reconstrói as linhas da tabela."""
        self.devices = devices
        self.total_label.value = f"Total: {len(self.devices)} terminal(is)"
        self.render_rows()
        self.update()

    def render_rows(self):
        """Monta as DataRow da tabela."""
        if not self.devices:
            self.table.rows = []
            self.empty_label.visible = True
            return

        self.empty_label.visible = False
        rows = []
        for dev in self.devices:
            def create_check_handler(device: ControlIdDevice):
                return lambda e: self._on_checkbox_change(device, e.control.value)

            status_color = COLOR_SUCCESS if dev.stats.status in ("OK", "Objetos OK", "Concluído") else (
                COLOR_DANGER if dev.stats.status == "Erro" else COLOR_TEXT_SECONDARY
            )

            rows.append(
                ft.DataRow(
                    cells=[
                        ft.DataCell(
                            ft.Checkbox(
                                value=dev.selected_for_backup,
                                active_color=COLOR_ACCENT,
                                on_change=create_check_handler(dev),
                            )
                        ),
                        ft.DataCell(ft.Text(f"{dev.ip}:{dev.port}", size=13, color=COLOR_TEXT_PRIMARY, weight=ft.FontWeight.W_500)),
                        ft.DataCell(ft.Text(dev.model, size=13, color=COLOR_TEXT_PRIMARY)),
                        ft.DataCell(ft.Text(dev.serial or "—", size=13, color=COLOR_TEXT_PRIMARY)),
                        ft.DataCell(ft.Text(str(dev.stats.user_count) if dev.stats.user_count else "—", size=13, color=COLOR_TEXT_PRIMARY)),
                        ft.DataCell(ft.Text(str(dev.stats.face_count) if dev.stats.face_count else "—", size=13, color=COLOR_ACCENT, weight=ft.FontWeight.W_600)),
                        ft.DataCell(
                            ft.Container(
                                content=ft.Text(dev.stats.status, size=11, weight=ft.FontWeight.BOLD, color=status_color),
                                padding=ft.Padding.symmetric(horizontal=8, vertical=4),
                                border_radius=4,
                                bgcolor=COLOR_BG_TERTIARY,
                            )
                        ),
                    ]
                )
            )
        self.table.rows = rows

    def _on_checkbox_change(self, device: ControlIdDevice, value: bool):
        device.selected_for_backup = bool(value)
        self.on_selection_changed()

    def get_selected_devices(self) -> List[ControlIdDevice]:
        return [d for d in self.devices if d.selected_for_backup]
