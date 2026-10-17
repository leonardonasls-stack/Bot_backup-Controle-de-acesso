"""
Detector de equipamentos Control iD (iDFace, iDBox, iDAccess, etc.).
Valida portas HTTP/HTTPS e faz fingerprint inicial leve via API .fcgi.
"""

import asyncio
from typing import Optional, Dict, Any
import httpx

from backend.models.device import ControlIdDevice


async def check_tcp_port(ip: str, port: int = 80, timeout: float = 1.0) -> bool:
    """Verificação TCP rápida para checar se a porta do serviço está aberta."""
    try:
        _, writer = await asyncio.wait_for(
            asyncio.open_connection(ip, port), timeout=timeout
        )
        writer.close()
        await writer.wait_closed()
        return True
    except Exception:
        return False


async def probe_controlid_device(
    ip: str, port: int = 80, timeout: float = 2.0
) -> Optional[ControlIdDevice]:
    """
    Testa se o IP corresponde a um equipamento Control iD respondendo à API .fcgi.
    Tenta uma requisição leve em endpoints públicos ou session_is_valid.fcgi.
    """
    scheme = "https" if port == 443 else "http"
    base_url = f"{scheme}://{ip}:{port}" if port not in (80, 443) else f"{scheme}://{ip}"

    # 1. Quick TCP check
    port_open = await check_tcp_port(ip, port, timeout=1.0)
    if not port_open:
        return None

    # 2. HTTP probe
    device = ControlIdDevice(ip=ip, port=port, is_online=True)

    transport = httpx.AsyncHTTPTransport(verify=False)
    async with httpx.AsyncClient(transport=transport, timeout=timeout) as client:
        try:
            # Tenta session_is_valid.fcgi com token vazio para checar se o servidor é Control iD
            # Terminais Control iD retornam HTTP 200 {"session_is_valid": false} ou HTTP 400
            resp = await client.post(
                f"{base_url}/session_is_valid.fcgi",
                json={},
                headers={"Content-Type": "application/json"},
            )

            # Verifica se o servidor retornou resposta JSON típica de Control iD
            if resp.status_code in (200, 400, 401):
                try:
                    data = resp.json()
                    if isinstance(data, dict) and ("session_is_valid" in data or "error" in data or resp.status_code == 200):
                        return device
                except Exception:
                    pass

            # Fallback: Tenta system_information.fcgi sem sessão (algumas versões retornam erro de auth estruturado)
            resp_info = await client.post(
                f"{base_url}/system_information.fcgi",
                json={},
                headers={"Content-Type": "application/json"},
            )
            if resp_info.status_code in (200, 400, 401, 403):
                return device

        except Exception:
            return None

    return None
