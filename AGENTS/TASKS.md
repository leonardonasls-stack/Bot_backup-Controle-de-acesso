# TASKS: Plano de Execução e Checklist de Desenvolvimento (IDE)

**Projeto:** Bot Backup Catraca (Control iD iDFace $\rightarrow$ SQLite / MySQL iDSecure)  
**Stack:** Python 3.10+ | Flet (Flutter UI) | HTTPX (Async) | SQLite3 | PyMySQL  
**Documentos Base:**
* [PRD.md](file:///g:/Meu%20Drive/Projetos/Bot%20Backup%20Catraca/PRD.md) — Requisitos de Produto
* [TRD.md](file:///g:/Meu%20Drive/Projetos/Bot%20Backup%20Catraca/TRD.md) — Arquitetura Técnica
* [API_DATABASE_MAPPING.md](file:///g:/Meu%20Drive/Projetos/Bot%20Backup%20Catraca/AGENTS/API_DATABASE_MAPPING.md) — Payloads `.fcgi` e Mapeamento MySQL `iDSecure`

---

## Fase 1: Setup Inicial e Modelos de Domínio
- [x] **1.1** Criar `requirements.txt` (`flet`, `httpx`, `pymysql`, `cryptography`, `reportlab`, `pyinstaller`) e estrutura de pastas (`backend/core`, `backend/models`, `backend/services`, `frontend/components`, `frontend/styles`, `tests`, `backups`).
- [x] **1.2** Implementar `backend/models/device.py` (`ControlIdDevice`, `DeviceBackupStats`).
- [x] **1.3** Implementar `backend/models/backup_models.py` (`BackupProgress`, `BackupAuditReport`, `MySQLConnectionConfig`, `iDSecureAPIConfig`).

## Fase 2: Descoberta de Rede e Cliente API iDFace (`backend/core/`)
- [x] **2.1** Implementar `network_utils.py`, `detector.py` e `scanner.py` (suporte a IP único, faixa `192.168.1.100-110`, lista de IPs e CIDR `/24`, reutilizando o padrão assíncrono do Scan Bot).
- [x] **2.2** Implementar `idface_client.py`:
  - `login()` com armazenamento de `session` e **middleware de auto-reautenticação** caso retorne HTTP 401/403.
  - `count_users_and_faces()` para pré-diagnóstico rápido na tabela de equipamentos.
  - `load_all_objects(object_name, page_size=500)` com paginação automática (`limit` / `offset`).
  - `list_user_images()` via `POST /user_list_images.fcgi` (com fallback para `users.image_timestamp`).
  - `download_user_image(user_id)` via `GET /user_get_image.fcgi` com 3 *retries* e *backoff*.

## Fase 3: Persistência SQLite, Extração e Deduplicação (`backend/core/` & `backend/services/`)
- [x] **3.1** Implementar `sqlite_storage.py`:
  - Criação do banco `backup_controlid.sqlite` com tabelas de controle (`source_devices`, `raw_device_objects`) e tabelas consolidadas (`users`, `user_images`, `cards`, `groups`, `user_groups`, `time_zones`, `time_spans`, `access_rules`, `api_objects`).
  - Suporte a *Checkpoints* (verificar quais fotos já estão com status `DOWNLOADED` para permitir retomar um backup interrompido).
- [x] **3.2** Implementar `extractor.py` e `merger.py`:
  - Extração coordenada de múltiplos iDFaces com semáforo por IP (`MAX_CONCURRENT_IMAGES_PER_DEVICE = 3`).
  - **Deduplicação Pré-Download de Fotos:** Não baixar novamente a foto de um `user_id` se ela já foi baixada de outra catraca com `timestamp` igual ou superior.
  - Consolidação de registros (`Best-Record Wins`) e detecção de conflitos de cadastro entre catracas.
- [x] **3.3** Implementar `exporter_service.py`:
  - Geração do `backup_full.json`, `audit_report.json` e organização da pasta `/faces/{id}_{registration}_{nome}.jpg`.

## Fase 4: Tradutor MySQL e Restauração no iDSecure (`backend/services/`)
- [x] **4.1** Implementar `mysql_idsecure_service.py`:
  - **Gerador de Dump (`dump_idsecure_mysql.sql`):** Gera automaticamente o script SQL compatível com o MySQL do iDSecure (`Users` com `id` + `idDevice`, `Cards`, `Groups`, `UserGroups`, `Scheduls`, `AccessRules`, `Devices`).
  - **Conector Direto `PyMySQL`:** Testar conexão na porta `3306`, inspecionar `INFORMATION_SCHEMA.COLUMNS` do banco `idsecure` e injetar os dados em lote (`executemany` / transações seguras).
- [x] **4.2** Implementar `idsecure_api_restorer.py`:
  - Geração automática do pacote `importacao_idsecure.zip` (Planilha CSV UTF-8 BOM + Fotos JPG).
  - Conector de restauração via API local do iDSecure (`https://localhost:30443/api/...`) para envio automatizado de usuários e fotos faciais.

## Fase 5: Interface Gráfica Desktop em Flet (`frontend/`)
- [x] **5.1** Implementar `frontend/styles/theme.py` (Dark Mode corporativo consistente com o Scan Bot).
- [x] **5.2** Implementar **Aba 1 — Extração iDFace**:
  - `connection_panel.py` (Input de IP/Faixa/CIDR + Login/Senha + Botão Buscar).
  - `device_selector.py` (Tabela de iDFaces com checkbox, serial, modelo, qtd. de usuários e fotos).
  - `progress_panel.py` (Barras de progresso de Objetos e Fotos com ETA, botão Pausar/Retomar e console de logs).
  - `audit_summary.py` (Cards de KPI pós-extração + botão Abrir Pasta do Backup).
- [x] **5.3** Implementar **Aba 2 — Restauração MySQL / iDSecure** (`restore_mysql_panel.py`):
  - Seletor da pasta de backup gerada.
  - Formulário MySQL (`Host`, `Porta 3306`, `User`, `Password`, `Database idsecure`) + botões **"Testar Conexão MySQL"** e **"Injetar no Banco MySQL"**.
  - Formulário API iDSecure (`https://localhost:30443`) + botões de sincronização de fotos e acesso rápido ao `dump_idsecure_mysql.sql` e `importacao_idsecure.zip`.
- [x] **5.4** Integrar tudo no `frontend/app.py` e `main.py`.

## Fase 6: Servidor Mock Control iD, Testes Automatizados e Build `.exe`
- [x] **6.1** Criar `tests/mock_idface_server.py` (simulando 2 catracas iDFace com usuários, cartões, grupos, horários e fotos JPEG binárias).
- [x] **6.2** Criar testes unitários e E2E (`test_client_extractor.py`, `test_merger_sqlite.py`, `test_mysql_translator.py`, `test_e2e.py`).
- [x] **6.3** Criar `build.ps1` para rodar os testes e empacotar o executável standalone `dist/BACKUP-BOT-iDFace.exe` via PyInstaller.
