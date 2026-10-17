"""
Entrypoint principal do Bot Backup Catraca (Control iD iDFace -> iDSecure / MySQL).
Inicia a aplicação desktop em Flet.
"""

import sys
import flet as ft
from frontend.styles.theme import apply_theme
from frontend.app import build_app


def main(page: ft.Page):
    """Inicializador da aplicação Flet."""
    apply_theme(page)
    build_app(page)


if __name__ == "__main__":
    if hasattr(ft, "run"):
        ft.run(main)
    else:
        ft.app(target=main)
