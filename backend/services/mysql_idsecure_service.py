"""
Serviço de Tradução e Restauração Direta no MySQL do iDSecure.
Gera o dump SQL completo (dump_idsecure_mysql.sql) e realiza injeção direta via PyMySQL
com introspecção dinâmica de schema (INFORMATION_SCHEMA.COLUMNS) para máxima compatibilidade.
"""

from pathlib import Path
import sqlite3
import time
from typing import Dict, Any, List, Optional, Set, Tuple

try:
    import pymysql
    import pymysql.cursors
except ImportError:
    pymysql = None

from backend.models.backup_models import MySQLConnectionConfig
from backend.services.sqlite_storage import SQLiteStorage


class MySQLIDSecureService:
    """Gerador de script SQL e conector de injeção direta no MySQL do iDSecure."""

    def __init__(self, storage: SQLiteStorage, output_dir: str):
        self.storage = storage
        self.output_dir = Path(output_dir)

    def test_connection(self, config: MySQLConnectionConfig) -> Tuple[bool, str]:
        """Testa conectividade na porta 3306 e autenticação no MySQL."""
        if pymysql is None:
            return False, "Driver PyMySQL não está instalado no ambiente."

        try:
            conn = pymysql.connect(
                host=config.host,
                port=config.port,
                user=config.user,
                password=config.password,
                database=config.database,
                charset=config.charset,
                connect_timeout=config.connect_timeout,
                cursorclass=pymysql.cursors.DictCursor,
            )
            with conn.cursor() as cursor:
                cursor.execute("SELECT VERSION() AS ver, DATABASE() AS db;")
                row = cursor.fetchone()
                version = row.get("ver", "Desconhecida") if row else ""
            conn.close()
            return True, f"Conexão estabelecida com sucesso! MySQL versão: {version}"
        except Exception as e:
            return False, f"Falha ao conectar no MySQL: {str(e)}"

    def get_existing_table_columns(self, config: MySQLConnectionConfig) -> Dict[str, Dict[str, Dict[str, Any]]]:
        """
        Inspeciona o INFORMATION_SCHEMA para obter colunas reais, tipo de dados, se aceita nulo e valor padrão.
        Retorna: { 'tabela_minuscula': { 'coluna_minuscula': {'data_type': str, 'nullable': bool, 'default': Any} } }
        """
        if pymysql is None:
            return {}

        cols_by_table: Dict[str, Dict[str, Dict[str, Any]]] = {}
        try:
            conn = pymysql.connect(
                host=config.host,
                port=config.port,
                user=config.user,
                password=config.password,
                database=config.database,
                charset=config.charset,
                connect_timeout=config.connect_timeout,
                cursorclass=pymysql.cursors.DictCursor,
            )
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT TABLE_NAME, COLUMN_NAME, DATA_TYPE, IS_NULLABLE, COLUMN_DEFAULT, EXTRA
                    FROM INFORMATION_SCHEMA.COLUMNS
                    WHERE TABLE_SCHEMA = %s;
                    """,
                    (config.database,),
                )
                for row in cursor.fetchall():
                    tbl = row["TABLE_NAME"].lower()
                    col = row["COLUMN_NAME"].lower()
                    dtype = (row.get("DATA_TYPE") or "").lower()
                    nullable = (row.get("IS_NULLABLE") or "").upper() == "YES"
                    col_def = row.get("COLUMN_DEFAULT")
                    extra = (row.get("EXTRA") or "").lower()

                    if tbl not in cols_by_table:
                        cols_by_table[tbl] = {}
                    cols_by_table[tbl][col] = {
                        "data_type": dtype,
                        "nullable": nullable,
                        "default": col_def,
                        "auto_increment": "auto_increment" in extra,
                    }
            conn.close()
        except Exception:
            pass
        return cols_by_table

    def generate_sql_dump(self) -> Path:
        """
        Gera o arquivo dump_idsecure_mysql.sql pronto para execução via Workbench,
        HeidiSQL ou comando 'mysql -u root -p idsecure < dump_idsecure_mysql.sql'.
        """
        dump_file = self.output_dir / "dump_idsecure_mysql.sql"

        lines = [
            "-- =============================================================",
            "-- SCRIPT DE RESTAURAÇÃO PARA MYSQL DO IDSECURE",
            f"-- Gerado pelo Bot Backup Catraca em: {time.strftime('%Y-%m-%d %H:%M:%S')}",
            "-- Compatível com iDSecure Lite / Pro / Enterprise",
            "-- =============================================================",
            "",
            "SET FOREIGN_KEY_CHECKS = 0;",
            "SET SQL_MODE = 'NO_AUTO_VALUE_ON_ZERO';",
            "",
            "-- Criação condicional das tabelas principais caso o banco esteja limpo",
            """
            CREATE TABLE IF NOT EXISTS `Users` (
              `id` bigint(20) NOT NULL,
              `idDevice` int(11) NOT NULL,
              `name` varchar(255) COLLATE utf8mb4_unicode_ci NOT NULL,
              `registration` varchar(100) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
              `password` varchar(255) COLLATE utf8mb4_unicode_ci DEFAULT '',
              `salt` varchar(255) COLLATE utf8mb4_unicode_ci DEFAULT '',
              `inativo` tinyint(1) DEFAULT 0,
              `contingency` tinyint(1) DEFAULT 1,
              `deleted` tinyint(1) DEFAULT 0,
              `idType` tinyint(1) DEFAULT 0,
              `timeOfRegistration` bigint(20) DEFAULT 0,
              PRIMARY KEY (`id`),
              KEY `idx_users_iddevice` (`idDevice`)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
            """,
            """
            CREATE TABLE IF NOT EXISTS `Cards` (
              `id` bigint(20) NOT NULL,
              `id_user` bigint(20) NOT NULL,
              `code` bigint(20) DEFAULT NULL,
              `value` varchar(100) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
              `type` int(11) DEFAULT 1,
              PRIMARY KEY (`id`),
              KEY `idx_cards_user` (`id_user`)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
            """,
            """
            CREATE TABLE IF NOT EXISTS `Groups` (
              `id` int(11) NOT NULL,
              `name` varchar(255) COLLATE utf8mb4_unicode_ci NOT NULL,
              `idType` int(11) DEFAULT 1,
              PRIMARY KEY (`id`)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
            """,
            """
            CREATE TABLE IF NOT EXISTS `UserGroups` (
              `id` bigint(20) NOT NULL AUTO_INCREMENT,
              `idUser` bigint(20) NOT NULL,
              `idGroup` int(11) NOT NULL,
              PRIMARY KEY (`id`),
              UNIQUE KEY `idx_user_group` (`idUser`, `idGroup`)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
            """,
            """
            CREATE TABLE IF NOT EXISTS `Devices` (
              `id` int(11) NOT NULL AUTO_INCREMENT,
              `name` varchar(255) COLLATE utf8mb4_unicode_ci NOT NULL,
              `ip` varchar(50) COLLATE utf8mb4_unicode_ci NOT NULL,
              `serial` varchar(100) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
              `model` varchar(100) COLLATE utf8mb4_unicode_ci DEFAULT 'iDFace',
              PRIMARY KEY (`id`),
              UNIQUE KEY `idx_device_serial` (`serial`)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
            """,
            "",
            "-- INSERÇÃO DOS DADOS CONSOLIDADOS",
            "",
        ]

        with self.storage._get_connection() as conn:
            # 1. Users
            users = conn.execute("SELECT * FROM users").fetchall()
            for u in users:
                u_id = u["id"]
                reg = f"'{self._escape_sql(u['registration'])}'" if u["registration"] else "NULL"
                name = f"'{self._escape_sql(u['name'])}'"
                pwd = f"'{self._escape_sql(u['password'])}'"
                salt = f"'{self._escape_sql(u['salt'])}'"
                u_type = int(u["user_type_id"] or 0)
                ts_reg = int(u["begin_time"] or time.time())

                lines.append(
                    f"INSERT INTO `Users` (`id`, `idDevice`, `name`, `registration`, `password`, `salt`, `inativo`, `contingency`, `deleted`, `idType`, `timeOfRegistration`) "
                    f"VALUES ({u_id}, {u_id}, {name}, {reg}, {pwd}, {salt}, 0, 1, 0, {u_type}, {ts_reg}) "
                    f"ON DUPLICATE KEY UPDATE `name`={name}, `registration`={reg}, `idDevice`={u_id}, `contingency`=1;"
                )

            # 2. Cards
            cards = conn.execute("SELECT * FROM cards").fetchall()
            for c in cards:
                c_id = c["id"]
                u_id = c["user_id"]
                c_val = str(c["value"])
                # Se for número
                code_val = c_val if c_val.isdigit() else "0"
                c_type = int(c["type"] or 1)
                lines.append(
                    f"INSERT INTO `Cards` (`id`, `id_user`, `code`, `value`, `type`) "
                    f"VALUES ({c_id}, {u_id}, {code_val}, '{self._escape_sql(c_val)}', {c_type}) "
                    f"ON DUPLICATE KEY UPDATE `code`={code_val}, `value`='{self._escape_sql(c_val)}';"
                )

            # 3. Groups
            groups = conn.execute("SELECT * FROM groups").fetchall()
            for g in groups:
                g_id = g["id"]
                g_name = f"'{self._escape_sql(g['name'])}'"
                lines.append(
                    f"INSERT INTO `Groups` (`id`, `name`, `idType`) "
                    f"VALUES ({g_id}, {g_name}, 1) "
                    f"ON DUPLICATE KEY UPDATE `name`={g_name};"
                )

            # 4. UserGroups
            user_groups = conn.execute("SELECT * FROM user_groups").fetchall()
            for ug in user_groups:
                lines.append(
                    f"INSERT IGNORE INTO `UserGroups` (`idUser`, `idGroup`) "
                    f"VALUES ({ug['user_id']}, {ug['group_id']});"
                )

            # 5. Devices
            devices = conn.execute("SELECT * FROM source_devices").fetchall()
            for d in devices:
                lines.append(
                    f"INSERT INTO `Devices` (`name`, `ip`, `serial`, `model`) "
                    f"VALUES ('{self._escape_sql(d['model'])} - {self._escape_sql(d['ip'])}', '{self._escape_sql(d['ip'])}', '{self._escape_sql(d['serial'])}', '{self._escape_sql(d['model'])}') "
                    f"ON DUPLICATE KEY UPDATE `ip`='{self._escape_sql(d['ip'])}', `model`='{self._escape_sql(d['model'])}';"
                )

        lines.extend([
            "",
            "SET FOREIGN_KEY_CHECKS = 1;",
            "-- FIM DO SCRIPT",
        ])

        with open(dump_file, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))

        return dump_file

    def restore_direct_mysql(
        self,
        config: MySQLConnectionConfig,
        on_log: Optional[callable] = None,
        on_progress: Optional[callable] = None,
    ) -> Tuple[bool, str]:
        """Injeta dados diretamente no MySQL usando PyMySQL com controle de transação e schema dinâmico."""
        from backend.core.logger import logger, add_backup_folder_logger

        add_backup_folder_logger(str(self.output_dir))

        if pymysql is None:
            err = "Driver PyMySQL não instalado."
            logger.error(err)
            return False, err

        def log(msg: str):
            logger.info(msg)
            if on_log:
                on_log(msg)

        def report_prog(current: int, total: int, step_desc: str):
            if on_progress:
                on_progress(current, total, step_desc)

        try:
            log("Conectando ao servidor MySQL...")
            report_prog(0, 100, "Conectando ao MySQL...")
            conn = pymysql.connect(
                host=config.host,
                port=config.port,
                user=config.user,
                password=config.password,
                database=config.database,
                charset=config.charset,
                connect_timeout=config.connect_timeout,
                cursorclass=pymysql.cursors.DictCursor,
                autocommit=False,
            )

            # Inspeciona schema existente na base de dados conectada
            log("Inspecionando colunas existentes nas tabelas do banco...")
            existing_cols = self.get_existing_table_columns(config)

            with conn.cursor() as cursor:
                cursor.execute("SET FOREIGN_KEY_CHECKS = 0;")

                # Garante tabelas básicas caso o banco esteja completamente vazio
                self._ensure_tables_if_needed(cursor)
                # Re-lê colunas após criação preventiva
                existing_cols = self.get_existing_table_columns(config)

                with self.storage._get_connection() as s_conn:
                    users = s_conn.execute("SELECT * FROM users").fetchall()
                    cards = s_conn.execute("SELECT * FROM cards").fetchall()
                    groups = s_conn.execute("SELECT * FROM groups").fetchall()
                    user_groups = s_conn.execute("SELECT * FROM user_groups").fetchall()
                    devices = s_conn.execute("SELECT * FROM source_devices").fetchall()

                    total_operations = len(users) + len(cards) + len(groups) + len(user_groups) + len(devices)
                    if total_operations == 0:
                        total_operations = 1
                    completed_ops = 0

                    def apply_not_null_defaults(fields_dict: Dict[str, Any], meta_dict: Dict[str, Dict[str, Any]]):
                        if not meta_dict:
                            return
                        for c_name, meta in meta_dict.items():
                            if c_name in fields_dict or meta.get("auto_increment"):
                                continue
                            if not meta.get("nullable") and meta.get("default") is None:
                                dt = meta.get("data_type", "")
                                if "int" in dt or "decimal" in dt or "float" in dt or "double" in dt:
                                    fields_dict[c_name] = 0
                                elif "date" in dt or "time" in dt:
                                    fields_dict[c_name] = time.strftime("%Y-%m-%d %H:%M:%S")
                                else:
                                    fields_dict[c_name] = ""

                    # 1. Injeta Users de forma dinâmica
                    cols_users = existing_cols.get("users", {})
                    log(f"Injetando {len(users)} usuários na tabela Users...")
                    for u in users:
                        user_fields: Dict[str, Any] = {}
                        u_id = u["id"]
                        
                        # Mapeamento com checagem de existência real na tabela Users do iDSecure
                        if not cols_users or "id" in cols_users:
                            user_fields["id"] = u_id
                        if not cols_users or "iddevice" in cols_users:
                            user_fields["iddevice"] = u_id
                        if not cols_users or "name" in cols_users:
                            user_fields["name"] = u["name"] or ""
                        if not cols_users or "registration" in cols_users:
                            user_fields["registration"] = u["registration"] or None
                        if cols_users and "password" in cols_users:
                            user_fields["password"] = u["password"] or ""
                        if cols_users and "salt" in cols_users:
                            user_fields["salt"] = u["salt"] or ""
                        if cols_users and "inativo" in cols_users:
                            user_fields["inativo"] = 0
                        if cols_users and "contingency" in cols_users:
                            user_fields["contingency"] = 1
                        if cols_users and "deleted" in cols_users:
                            user_fields["deleted"] = 0
                        if cols_users and "idtype" in cols_users:
                            user_fields["idtype"] = u["user_type_id"] or 0
                        
                        if cols_users and "timeofregistration" in cols_users:
                            raw_ts = u["begin_time"]
                            col_dtype = cols_users["timeofregistration"].get("data_type", "").lower()
                            
                            # Trata timestamp Unix
                            try:
                                ts_int = int(raw_ts) if raw_ts else int(time.time())
                                if ts_int <= 0:
                                    ts_int = int(time.time())
                            except Exception:
                                ts_int = int(time.time())

                            # Converte conforme tipo da coluna no MySQL
                            if "date" in col_dtype or "time" in col_dtype:
                                try:
                                    user_fields["timeofregistration"] = time.strftime(
                                        "%Y-%m-%d %H:%M:%S", time.localtime(ts_int)
                                    )
                                except Exception:
                                    user_fields["timeofregistration"] = time.strftime("%Y-%m-%d %H:%M:%S")
                            else:
                                user_fields["timeofregistration"] = ts_int

                        # Preenche automaticamente qualquer coluna NOT NULL que o iDSecure exija (ex: pis, etc.)
                        apply_not_null_defaults(user_fields, cols_users)

                        if user_fields:
                            col_names = [f"`{col}`" for col in user_fields.keys()]
                            placeholders = ["%s"] * len(user_fields)
                            val_list = list(user_fields.values())

                            update_cols = [c for c in user_fields.keys() if c.lower() != "id"]
                            update_clauses = [f"`{c}`=VALUES(`{c}`)" for c in update_cols]
                            update_str = ", ".join(update_clauses) if update_clauses else f"`id`=VALUES(`id`)"

                            sql = f"INSERT INTO `Users` ({', '.join(col_names)}) VALUES ({', '.join(placeholders)}) ON DUPLICATE KEY UPDATE {update_str};"
                            cursor.execute(sql, val_list)

                        completed_ops += 1
                        if completed_ops % 50 == 0 or completed_ops == len(users):
                            report_prog(completed_ops, total_operations, f"Usuários: {completed_ops}/{len(users)}")

                    # 2. Injeta Cards de forma dinâmica
                    cols_cards = existing_cols.get("cards", {})
                    log(f"Injetando {len(cards)} cartões na tabela Cards...")
                    for c in cards:
                        c_fields: Dict[str, Any] = {}
                        val_str = str(c["value"])
                        code_num = int(val_str) if val_str.isdigit() else 0

                        if not cols_cards or "id" in cols_cards:
                            c_fields["id"] = c["id"]
                        if not cols_cards or "id_user" in cols_cards:
                            c_fields["id_user"] = c["user_id"]
                        elif "iduser" in cols_cards:
                            c_fields["iduser"] = c["user_id"]
                        if not cols_cards or "code" in cols_cards:
                            c_fields["code"] = code_num
                        if not cols_cards or "value" in cols_cards:
                            c_fields["value"] = val_str
                        if not cols_cards or "type" in cols_cards:
                            c_fields["type"] = c["type"] or 1

                        apply_not_null_defaults(c_fields, cols_cards)

                        if c_fields:
                            col_names = [f"`{col}`" for col in c_fields.keys()]
                            placeholders = ["%s"] * len(c_fields)
                            val_list = list(c_fields.values())
                            update_cols = [col for col in c_fields.keys() if col.lower() != "id"]
                            update_clauses = [f"`{col}`=VALUES(`{col}`)" for col in update_cols]
                            update_str = ", ".join(update_clauses) if update_clauses else f"`id`=VALUES(`id`)"

                            sql = f"INSERT INTO `Cards` ({', '.join(col_names)}) VALUES ({', '.join(placeholders)}) ON DUPLICATE KEY UPDATE {update_str};"
                            cursor.execute(sql, val_list)

                        completed_ops += 1
                        if completed_ops % 50 == 0 or completed_ops == (len(users) + len(cards)):
                            report_prog(completed_ops, total_operations, f"Cartões: {completed_ops - len(users)}/{len(cards)}")

                    # 3. Injeta Groups
                    cols_groups = existing_cols.get("groups", {})
                    log(f"Injetando {len(groups)} grupos na tabela Groups...")
                    for g in groups:
                        g_fields: Dict[str, Any] = {}
                        if not cols_groups or "id" in cols_groups:
                            g_fields["id"] = g["id"]
                        if not cols_groups or "name" in cols_groups:
                            g_fields["name"] = g["name"]
                        if cols_groups and "idtype" in cols_groups:
                            g_fields["idtype"] = 1

                        apply_not_null_defaults(g_fields, cols_groups)

                        if g_fields:
                            col_names = [f"`{col}`" for col in g_fields.keys()]
                            placeholders = ["%s"] * len(g_fields)
                            val_list = list(g_fields.values())
                            update_cols = [col for col in g_fields.keys() if col.lower() != "id"]
                            update_clauses = [f"`{col}`=VALUES(`{col}`)" for col in update_cols]
                            update_str = ", ".join(update_clauses) if update_clauses else f"`id`=VALUES(`id`)"

                            sql = f"INSERT INTO `Groups` ({', '.join(col_names)}) VALUES ({', '.join(placeholders)}) ON DUPLICATE KEY UPDATE {update_str};"
                            cursor.execute(sql, val_list)

                        completed_ops += 1
                        report_prog(completed_ops, total_operations, f"Grupos: {len(groups)} processados")

                    # 4. Injeta UserGroups
                    cols_ug = existing_cols.get("usergroups", {})
                    log(f"Injetando {len(user_groups)} vínculos na tabela UserGroups...")
                    for ug in user_groups:
                        ug_fields: Dict[str, Any] = {}
                        if not cols_ug or "iduser" in cols_ug:
                            ug_fields["iduser"] = ug["user_id"]
                        elif "id_user" in cols_ug:
                            ug_fields["id_user"] = ug["user_id"]

                        if not cols_ug or "idgroup" in cols_ug:
                            ug_fields["idgroup"] = ug["group_id"]
                        elif "id_group" in cols_ug:
                            ug_fields["id_group"] = ug["group_id"]

                        apply_not_null_defaults(ug_fields, cols_ug)

                        if ug_fields:
                            col_names = [f"`{col}`" for col in ug_fields.keys()]
                            placeholders = ["%s"] * len(ug_fields)
                            val_list = list(ug_fields.values())
                            sql = f"INSERT IGNORE INTO `UserGroups` ({', '.join(col_names)}) VALUES ({', '.join(placeholders)});"
                            cursor.execute(sql, val_list)

                        completed_ops += 1
                        if completed_ops % 50 == 0:
                            report_prog(completed_ops, total_operations, "Vinculando usuários a grupos...")

                    # 5. Injeta Devices
                    cols_dev = existing_cols.get("devices", {})
                    log(f"Injetando {len(devices)} dispositivos na tabela Devices...")
                    for d in devices:
                        d_fields: Dict[str, Any] = {}
                        if not cols_dev or "name" in cols_dev:
                            d_fields["name"] = f"{d['model']} - {d['ip']}"
                        if not cols_dev or "ip" in cols_dev:
                            d_fields["ip"] = d["ip"]
                        if not cols_dev or "serial" in cols_dev:
                            d_fields["serial"] = d["serial"]
                        if not cols_dev or "model" in cols_dev:
                            model_meta = cols_dev.get("model", {})
                            model_dtype = model_meta.get("data_type", "").lower()
                            # No iDSecure, se 'model' for tipo inteiro, mapeia código enum (ex: iDFace = 15 ou 1)
                            if "int" in model_dtype or "decimal" in model_dtype:
                                # Dicionário de modelos Control iD para IDs de equipamento no iDSecure
                                model_str = (d["model"] or "").lower()
                                if "face" in model_str:
                                    d_fields["model"] = 15  # iDFace padrão no iDSecure
                                elif "access" in model_str:
                                    d_fields["model"] = 1
                                elif "box" in model_str:
                                    d_fields["model"] = 3
                                elif "fit" in model_str:
                                    d_fields["model"] = 5
                                else:
                                    d_fields["model"] = 1
                            else:
                                d_fields["model"] = d["model"]

                        apply_not_null_defaults(d_fields, cols_dev)

                        if d_fields:
                            col_names = [f"`{col}`" for col in d_fields.keys()]
                            placeholders = ["%s"] * len(d_fields)
                            val_list = list(d_fields.values())
                            update_cols = [col for col in d_fields.keys() if col.lower() != "id"]
                            update_clauses = [f"`{col}`=VALUES(`{col}`)" for col in update_cols]
                            update_str = ", ".join(update_clauses) if update_clauses else f"`ip`=VALUES(`ip`)"

                            sql = f"INSERT INTO `Devices` ({', '.join(col_names)}) VALUES ({', '.join(placeholders)}) ON DUPLICATE KEY UPDATE {update_str};"
                            cursor.execute(sql, val_list)

                        completed_ops += 1
                        report_prog(completed_ops, total_operations, "Dispositivos restaurados...")

                cursor.execute("SET FOREIGN_KEY_CHECKS = 1;")
                conn.commit()

            conn.close()
            report_prog(total_operations, total_operations, "Concluído com 100% de sucesso!")
            msg = "Injeção direta no MySQL do iDSecure concluída com sucesso!"
            log(msg)
            return True, msg

        except Exception as e:
            err = f"Erro durante injeção no MySQL: {str(e)}"
            log(err)
            logger.exception("Exceção detalhada na injeção MySQL:")
            return False, err

    def _ensure_tables_if_needed(self, cursor):
        """Cria tabelas mínimas se o banco estiver vazio."""
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS `Users` (
              `id` bigint(20) NOT NULL,
              `idDevice` int(11) NOT NULL,
              `name` varchar(255) COLLATE utf8mb4_unicode_ci NOT NULL,
              `registration` varchar(100) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
              `password` varchar(255) COLLATE utf8mb4_unicode_ci DEFAULT '',
              `salt` varchar(255) COLLATE utf8mb4_unicode_ci DEFAULT '',
              `inativo` tinyint(1) DEFAULT 0,
              `contingency` tinyint(1) DEFAULT 1,
              `deleted` tinyint(1) DEFAULT 0,
              `idType` tinyint(1) DEFAULT 0,
              `timeOfRegistration` bigint(20) DEFAULT 0,
              PRIMARY KEY (`id`),
              KEY `idx_users_iddevice` (`idDevice`)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS `Cards` (
              `id` bigint(20) NOT NULL,
              `id_user` bigint(20) NOT NULL,
              `code` bigint(20) DEFAULT NULL,
              `value` varchar(100) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
              `type` int(11) DEFAULT 1,
              PRIMARY KEY (`id`),
              KEY `idx_cards_user` (`id_user`)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS `Groups` (
              `id` int(11) NOT NULL,
              `name` varchar(255) COLLATE utf8mb4_unicode_ci NOT NULL,
              `idType` int(11) DEFAULT 1,
              PRIMARY KEY (`id`)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS `UserGroups` (
              `id` bigint(20) NOT NULL AUTO_INCREMENT,
              `idUser` bigint(20) NOT NULL,
              `idGroup` int(11) NOT NULL,
              PRIMARY KEY (`id`),
              UNIQUE KEY `idx_user_group` (`idUser`, `idGroup`)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS `Devices` (
              `id` int(11) NOT NULL AUTO_INCREMENT,
              `name` varchar(255) COLLATE utf8mb4_unicode_ci NOT NULL,
              `ip` varchar(50) COLLATE utf8mb4_unicode_ci NOT NULL,
              `serial` varchar(100) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
              `model` varchar(100) COLLATE utf8mb4_unicode_ci DEFAULT 'iDFace',
              PRIMARY KEY (`id`),
              UNIQUE KEY `idx_device_serial` (`serial`)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
        """)

    @staticmethod
    def _escape_sql(val: Optional[str]) -> str:
        if val is None:
            return ""
        return str(val).replace("\\", "\\\\").replace("'", "''")
