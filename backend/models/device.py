"""
Modelos de domínio para dispositivos Control iD (iDFace, iDBox, etc.).
"""

from dataclasses import dataclass, field
from typing import Optional, Dict, Any


@dataclass
class DeviceBackupStats:
    """Estatísticas de pré-diagnóstico e backup de um dispositivo."""
    user_count: int = 0
    face_count: int = 0
    card_count: int = 0
    downloaded_faces: int = 0
    failed_faces: int = 0
    status: str = "Pendente"  # Pendente, Conectando, Extraindo, Concluído, Erro


@dataclass
class ControlIdDevice:
    """Representação de um terminal Control iD na rede."""
    ip: str
    port: int = 80
    serial: str = ""
    version: str = ""
    model: str = "iDFace"
    session: Optional[str] = None
    is_online: bool = False
    is_authenticated: bool = False
    auth_error: Optional[str] = None
    stats: DeviceBackupStats = field(default_factory=DeviceBackupStats)
    raw_info: Dict[str, Any] = field(default_factory=dict)
    selected_for_backup: bool = True

    @property
    def display_name(self) -> str:
        s = self.serial if self.serial else "S/N Desconhecido"
        return f"{self.model} ({self.ip}) - {s}"

    @property
    def base_url(self) -> str:
        scheme = "https" if self.port == 443 else "http"
        if self.port in (80, 443):
            return f"{scheme}://{self.ip}"
        return f"{scheme}://{self.ip}:{self.port}"
