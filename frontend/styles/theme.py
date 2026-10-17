"""
Tema Dark Mode corporativo e padronização visual da aplicação Desktop Flet.
Segue a identidade visual de ferramentas de missão crítica de infraestrutura (Dark Slate & Neon Accent).
"""

import flet as ft

# Paleta de Cores
COLOR_BG_PRIMARY = "#0B0F17"       # Fundo principal escuro profundo
COLOR_BG_SECONDARY = "#131C2E"     # Fundo de cards, containers e painéis
COLOR_BG_TERTIARY = "#1E293B"      # Fundo de inputs, bordas e divisores
COLOR_BORDER = "#334155"           # Bordas sutis elegantes

# Cores de Acento
COLOR_ACCENT = "#0EA5E9"           # Cyan moderno / Azul vibrante
COLOR_ACCENT_HOVER = "#38BDF8"
COLOR_SUCCESS = "#10B981"          # Verde esmeralda (Conectado / Sucesso)
COLOR_WARNING = "#F59E0B"          # Âmbar (Avisos / Conflitos)
COLOR_DANGER = "#EF4444"           # Vermelho (Falhas / Erros)

# Tipografia e Textos
COLOR_TEXT_PRIMARY = "#F8FAFC"     # Branco puro para títulos e destaque
COLOR_TEXT_SECONDARY = "#94A3B8"   # Cinza suave para legendas e labels
COLOR_TEXT_MUTED = "#64748B"       # Cinza discreto para hints


def apply_theme(page: ft.Page):
    """Configura o tema global e dimensões da janela."""
    page.title = "BOT BACKUP CATRACA — Control iD iDFace ↔ iDSecure & MySQL"
    page.theme_mode = ft.ThemeMode.DARK
    page.bgcolor = COLOR_BG_PRIMARY
    page.padding = 0
    page.window.width = 1180
    page.window.height = 760
    page.window.min_width = 1000
    page.window.min_height = 680


def create_card_container(content: ft.Control, padding: int = 20) -> ft.Container:
    """Cria um card moderno com bordas arredondadas e sombra suave."""
    return ft.Container(
        content=content,
        bgcolor=COLOR_BG_SECONDARY,
        border_radius=10,
        border=ft.Border.all(1, COLOR_BORDER),
        padding=padding,
    )
