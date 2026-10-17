"""
Servidor Mock HTTP assíncrono para simular catracas iDFace da Control iD em testes automatizados.
Suporta login.fcgi, session_is_valid.fcgi, system_information.fcgi, load_objects.fcgi,
user_list_images.fcgi e user_get_image.fcgi.
"""

import asyncio
from http.server import HTTPServer, BaseHTTPRequestHandler
import json
import threading
import urllib.parse


# Imagem JPEG mínima de 1x1 pixel válida (631 bytes)
MOCK_JPEG_BYTES = (
    b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x01\x00`\x00`\x00\x00\xff\xdb\x00C\x00\x08\x06\x06\x07\x06\x05\x08"
    b"\x07\x07\x07\t\t\x08\n\x0c\x14\r\x0c\x0b\x0b\x0c\x19\x12\x13\x0f\x14\x1d\x1a\x1f\x1e\x1d\x1a\x1c\x1c $.' \",#\x1c"
    b"\x1c(7),01444\x1f'9=82<.342\xff\xc0\x00\x0b\x08\x00\x01\x00\x01\x01\x01\x11\x00\xff\xc4\x00\x1f\x00\x00\x01\x05"
    b"\x01\x01\x01\x01\x01\x01\x00\x00\x00\x00\x00\x00\x00\x00\x01\x02\x03\x04\x05\x06\x07\x08\t\n\x0b\xff\xda\x00\x08"
    b"\x01\x01\x00\x00?\x00\xbf\x00\xff\xd9" * 4
)


class MockIDFaceHandler(BaseHTTPRequestHandler):
    """Handler HTTP simulando endpoints .fcgi."""

    mock_serial = "0K00012345"
    mock_users = [
        {"id": 1, "registration": "1001", "name": "CARLOS SILVA", "password": "", "salt": "", "user_type_id": 0, "image_timestamp": 1710000000, "begin_time": 1710000000},
        {"id": 2, "registration": "1002", "name": "MARIA SOUZA", "password": "", "salt": "", "user_type_id": 0, "image_timestamp": 1710000500, "begin_time": 1710000000},
    ]
    mock_cards = [
        {"id": 10, "value": "42949673960", "user_id": 1, "type": 1},
        {"id": 11, "value": "12345678", "user_id": 2, "type": 0},
    ]
    mock_groups = [{"id": 1, "name": "Administração"}]
    mock_user_groups = [{"user_id": 1, "group_id": 1}, {"user_id": 2, "group_id": 1}]
    mock_rules = [{"id": 1, "name": "Acesso Livre", "type": 1, "priority": 0}]

    def _send_json(self, status: int, data: dict):
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(data).encode("utf-8"))

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        length = int(self.headers.get("content-length", 0))
        body = self.rfile.read(length)
        payload = json.loads(body.decode("utf-8")) if body else {}

        if path == "/login.fcgi":
            if payload.get("login") == "admin" and payload.get("password") == "admin":
                self._send_json(200, {"session": "mock_session_12345"})
            else:
                self._send_json(401, {"error": "Invalid login or password"})

        elif path == "/session_is_valid.fcgi":
            self._send_json(200, {"session_is_valid": True})

        elif path == "/system_information.fcgi":
            self._send_json(200, {
                "serial": self.mock_serial,
                "version": "6.14.2",
                "device_model": "iDFace",
            })

        elif path == "/load_objects.fcgi":
            obj = payload.get("object")
            limit = payload.get("limit", 500)
            offset = payload.get("offset", 0)

            data_map = {
                "users": self.mock_users,
                "cards": self.mock_cards,
                "groups": self.mock_groups,
                "user_groups": self.mock_user_groups,
                "access_rules": self.mock_rules,
                "time_zones": [{"id": 1, "name": "Comercial"}],
                "time_spans": [{"id": 1, "time_zone_id": 1, "start": 28800, "end": 64800, "mon": 1}],
            }
            items = data_map.get(obj, [])
            paged = items[offset : offset + limit]
            self._send_json(200, {obj: paged})

        elif path == "/user_list_images.fcgi":
            self._send_json(200, {
                "user_images": [
                    {"user_id": 1, "timestamp": 1710000000},
                    {"user_id": 2, "timestamp": 1710000500},
                ]
            })

        else:
            self._send_json(404, {"error": "Endpoint not found"})

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        qs = urllib.parse.parse_qs(parsed.query)

        if path == "/user_get_image.fcgi":
            user_id = qs.get("user_id", [""])[0]
            if user_id in ("1", "2"):
                self.send_response(200)
                self.send_header("Content-Type", "image/jpeg")
                self.send_header("Content-Length", str(len(MOCK_JPEG_BYTES)))
                self.end_headers()
                self.wfile.write(MOCK_JPEG_BYTES)
            else:
                self.send_response(404)
                self.end_headers()
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format, *args):
        # Silencia logs no terminal durante execução de testes
        pass


def run_mock_server(port: int = 18080) -> HTTPServer:
    """Inicia o servidor Mock em background thread."""
    server = HTTPServer(("127.0.0.1", port), MockIDFaceHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server
