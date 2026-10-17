"""
Modelos de dados do Bot Backup Catraca.
"""

from .device import ControlIdDevice, DeviceBackupStats
from .backup_models import (
    BackupProgress,
    BackupAuditReport,
    MySQLConnectionConfig,
    iDSecureAPIConfig,
)

__all__ = [
    "ControlIdDevice",
    "DeviceBackupStats",
    "BackupProgress",
    "BackupAuditReport",
    "MySQLConnectionConfig",
    "iDSecureAPIConfig",
]
