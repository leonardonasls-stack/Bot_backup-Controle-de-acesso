"""
Testes unitários para MySQLIDSecureService (geração do dump SQL do iDSecure)
e IDSecureAPIRestorer (geração do ZIP de importação).
"""

from pathlib import Path
import tempfile
import zipfile
import pytest
from backend.services.sqlite_storage import SQLiteStorage
from backend.services.mysql_idsecure_service import MySQLIDSecureService
from backend.services.idsecure_api_restorer import IDSecureAPIRestorer


def test_mysql_dump_generation():
    with tempfile.TemporaryDirectory() as tmp_dir:
        db_path = Path(tmp_dir) / "test.sqlite"
        storage = SQLiteStorage(str(db_path))

        # Adiciona dados no SQLite
        with storage._get_connection() as conn:
            conn.execute("INSERT INTO users (id, name, registration) VALUES (1, 'FERNANDO', 'F123')")
            conn.execute("INSERT INTO cards (id, user_id, value, type) VALUES (10, 1, '998877', 1)")
            conn.commit()

        mysql_svc = MySQLIDSecureService(storage, tmp_dir)
        dump_file = mysql_svc.generate_sql_dump()

        assert dump_file.exists()
        content = dump_file.read_text(encoding="utf-8")
        assert "INSERT INTO `Users`" in content
        assert "FERNANDO" in content
        assert "INSERT INTO `Cards`" in content
        assert "998877" in content


def test_idsecure_zip_generation():
    with tempfile.TemporaryDirectory() as tmp_dir:
        db_path = Path(tmp_dir) / "test.sqlite"
        storage = SQLiteStorage(str(db_path))

        # Cria foto de teste
        faces_dir = Path(tmp_dir) / "faces"
        faces_dir.mkdir(parents=True, exist_ok=True)
        sample_face = faces_dir / "1_F123_FERNANDO.jpg"
        sample_face.write_bytes(b"\xff\xd8\xff\xe0mockjpeg\xff\xd9")

        with storage._get_connection() as conn:
            conn.execute("INSERT INTO users (id, name, registration) VALUES (1, 'FERNANDO', 'F123')")
            conn.execute(
                "INSERT INTO user_images (user_id, file_path, status) VALUES (1, ?, 'DOWNLOADED')",
                (str(sample_face),),
            )
            conn.commit()

        api_restorer = IDSecureAPIRestorer(storage, tmp_dir)
        zip_file = api_restorer.generate_import_zip()

        assert zip_file.exists()
        with zipfile.ZipFile(zip_file, "r") as z:
            names = z.namelist()
            assert "usuarios.csv" in names
            assert "fotos/1_F123_FERNANDO.jpg" in names
