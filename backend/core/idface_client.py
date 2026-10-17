"""
Cliente HTTP assíncrono para a API .fcgi dos terminais Control iD (iDFace, iDBox, iDAccess).
Inclui gerenciamento automático de sessão, auto-reautenticação, paginação e retries de download de imagens.
"""

import asyncio
from typing import Dict, Any, List, Optional, Tuple
import httpx

from backend.models.device import ControlIdDevice


class IDFaceAPIError(Exception):
    """Exceção levantada em erros de comunicação com a API Control iD."""
    pass


class IDFaceClient:
    """Cliente assíncrono para interagir com a API .fcgi do iDFace."""

    def __init__(
        self,
        device: ControlIdDevice,
        login_user: str = "admin",
        login_password: str = "admin",
        timeout: float = 10.0,
    ):
        self.device = device
        self.login_user = login_user
        self.login_password = login_password
        self.timeout = timeout
        self._session_lock = asyncio.Lock()
        
        # Cliente HTTP com suporte a SSL auto-assinado (portas 443 do iDFace costumam usar cert auto-assinado)
        transport = httpx.AsyncHTTPTransport(verify=False)
        self.client = httpx.AsyncClient(transport=transport, timeout=timeout)

    async def close(self):
        """Fecha as conexões ativas do cliente HTTP."""
        await self.client.aclose()

    async def login(self) -> str:
        """
        Autentica no terminal via POST /login.fcgi e obtém o token de sessão.
        """
        url = f"{self.device.base_url}/login.fcgi"
        payload = {"login": self.login_user, "password": self.login_password}

        try:
            resp = await self.client.post(url, json=payload, headers={"Content-Type": "application/json"})
            if resp.status_code == 200:
                data = resp.json()
                session = data.get("session")
                if session:
                    self.device.session = session
                    self.device.is_authenticated = True
                    self.device.auth_error = None
                    return session
                else:
                    err = "Resposta de login sem token de sessão"
                    self.device.auth_error = err
                    raise IDFaceAPIError(err)
            elif resp.status_code in (401, 403):
                err = "Credenciais inválidas (usuário ou senha incorretos)"
                self.device.auth_error = err
                self.device.is_authenticated = False
                raise IDFaceAPIError(err)
            else:
                err = f"Erro no login: HTTP {resp.status_code} - {resp.text}"
                self.device.auth_error = err
                raise IDFaceAPIError(err)
        except httpx.RequestError as e:
            err = f"Falha de conexão com {self.device.ip}: {str(e)}"
            self.device.auth_error = err
            raise IDFaceAPIError(err)

    async def ensure_session(self) -> str:
        """Garante que há uma sessão válida, efetuando login se necessário."""
        async with self._session_lock:
            if not self.device.session:
                return await self.login()

            # Valida sessão existente
            try:
                val_url = f"{self.device.base_url}/session_is_valid.fcgi?session={self.device.session}"
                resp = await self.client.post(val_url, json={}, headers={"Content-Type": "application/json"})
                if resp.status_code == 200:
                    data = resp.json()
                    if data.get("session_is_valid") is True:
                        return self.device.session
            except Exception:
                pass

            # Se expirou ou falhou, refaz login
            return await self.login()

    async def request_api(
        self,
        endpoint: str,
        method: str = "POST",
        payload: Optional[Dict[str, Any]] = None,
        is_binary: bool = False,
        params: Optional[Dict[str, Any]] = None,
        max_retries: int = 2,
    ) -> Any:
        """
        Executa requisição à API .fcgi com auto-reautenticação em caso de HTTP 401/403.
        """
        if params is None:
            params = {}

        for attempt in range(max_retries + 1):
            session = await self.ensure_session()
            params["session"] = session

            url = f"{self.device.base_url}/{endpoint.lstrip('/')}"
            try:
                if method.upper() == "POST":
                    resp = await self.client.post(
                        url,
                        params=params,
                        json=payload or {},
                        headers={"Content-Type": "application/json"},
                    )
                else:
                    resp = await self.client.get(url, params=params)

                # Se token expirou no meio do caminho
                if resp.status_code in (401, 403) and attempt < max_retries:
                    self.device.session = None
                    continue

                if resp.status_code != 200:
                    raise IDFaceAPIError(f"HTTP {resp.status_code}: {resp.text}")

                if is_binary:
                    return resp.content
                return resp.json()

            except (httpx.RequestError, httpx.HTTPStatusError) as e:
                if attempt == max_retries:
                    raise IDFaceAPIError(f"Falha na requisição {endpoint}: {str(e)}")
                await asyncio.sleep(0.5)

    async def get_system_information(self) -> Dict[str, Any]:
        """Obtém número de série, versão de firmware e modelo."""
        info = await self.request_api("system_information.fcgi")
        self.device.raw_info = info
        self.device.serial = str(info.get("serial", ""))
        self.device.version = str(info.get("version", ""))
        self.device.model = str(info.get("device_model", "iDFace"))
        return info

    async def load_all_objects(
        self, object_name: str, page_size: int = 500
    ) -> List[Dict[str, Any]]:
        """
        Extrai todos os registros de uma tabela/objeto via /load_objects.fcgi com paginação automática.
        """
        items: List[Dict[str, Any]] = []
        offset = 0

        while True:
            payload = {
                "object": object_name,
                "limit": page_size,
                "offset": offset,
            }
            try:
                data = await self.request_api("load_objects.fcgi", payload=payload)
            except IDFaceAPIError as e:
                # Alguns firmwares não têm certas tabelas (ex: qrcodes, pins)
                if "Invalid object" in str(e) or "400" in str(e):
                    break
                raise

            page_items = data.get(object_name, [])
            if not page_items:
                break

            items.extend(page_items)

            if len(page_items) < page_size:
                # Fim dos registros
                break

            offset += len(page_items)

        return items

    async def count_users_and_faces(self) -> Tuple[int, int, int]:
        """
        Pré-diagnóstico rápido de contagem de usuários, fotos faciais e cartões.
        Atualiza o stats do device.
        """
        # 1. Contagem de usuários (limit: 1 apenas para checar o cabeçalho/total ou carregar users)
        users = await self.load_all_objects("users", page_size=500)
        user_count = len(users)

        # 2. Contagem de imagens
        faces_count = 0
        try:
            img_list_resp = await self.request_api(
                "user_list_images.fcgi", payload={"get_timestamp": True}
            )
            # O firmware do iDFace pode retornar 'image_info', 'user_ids' ou 'user_images'
            user_images = (
                img_list_resp.get("image_info")
                or img_list_resp.get("user_ids")
                or img_list_resp.get("user_images")
                or []
            )
            faces_count = len(user_images)
        except Exception:
            # Fallback: conta users com image_timestamp > 0
            faces_count = sum(1 for u in users if u.get("image_timestamp", 0) > 0)

        # 3. Contagem de cartões
        cards = await self.load_all_objects("cards", page_size=500)
        card_count = len(cards)

        self.device.stats.user_count = user_count
        self.device.stats.face_count = faces_count
        self.device.stats.card_count = card_count

        return user_count, faces_count, card_count

    async def list_user_images(self) -> List[Dict[str, Any]]:
        """
        Lista IDs de usuários que possuem foto facial cadastrada.
        Retorna lista de dicionários com {"user_id": int, "timestamp": int}.
        Compatível com todas as versões de firmware Control iD (image_info, user_ids, user_images).
        """
        try:
            # 1. Tenta com get_timestamp: True
            resp = await self.request_api(
                "user_list_images.fcgi", payload={"get_timestamp": True}
            )
            # Caso 1: Retorna 'image_info' com lista de objetos [{"user_id": ..., "timestamp": ...}]
            if "image_info" in resp and isinstance(resp["image_info"], list):
                return resp["image_info"]

            # Caso 2: Retorna 'user_images' com lista de objetos
            if "user_images" in resp and isinstance(resp["user_images"], list):
                return resp["user_images"]

            # Caso 3: Retorna 'user_ids' com lista de inteiros [107, 134, ...]
            if "user_ids" in resp and isinstance(resp["user_ids"], list):
                return [{"user_id": int(uid), "timestamp": 0} for uid in resp["user_ids"]]

            # Fallback secundário: tenta sem payload para obter 'user_ids'
            resp_empty = await self.request_api("user_list_images.fcgi", payload={})
            if "user_ids" in resp_empty and isinstance(resp_empty["user_ids"], list):
                return [{"user_id": int(uid), "timestamp": 0} for uid in resp_empty["user_ids"]]

        except Exception:
            pass

        # Fallback para load_all_objects("users")
        try:
            users = await self.load_all_objects("users")
            return [
                {"user_id": u["id"], "timestamp": u.get("image_timestamp", 0)}
                for u in users
                if u.get("image_timestamp", 0) > 0 or "id" in u
            ]
        except Exception:
            return []

    async def download_user_image(
        self, user_id: int, max_retries: int = 3
    ) -> Optional[bytes]:
        """
        Baixa a foto facial binária JPEG via GET /user_get_image.fcgi com backoff exponencial.
        Se a catraca responder que o usuário não possui imagem cadastrada, retorna None imediatamente.
        """
        for attempt in range(1, max_retries + 1):
            try:
                image_bytes = await self.request_api(
                    endpoint="user_get_image.fcgi",
                    method="GET",
                    params={"user_id": user_id},
                    is_binary=True,
                )
                if image_bytes and len(image_bytes) > 100:  # Checagem de tamanho mínimo JPEG
                    return image_bytes
            except IDFaceAPIError as e:
                # Se o usuário não tem imagem, não precisa tentar de novo
                err_str = str(e)
                if "does not have an image" in err_str or "User does not have" in err_str:
                    return None
                if attempt == max_retries:
                    return None
                await asyncio.sleep(0.3 * attempt)
            except Exception:
                if attempt == max_retries:
                    return None
                await asyncio.sleep(0.3 * attempt)

        return None
