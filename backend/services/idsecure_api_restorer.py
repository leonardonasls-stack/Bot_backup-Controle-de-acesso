"""
Serviço de Restauração via API Local do iDSecure (https://localhost:30443)
e Gerador do Pacote Nativo de Importação (importacao_idsecure.zip com Planilha CSV + Fotos JPG).
"""

import base64
import csv
import io
from pathlib import Path
import zipfile
from typing import Dict, Any, List, Optional, Tuple
import httpx

from backend.models.backup_models import iDSecureAPIConfig
from backend.services.sqlite_storage import SQLiteStorage


class IDSecureAPIRestorer:
    """Gerador de ZIP e conector para API local do iDSecure."""

    def __init__(self, storage: SQLiteStorage, output_dir: str):
        self.storage = storage
        self.output_dir = Path(output_dir)
        self.faces_dir = self.output_dir / "faces"

    def generate_import_zip(self) -> Path:
        """
        Gera o pacote importacao_idsecure.zip contendo:
        1. usuarios.csv: Planilha com UTF-8 BOM e delimitador ';' compatível com importador web do iDSecure.
        2. Pasta fotos/: Imagens nomeadas conforme coluna de foto do CSV.
        """
        zip_path = self.output_dir / "importacao_idsecure.zip"

        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zipf:
            # 1. Gera CSV em memória com UTF-8 BOM
            csv_output = io.StringIO()
            csv_output.write("\ufeff")  # BOM para Excel e iDSecure abrirem perfeitamente com acentos

            writer = csv.writer(csv_output, delimiter=";", quoting=csv.QUOTE_MINIMAL)
            # Cabeçalho padrão aceito pelo importador do iDSecure
            writer.writerow(["ID", "Matrícula", "Nome", "Cartão", "Grupo", "Foto"])

            with self.storage._get_connection() as conn:
                query = """
                    SELECT 
                        u.id, 
                        u.registration, 
                        u.name, 
                        c.value AS card_value, 
                        g.name AS group_name,
                        img.file_path,
                        img.status AS img_status
                    FROM users u
                    LEFT JOIN cards c ON c.user_id = u.id
                    LEFT JOIN user_groups ug ON ug.user_id = u.id
                    LEFT JOIN groups g ON g.id = ug.group_id
                    LEFT JOIN user_images img ON img.user_id = u.id
                    ORDER BY u.id ASC
                """
                rows = conn.execute(query).fetchall()

                for row in rows:
                    u_id = row["id"]
                    reg = row["registration"] or ""
                    name = row["name"] or ""
                    card = row["card_value"] or ""
                    group = row["group_name"] or "Geral"
                    
                    foto_nome = ""
                    if row["file_path"] and row["img_status"] == "DOWNLOADED":
                        p = Path(row["file_path"])
                        if p.exists():
                            foto_nome = p.name
                            # Adiciona foto dentro do ZIP na pasta fotos/
                            zipf.write(p, arcname=f"fotos/{p.name}")

                    writer.writerow([u_id, reg, name, card, group, foto_nome])

            # Salva usuarios.csv no ZIP
            zipf.writestr("usuarios.csv", csv_output.getvalue().encode("utf-8-sig"))

        return zip_path

    async def test_api_connection(self, config: iDSecureAPIConfig) -> Tuple[bool, str]:
        """Testa comunicação com a API local do iDSecure (porta 30443)."""
        transport = httpx.AsyncHTTPTransport(verify=config.verify_ssl)
        async with httpx.AsyncClient(transport=transport, timeout=10.0, follow_redirects=True) as client:
            try:
                # O servidor iDSecure espera /api/login/ com barra final ou redireciona via 307
                base = config.base_url.rstrip('/')
                login_url = f"{base}/api/login/"
                resp = await client.post(
                    login_url,
                    json={"username": config.api_user, "password": config.api_password},
                    headers={"Content-Type": "application/json"},
                )
                if resp.status_code == 200:
                    data = resp.json()
                    token = data.get("accessToken") or data.get("token") or data.get("session")
                    config.token = token
                    return True, "Autenticação na API do iDSecure bem-sucedida! Token JWT obtido."
                elif resp.status_code in (401, 403):
                    return False, "Usuário ou senha da API do iDSecure inválidos (Credenciais rejeitadas)."
                else:
                    return False, f"Resposta inesperada da API: HTTP {resp.status_code} - {resp.text[:100]}"
            except Exception as e:
                return False, f"Não foi possível conectar na API do iDSecure ({config.base_url}): {str(e)}"

    async def sync_faces_to_idsecure_api(
        self,
        config: iDSecureAPIConfig,
        on_progress: Optional[callable] = None,
        on_log: Optional[callable] = None,
    ) -> Tuple[int, int]:
        """
        Envia as fotos faciais para os usuários já cadastrados no iDSecure via API local.
        Retorna (sucessos, falhas).
        """
        def log(msg: str):
            if on_log:
                on_log(msg)

        if not config.token:
            ok, msg = await self.test_api_connection(config)
            if not ok:
                log(f"Falha ao autenticar na API: {msg}")
                return 0, 0

        transport = httpx.AsyncHTTPTransport(verify=config.verify_ssl)
        successes = 0
        failures = 0

        async with httpx.AsyncClient(transport=transport, timeout=15.0, follow_redirects=True) as client:
            headers = {
                "Authorization": f"Bearer {config.token}",
            }
            base = config.base_url.rstrip('/')
            url_user = f"{base}/api/user/"

            # 1. Carrega o mapeamento de usuários ativos do iDSecure para relacionar corretamente
            log("Obtendo mapa de usuários ativos do iDSecure para correlacionar fotos...")
            active_users_map: Dict[str, int] = {}  # "matricula" -> id_ativo e "iddevice" -> id_ativo
            try:
                # Busca lista completa de usuários do iDSecure (idType=0)
                r_list = await client.post(
                    f"{base}/api/user/list?idType=0&start=0&length=10000",
                    headers=headers,
                    json=None,
                )
                if r_list.status_code == 200:
                    for row in r_list.json().get("data", []):
                        act_id = row.get("id")
                        reg = str(row.get("registration") or "").strip().lower()
                        id_dev = str(row.get("idDevice") or "").strip()
                        if reg:
                            active_users_map[f"reg_{reg}"] = act_id
                        if id_dev:
                            active_users_map[f"dev_{id_dev}"] = act_id
            except Exception as e:
                log(f"Aviso ao consultar listagem de usuários do iDSecure: {e}")

            with self.storage._get_connection() as conn:
                # Obtém imagens associadas a usuários e matrículas
                images = conn.execute("""
                    SELECT img.user_id, img.file_path, u.registration
                    FROM user_images img
                    LEFT JOIN users u ON u.id = img.user_id
                    WHERE img.status = 'DOWNLOADED'
                """).fetchall()

            total = len(images)
            log(f"Sincronizando {total} fotos com os usuários ativos no iDSecure...")

            for idx, img in enumerate(images, 1):
                u_id = img["user_id"]
                reg = str(img["registration"] or "").strip().lower()
                path = Path(img["file_path"])
                if not path.exists():
                    failures += 1
                    continue

                # Determina o ID ativo real do usuário no iDSecure:
                # 1º por matrícula: se houver matrícula igual
                # 2º por idDevice: se o terminal usava esse u_id como idDevice
                # 3º pelo próprio ID numérico
                target_id = None
                if reg and f"reg_{reg}" in active_users_map:
                    target_id = active_users_map[f"reg_{reg}"]
                elif f"dev_{u_id}" in active_users_map:
                    target_id = active_users_map[f"dev_{u_id}"]
                else:
                    target_id = u_id

                try:
                    # 1. Busca dados cadastrais atuais do usuário ativo
                    r_get = await client.get(f"{url_user}{target_id}", headers=headers)
                    if r_get.status_code == 200:
                        u_data = r_get.json()
                    else:
                        u_data = {"id": target_id}

                    with open(path, "rb") as f_img:
                        b64 = base64.b64encode(f_img.read()).decode("utf-8")

                    u_data["foto"] = b64
                    u_data["canUseFacial"] = True
                    # No backend C# do iDSecure, para atualizar o registro sem disparar colisão de idDevice,
                    # o campo idDevice é enviado como None/null, preservando a foto e gerando o template facial.
                    u_data["idDevice"] = None

                    resp = await client.put(url_user, json=u_data, headers=headers)
                    if resp.status_code == 200 and resp.json().get("code") == 200:
                        successes += 1
                        # Atualiza mapa se gerou um newID na edição com substituição
                        new_id = resp.json().get("newID")
                        if new_id and new_id != target_id:
                            if reg:
                                active_users_map[f"reg_{reg}"] = new_id
                            active_users_map[f"dev_{u_id}"] = new_id
                    else:
                        failures += 1
                except Exception:
                    failures += 1

                if on_progress:
                    on_progress(idx, total)

        log(f"Sincronização de fotos concluída: {successes} enviadas com sucesso, {failures} falhas.")
        return successes, failures
