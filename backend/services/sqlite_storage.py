"""
Serviço de persistência local SQLite para staging do backup Control iD.
Garante integridade, armazenamento bruto para rastreabilidade e tabela consolidada
com suporte nativo a checkpoints incrementais de retomada.
"""

import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Dict, Any, List, Optional, Set, Tuple


class SQLiteStorage:
    """Gerenciador de banco SQLite local para extração e checkpoints do iDFace."""

    def __init__(self, db_path: str):
        self.db_path = str(db_path)
        # Garante que a pasta pai exista
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    @contextmanager
    def _get_connection(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON;")
        try:
            yield conn
        finally:
            conn.close()

    def _init_db(self):
        """Cria as tabelas necessárias no SQLite local caso não existam."""
        with self._get_connection() as conn:
            # 1. Tabela de dispositivos de origem
            conn.execute("""
                CREATE TABLE IF NOT EXISTS source_devices (
                    serial TEXT PRIMARY KEY,
                    ip TEXT NOT NULL,
                    port INTEGER DEFAULT 80,
                    model TEXT,
                    version TEXT,
                    raw_info_json TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)

            # 2. Tabela de objetos brutos extraídos por catraca (para auditoria)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS raw_device_objects (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    device_serial TEXT NOT NULL,
                    object_name TEXT NOT NULL,
                    object_id INTEGER,
                    payload_json TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (device_serial) REFERENCES source_devices(serial)
                );
            """)

            # 3. Tabelas Consolidadas
            conn.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY,
                    registration TEXT,
                    name TEXT NOT NULL,
                    password TEXT DEFAULT '',
                    salt TEXT DEFAULT '',
                    user_type_id INTEGER DEFAULT 0,
                    image_timestamp INTEGER DEFAULT 0,
                    begin_time INTEGER DEFAULT 0,
                    end_time INTEGER DEFAULT 0,
                    source_device_serial TEXT,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)

            conn.execute("""
                CREATE TABLE IF NOT EXISTS cards (
                    id INTEGER PRIMARY KEY,
                    user_id INTEGER,
                    value TEXT NOT NULL,
                    type INTEGER DEFAULT 1,
                    source_device_serial TEXT,
                    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
                );
            """)

            conn.execute("""
                CREATE TABLE IF NOT EXISTS groups (
                    id INTEGER PRIMARY KEY,
                    name TEXT NOT NULL,
                    source_device_serial TEXT
                );
            """)

            conn.execute("""
                CREATE TABLE IF NOT EXISTS user_groups (
                    user_id INTEGER,
                    group_id INTEGER,
                    source_device_serial TEXT,
                    PRIMARY KEY (user_id, group_id)
                );
            """)

            conn.execute("""
                CREATE TABLE IF NOT EXISTS time_zones (
                    id INTEGER PRIMARY KEY,
                    name TEXT NOT NULL,
                    source_device_serial TEXT
                );
            """)

            conn.execute("""
                CREATE TABLE IF NOT EXISTS time_spans (
                    id INTEGER PRIMARY KEY,
                    time_zone_id INTEGER,
                    start INTEGER,
                    end INTEGER,
                    sun INTEGER DEFAULT 0,
                    mon INTEGER DEFAULT 1,
                    tue INTEGER DEFAULT 1,
                    wed INTEGER DEFAULT 1,
                    thu INTEGER DEFAULT 1,
                    fri INTEGER DEFAULT 1,
                    sat INTEGER DEFAULT 0,
                    hol1 INTEGER DEFAULT 0,
                    hol2 INTEGER DEFAULT 0,
                    hol3 INTEGER DEFAULT 0,
                    source_device_serial TEXT
                );
            """)

            conn.execute("""
                CREATE TABLE IF NOT EXISTS access_rules (
                    id INTEGER PRIMARY KEY,
                    name TEXT NOT NULL,
                    type INTEGER DEFAULT 1,
                    priority INTEGER DEFAULT 0,
                    source_device_serial TEXT
                );
            """)

            # Tabelas relacionais de regras de acesso
            conn.execute("""
                CREATE TABLE IF NOT EXISTS group_access_rules (
                    group_id INTEGER,
                    access_rule_id INTEGER,
                    source_device_serial TEXT,
                    PRIMARY KEY (group_id, access_rule_id)
                );
            """)

            conn.execute("""
                CREATE TABLE IF NOT EXISTS user_access_rules (
                    user_id INTEGER,
                    access_rule_id INTEGER,
                    source_device_serial TEXT,
                    PRIMARY KEY (user_id, access_rule_id)
                );
            """)

            conn.execute("""
                CREATE TABLE IF NOT EXISTS access_rule_time_zones (
                    access_rule_id INTEGER,
                    time_zone_id INTEGER,
                    source_device_serial TEXT,
                    PRIMARY KEY (access_rule_id, time_zone_id)
                );
            """)

            conn.execute("""
                CREATE TABLE IF NOT EXISTS portal_access_rules (
                    portal_id INTEGER,
                    access_rule_id INTEGER,
                    source_device_serial TEXT,
                    PRIMARY KEY (portal_id, access_rule_id)
                );
            """)

            conn.execute("""
                CREATE TABLE IF NOT EXISTS holidays (
                    id INTEGER PRIMARY KEY,
                    name TEXT NOT NULL,
                    day INTEGER,
                    month INTEGER,
                    year INTEGER DEFAULT 0,
                    holiday_type INTEGER DEFAULT 1,
                    source_device_serial TEXT
                );
            """)

            # 4. Tabela de Fotos e Checkpoints de Download
            conn.execute("""
                CREATE TABLE IF NOT EXISTS user_images (
                    user_id INTEGER PRIMARY KEY,
                    timestamp INTEGER DEFAULT 0,
                    file_path TEXT,
                    file_size INTEGER DEFAULT 0,
                    status TEXT DEFAULT 'PENDING',  -- PENDING, DOWNLOADED, FAILED, SKIPPED
                    source_device_serial TEXT,
                    downloaded_at TIMESTAMP,
                    error_message TEXT
                );
            """)

            conn.commit()

    def register_device(
        self,
        serial: str,
        ip: str,
        port: int = 80,
        model: str = "iDFace",
        version: str = "",
        raw_info: Optional[Dict[str, Any]] = None,
    ):
        """Registra o dispositivo de origem no banco de backup."""
        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT INTO source_devices (serial, ip, port, model, version, raw_info_json)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(serial) DO UPDATE SET
                    ip = excluded.ip,
                    port = excluded.port,
                    model = excluded.model,
                    version = excluded.version,
                    raw_info_json = excluded.raw_info_json;
                """,
                (
                    serial,
                    ip,
                    port,
                    model,
                    version,
                    json.dumps(raw_info or {}, ensure_ascii=False),
                ),
            )
            conn.commit()

    def save_raw_objects(
        self, device_serial: str, object_name: str, items: List[Dict[str, Any]]
    ):
        """Salva a cópia bruta de objetos recebidos de um dispositivo."""
        if not items:
            return

        with self._get_connection() as conn:
            records = [
                (
                    device_serial,
                    object_name,
                    item.get("id"),
                    json.dumps(item, ensure_ascii=False),
                )
                for item in items
            ]
            conn.executemany(
                """
                INSERT INTO raw_device_objects (device_serial, object_name, object_id, payload_json)
                VALUES (?, ?, ?, ?)
                """,
                records,
            )
            conn.commit()

    def get_downloaded_face_ids(self) -> Set[int]:
        """Retorna os IDs de usuários cujas fotos já foram baixadas com sucesso (para checkpoints)."""
        with self._get_connection() as conn:
            cursor = conn.execute(
                "SELECT user_id FROM user_images WHERE status = 'DOWNLOADED'"
            )
            return {row["user_id"] for row in cursor.fetchall()}

    def get_face_timestamp(self, user_id: int) -> int:
        """Obtém o timestamp da foto registrada para um user_id."""
        with self._get_connection() as conn:
            cursor = conn.execute(
                "SELECT timestamp FROM user_images WHERE user_id = ?", (user_id,)
            )
            row = cursor.fetchone()
            return row["timestamp"] if row and row["timestamp"] is not None else 0

    def register_user_image(
        self,
        user_id: int,
        timestamp: int,
        file_path: Optional[str] = None,
        file_size: int = 0,
        status: str = "PENDING",
        source_device_serial: Optional[str] = None,
        error_message: Optional[str] = None,
    ):
        """Registra ou atualiza o status de download da imagem facial."""
        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT INTO user_images (user_id, timestamp, file_path, file_size, status, source_device_serial, downloaded_at, error_message)
                VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, ?)
                ON CONFLICT(user_id) DO UPDATE SET
                    timestamp = excluded.timestamp,
                    file_path = excluded.file_path,
                    file_size = excluded.file_size,
                    status = excluded.status,
                    source_device_serial = excluded.source_device_serial,
                    downloaded_at = CURRENT_TIMESTAMP,
                    error_message = excluded.error_message;
                """,
                (
                    user_id,
                    timestamp,
                    file_path,
                    file_size,
                    status,
                    source_device_serial,
                    error_message,
                ),
            )
            conn.commit()

    def get_stats_summary(self) -> Dict[str, int]:
        """Retorna contadores consolidados de usuários, cartões, grupos e fotos."""
        with self._get_connection() as conn:
            users_count = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
            cards_count = conn.execute("SELECT COUNT(*) FROM cards").fetchone()[0]
            groups_count = conn.execute("SELECT COUNT(*) FROM groups").fetchone()[0]
            rules_count = conn.execute("SELECT COUNT(*) FROM access_rules").fetchone()[0]
            faces_downloaded = conn.execute(
                "SELECT COUNT(*) FROM user_images WHERE status = 'DOWNLOADED'"
            ).fetchone()[0]
            faces_failed = conn.execute(
                "SELECT COUNT(*) FROM user_images WHERE status = 'FAILED'"
            ).fetchone()[0]

            return {
                "users": users_count,
                "cards": cards_count,
                "groups": groups_count,
                "access_rules": rules_count,
                "faces_downloaded": faces_downloaded,
                "faces_failed": faces_failed,
            }
