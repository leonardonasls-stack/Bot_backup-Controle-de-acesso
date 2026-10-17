"""
Motor de consolidação e deduplicação de cadastros de múltiplos equipamentos Control iD.
Aplica a regra 'Best-Record Wins' e detecta divergências/conflitos de cadastro entre catracas.
"""

from typing import Dict, Any, List, Tuple
from backend.services.sqlite_storage import SQLiteStorage


class DataMerger:
    """Consolidador e deduplicador multi-equipamento."""

    def __init__(self, storage: SQLiteStorage):
        self.storage = storage
        self.conflicts: List[Dict[str, Any]] = []

    def merge_users(self, device_serial: str, incoming_users: List[Dict[str, Any]]):
        """
        Consolida a lista de usuários extraídos de um terminal no banco consolidado.
        Regra:
        - Se o usuário não existe, insere.
        - Se já existe, compara timestamps e campos preenchidos (Best-Record Wins).
        - Se houver nomes diferentes para o mesmo ID, registra nos conflitos de auditoria.
        """
        if not incoming_users:
            return

        with self.storage._get_connection() as conn:
            for u in incoming_users:
                user_id = u["id"]
                name = str(u.get("name", "")).strip()
                registration = str(u.get("registration", "")).strip()
                password = str(u.get("password", "")).strip()
                salt = str(u.get("salt", "")).strip()
                user_type_id = int(u.get("user_type_id", 0))
                image_timestamp = int(u.get("image_timestamp", 0) or 0)
                begin_time = int(u.get("begin_time", 0) or 0)
                end_time = int(u.get("end_time", 0) or 0)

                cursor = conn.execute(
                    "SELECT id, name, registration, image_timestamp, source_device_serial FROM users WHERE id = ?",
                    (user_id,),
                )
                existing = cursor.fetchone()

                if not existing:
                    # Inserção direta
                    conn.execute(
                        """
                        INSERT INTO users (id, registration, name, password, salt, user_type_id, image_timestamp, begin_time, end_time, source_device_serial)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            user_id,
                            registration,
                            name,
                            password,
                            salt,
                            user_type_id,
                            image_timestamp,
                            begin_time,
                            end_time,
                            device_serial,
                        ),
                    )
                else:
                    # Checa conflito de nome para o mesmo ID
                    if existing["name"] != name and name:
                        self.conflicts.append({
                            "type": "USER_NAME_CONFLICT",
                            "user_id": user_id,
                            "existing_name": existing["name"],
                            "incoming_name": name,
                            "device_1": existing["source_device_serial"],
                            "device_2": device_serial,
                        })

                    # Aplica Best-Record: atualiza se a nova versão tiver foto mais recente ou matrícula preenchida
                    should_update = False
                    if image_timestamp > (existing["image_timestamp"] or 0):
                        should_update = True
                    elif not existing["registration"] and registration:
                        should_update = True

                    if should_update:
                        conn.execute(
                            """
                            UPDATE users SET
                                registration = CASE WHEN ? != '' THEN ? ELSE registration END,
                                name = CASE WHEN ? != '' THEN ? ELSE name END,
                                image_timestamp = MAX(image_timestamp, ?),
                                user_type_id = ?,
                                updated_at = CURRENT_TIMESTAMP
                            WHERE id = ?
                            """,
                            (
                                registration,
                                registration,
                                name,
                                name,
                                image_timestamp,
                                user_type_id,
                                user_id,
                            ),
                        )
            conn.commit()

    def merge_cards(self, device_serial: str, incoming_cards: List[Dict[str, Any]]):
        """Consolida cartões evitando duplicações por (user_id, value)."""
        if not incoming_cards:
            return

        with self.storage._get_connection() as conn:
            for card in incoming_cards:
                card_id = card.get("id")
                user_id = card.get("user_id")
                val = str(card.get("value", ""))
                c_type = int(card.get("type", 1))

                conn.execute(
                    """
                    INSERT INTO cards (id, user_id, value, type, source_device_serial)
                    VALUES (?, ?, ?, ?, ?)
                    ON CONFLICT(id) DO UPDATE SET
                        user_id = excluded.user_id,
                        value = excluded.value,
                        type = excluded.type;
                    """,
                    (card_id, user_id, val, c_type, device_serial),
                )
            conn.commit()

    def merge_groups(self, device_serial: str, incoming_groups: List[Dict[str, Any]]):
        """Consolida grupos/departamentos."""
        if not incoming_groups:
            return

        with self.storage._get_connection() as conn:
            for g in incoming_groups:
                conn.execute(
                    """
                    INSERT INTO groups (id, name, source_device_serial)
                    VALUES (?, ?, ?)
                    ON CONFLICT(id) DO UPDATE SET name = excluded.name;
                    """,
                    (g["id"], g.get("name", ""), device_serial),
                )
            conn.commit()

    def merge_user_groups(
        self, device_serial: str, incoming_user_groups: List[Dict[str, Any]]
    ):
        """Consolida vínculos de usuário com grupo."""
        if not incoming_user_groups:
            return

        with self.storage._get_connection() as conn:
            for ug in incoming_user_groups:
                conn.execute(
                    """
                    INSERT INTO user_groups (user_id, group_id, source_device_serial)
                    VALUES (?, ?, ?)
                    ON CONFLICT(user_id, group_id) DO NOTHING;
                    """,
                    (ug["user_id"], ug["group_id"], device_serial),
                )
            conn.commit()

    def merge_access_rules(
        self, device_serial: str, rules: List[Dict[str, Any]], time_zones: List[Dict[str, Any]], time_spans: List[Dict[str, Any]]
    ):
        """Consolida regras de acesso e faixas de horário."""
        with self.storage._get_connection() as conn:
            for r in rules:
                conn.execute(
                    """
                    INSERT INTO access_rules (id, name, type, priority, source_device_serial)
                    VALUES (?, ?, ?, ?, ?)
                    ON CONFLICT(id) DO UPDATE SET name = excluded.name;
                    """,
                    (r["id"], r.get("name", ""), r.get("type", 1), r.get("priority", 0), device_serial),
                )

            for tz in time_zones:
                conn.execute(
                    """
                    INSERT INTO time_zones (id, name, source_device_serial)
                    VALUES (?, ?, ?)
                    ON CONFLICT(id) DO UPDATE SET name = excluded.name;
                    """,
                    (tz["id"], tz.get("name", ""), device_serial),
                )

            for ts in time_spans:
                conn.execute(
                    """
                    INSERT INTO time_spans (id, time_zone_id, start, end, sun, mon, tue, wed, thu, fri, sat, hol1, hol2, hol3, source_device_serial)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(id) DO NOTHING;
                    """,
                    (
                        ts.get("id"),
                        ts.get("time_zone_id"),
                        ts.get("start"),
                        ts.get("end"),
                        ts.get("sun", 0),
                        ts.get("mon", 1),
                        ts.get("tue", 1),
                        ts.get("wed", 1),
                        ts.get("thu", 1),
                        ts.get("fri", 1),
                        ts.get("sat", 0),
                        ts.get("hol1", 0),
                        ts.get("hol2", 0),
                        ts.get("hol3", 0),
                        device_serial,
                    ),
                )
            conn.commit()
