"""
Serviço de exportação dos arquivos finais de backup:
- backup_full.json
- audit_report.json
- Organização e integridade da pasta /faces/
"""

import json
from pathlib import Path
from typing import Dict, Any, List
from dataclasses import asdict

from backend.services.sqlite_storage import SQLiteStorage
from backend.models.backup_models import BackupAuditReport


class ExporterService:
    """Exportador para JSON e geração de relatórios de auditoria."""

    def __init__(self, storage: SQLiteStorage, output_dir: str):
        self.storage = storage
        self.output_dir = Path(output_dir)

    def export_full_json(self) -> Path:
        """Exporta todos os dados consolidados do SQLite para um único arquivo JSON portátil."""
        output_file = self.output_dir / "backup_full.json"

        with self.storage._get_connection() as conn:
            # Carrega dispositivos
            devices = [dict(row) for row in conn.execute("SELECT * FROM source_devices").fetchall()]
            for d in devices:
                if d.get("raw_info_json"):
                    try:
                        d["raw_info"] = json.loads(d["raw_info_json"])
                    except Exception:
                        pass

            # Carrega usuários
            users = [dict(row) for row in conn.execute("SELECT * FROM users").fetchall()]
            # Carrega cartões
            cards = [dict(row) for row in conn.execute("SELECT * FROM cards").fetchall()]
            # Carrega grupos
            groups = [dict(row) for row in conn.execute("SELECT * FROM groups").fetchall()]
            user_groups = [dict(row) for row in conn.execute("SELECT * FROM user_groups").fetchall()]
            # Carrega regras
            rules = [dict(row) for row in conn.execute("SELECT * FROM access_rules").fetchall()]
            time_zones = [dict(row) for row in conn.execute("SELECT * FROM time_zones").fetchall()]
            time_spans = [dict(row) for row in conn.execute("SELECT * FROM time_spans").fetchall()]
            # Carrega imagens
            images = [dict(row) for row in conn.execute("SELECT * FROM user_images").fetchall()]

            data = {
                "version": "2.0",
                "exported_at": str(Path(self.output_dir).name),
                "source_devices": devices,
                "users": users,
                "cards": cards,
                "groups": groups,
                "user_groups": user_groups,
                "access_rules": rules,
                "time_zones": time_zones,
                "time_spans": time_spans,
                "user_images": images,
            }

            with open(output_file, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)

        return output_file

    def export_audit_report(self, report: BackupAuditReport) -> Path:
        """Salva o relatório detalhado de auditoria e conflitos em JSON."""
        output_file = self.output_dir / "audit_report.json"
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(asdict(report), f, ensure_ascii=False, indent=2)
        return output_file
