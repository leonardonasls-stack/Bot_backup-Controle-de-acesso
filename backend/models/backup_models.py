"""
Modelos de domínio para progresso de backup, auditoria, configurações do MySQL e API do iDSecure.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Dict, Any, Optional


@dataclass
class BackupProgress:
    """Acompanhamento em tempo real do progresso de extração e salvamento."""
    current_phase: str = "Iniciando..."  # Conectando, Extraindo Objetos, Baixando Fotos, Finalizando
    device_ip: str = ""
    device_serial: str = ""
    total_objects: int = 0
    extracted_objects: int = 0
    total_faces: int = 0
    downloaded_faces: int = 0
    failed_faces: int = 0
    skipped_faces: int = 0  # Deduplicadas / já existentes
    start_time: Optional[datetime] = None
    eta_seconds: Optional[int] = None
    is_paused: bool = False
    is_cancelled: bool = False
    error_message: Optional[str] = None

    @property
    def percent_faces(self) -> float:
        if self.total_faces == 0:
            return 100.0
        done = self.downloaded_faces + self.skipped_faces
        return min(100.0, (done / self.total_faces) * 100.0)

    @property
    def percent_objects(self) -> float:
        if self.total_objects == 0:
            return 100.0
        return min(100.0, (self.extracted_objects / self.total_objects) * 100.0)


@dataclass
class BackupAuditReport:
    """Relatório final de auditoria e métricas de integridade pós-backup."""
    backup_id: str
    created_at: str
    target_folder: str
    devices_scanned: int = 0
    devices_backed_up: int = 0
    total_users_consolidated: int = 0
    total_cards_consolidated: int = 0
    total_groups_consolidated: int = 0
    total_access_rules_consolidated: int = 0
    total_faces_downloaded: int = 0
    total_faces_deduplicated: int = 0
    total_faces_failed: int = 0
    devices_details: List[Dict[str, Any]] = field(default_factory=list)
    conflicts_detected: List[Dict[str, Any]] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)


@dataclass
class MySQLConnectionConfig:
    """Parâmetros de conexão direta com o servidor MySQL do iDSecure."""
    host: str = "localhost"
    port: int = 3306
    user: str = "root"
    password: str = ""
    database: str = "idsecure"
    charset: str = "utf8mb4"
    connect_timeout: int = 10


@dataclass
class iDSecureAPIConfig:
    """Configurações de integração com a API local do servidor iDSecure."""
    base_url: str = "https://localhost:30443"
    api_user: str = "admin"
    api_password: str = "admin"
    verify_ssl: bool = False
    token: Optional[str] = None
