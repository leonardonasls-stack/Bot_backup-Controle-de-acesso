"""
Testes unitários para IDFaceClient e detecção de equipamentos Control iD.
"""

import pytest
from backend.models.device import ControlIdDevice
from backend.core.idface_client import IDFaceClient
from tests.mock_idface_server import run_mock_server


@pytest.fixture(scope="module")
def mock_server():
    server = run_mock_server(port=18081)
    yield server
    server.shutdown()


@pytest.mark.asyncio
async def test_client_login_and_info(mock_server):
    dev = ControlIdDevice(ip="127.0.0.1", port=18081)
    client = IDFaceClient(dev, login_user="admin", login_password="admin")

    session = await client.login()
    assert session == "mock_session_12345"
    assert dev.is_authenticated is True

    info = await client.get_system_information()
    assert info["serial"] == "0K00012345"
    assert dev.serial == "0K00012345"

    await client.close()


@pytest.mark.asyncio
async def test_client_load_objects_and_faces(mock_server):
    dev = ControlIdDevice(ip="127.0.0.1", port=18081)
    client = IDFaceClient(dev, login_user="admin", login_password="admin")

    users = await client.load_all_objects("users")
    assert len(users) == 2
    assert users[0]["name"] == "CARLOS SILVA"

    faces = await client.list_user_images()
    assert len(faces) == 2

    img_bytes = await client.download_user_image(1)
    assert img_bytes is not None
    assert len(img_bytes) > 100

    await client.close()
