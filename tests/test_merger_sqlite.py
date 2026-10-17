"""
Testes unitários para SQLiteStorage e DataMerger.
"""

from pathlib import Path
import tempfile
import pytest
from backend.services.sqlite_storage import SQLiteStorage
from backend.core.merger import DataMerger


def test_sqlite_storage_and_checkpoints():
    with tempfile.TemporaryDirectory() as tmp_dir:
        db_path = Path(tmp_dir) / "test.sqlite"
        storage = SQLiteStorage(str(db_path))

        storage.register_device("SERIAL_1", "192.168.1.101", 80, "iDFace")
        assert len(storage.get_downloaded_face_ids()) == 0

        # Registra foto baixada
        storage.register_user_image(user_id=1, timestamp=1710000000, status="DOWNLOADED", file_size=500)
        assert 1 in storage.get_downloaded_face_ids()
        assert storage.get_face_timestamp(1) == 1710000000


def test_merger_best_record_and_conflict():
    with tempfile.TemporaryDirectory() as tmp_dir:
        db_path = Path(tmp_dir) / "test.sqlite"
        storage = SQLiteStorage(str(db_path))
        merger = DataMerger(storage)

        # Catraca 1: Usuário 1 sem matrícula
        merger.merge_users("DEV_1", [{"id": 1, "name": "JOAO SILVA", "registration": "", "image_timestamp": 100}])
        
        # Catraca 2: Mesmo Usuário 1 com matrícula preenchida e foto mais recente
        merger.merge_users("DEV_2", [{"id": 1, "name": "JOAO SILVA", "registration": "MAT-99", "image_timestamp": 200}])

        with storage._get_connection() as conn:
            user = conn.execute("SELECT * FROM users WHERE id = 1").fetchone()
            assert user["registration"] == "MAT-99"
            assert user["image_timestamp"] == 200

        # Catraca 3: Mesmo Usuário 1 com nome diferente -> Gera Conflito
        merger.merge_users("DEV_3", [{"id": 1, "name": "JOAO CARLOS SILVA", "registration": "MAT-99"}])
        assert len(merger.conflicts) == 1
        assert merger.conflicts[0]["type"] == "USER_NAME_CONFLICT"
