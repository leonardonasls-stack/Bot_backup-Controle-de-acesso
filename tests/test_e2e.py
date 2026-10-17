"""
Teste End-to-End (E2E) simulando extração completa de catracas Control iD
e geração dos artefatos de restauração para o iDSecure.
"""

from pathlib import Path
import tempfile
import pytest
from backend.models.device import ControlIdDevice
from backend.core.extractor import BackupExtractor
from backend.services.exporter_service import ExporterService
from backend.services.mysql_idsecure_service import MySQLIDSecureService
from backend.services.idsecure_api_restorer import IDSecureAPIRestorer
from tests.mock_idface_server import run_mock_server


@pytest.fixture(scope="module")
def mock_server():
    server = run_mock_server(port=18082)
    yield server
    server.shutdown()


@pytest.mark.asyncio
async def test_full_e2e_pipeline(mock_server):
    with tempfile.TemporaryDirectory() as tmp_dir:
        dev = ControlIdDevice(ip="127.0.0.1", port=18082, selected_for_backup=True)

        # 1. Extração
        extractor = BackupExtractor([dev], output_dir=tmp_dir)
        report = await extractor.run()

        assert report.devices_backed_up == 1
        assert report.total_users_consolidated == 2
        assert report.total_cards_consolidated == 2
        assert report.total_faces_downloaded == 2

        # 2. Exporte JSON
        exporter = ExporterService(extractor.storage, tmp_dir)
        json_file = exporter.export_full_json()
        assert json_file.exists()

        audit_file = exporter.export_audit_report(report)
        assert audit_file.exists()

        # 3. Geração de SQL Dump iDSecure
        mysql_svc = MySQLIDSecureService(extractor.storage, tmp_dir)
        dump_file = mysql_svc.generate_sql_dump()
        assert dump_file.exists()
        assert "CARLOS SILVA" in dump_file.read_text(encoding="utf-8")

        # 4. Geração do Pacote ZIP de Importação
        api_restorer = IDSecureAPIRestorer(extractor.storage, tmp_dir)
        zip_file = api_restorer.generate_import_zip()
        assert zip_file.exists()
