# API & Database Mapping Specification — Control iD (iDFace `.fcgi` ↔ iDSecure `MySQL` & `REST API`)

**Referência:** Complemento Técnico ao [TRD.md](file:///g:/Meu%20Drive/Projetos/Bot%20Backup%20Catraca/TRD.md)  
**Objetivo:** Documentar todos os payloads JSON exatos dos terminais **iDFace** e as queries/estruturas de tradução para o banco **MySQL do iDSecure** e pacote de importação.

---

## 1. Endpoints da API Embarcada do Terminal (`iDFace` — Porta 80/443)

Todas as requisições (exceto `login.fcgi`) exigem o parâmetro `?session={token}` na URL e `Content-Type: application/json`.

### 1.1 Autenticação e Sessão
* **Login:** `POST http://{ip}/login.fcgi`
  ```json
  // Request
  {"login": "admin", "password": "admin"}
  // Response (200 OK)
  {"session": "0192837465abcdef"}
  ```
* **Validação de Sessão:** `POST http://{ip}/session_is_valid.fcgi?session={token}`
* **Informações do Equipamento:** `POST http://{ip}/system_information.fcgi?session={token}`
  ```json
  // Response parcial relevante
  {
    "serial": "0K0123456789",
    "version": "6.14.2",
    "device_model": "iDFace"
  }
  ```

### 1.2 Extração Paginada de Objetos (`POST /load_objects.fcgi?session={token}`)
Para evitar sobrecarga na CPU/RAM da catraca, usar sempre `limit: 500` e incrementar `offset` de `500` em `500` até que a lista retornada venha vazia ou menor que `limit`.

```json
// Request Genérico
{
  "object": "users",
  "limit": 500,
  "offset": 0
}
```

#### Tabelas a Extrair e Seus Campos Nativos no iDFace:
1. **`users`**:
   ```json
   {"users": [{"id": 1, "registration": "1001", "name": "JOAO SILVA", "password": "", "salt": "", "expires": 0, "user_type_id": 0, "begin_time": 0, "end_time": 0, "image_timestamp": 1710000000}]}
   ```
2. **`cards`**:
   * Nota: No iDFace, o campo `value` armazena o cartão em 64 bits (`(area << 32) + codigo` para Wiegand 26, ou o decimal direto).
   ```json
   {"cards": [{"id": 10, "value": 42949673960, "user_id": 1, "type": 1}]}
   ```
3. **`groups`** e **`departments`**:
   ```json
   {"groups": [{"id": 1, "name": "Padrão"}]}
   ```
4. **`user_groups`**:
   ```json
   {"user_groups": [{"user_id": 1, "group_id": 1}]}
   ```
5. **`time_zones`** (Horários) e **`time_spans`** (Faixas de Horário):
   ```json
   {"time_zones": [{"id": 1, "name": "Comercial"}]}
   ```
   ```json
   {"time_spans": [{"id": 1, "time_zone_id": 1, "start": 28800, "end": 64800, "sun": 0, "mon": 1, "tue": 1, "wed": 1, "thu": 1, "fri": 1, "sat": 0, "hol1": 0, "hol2": 0, "hol3": 0}]}
   ```
6. **`access_rules`** e Tabelas Relacionais:
   * `access_rules`: `{"id": 1, "name": "Regra Geral", "type": 1, "priority": 0}`
   * `group_access_rules`: `{"group_id": 1, "access_rule_id": 1}`
   * `user_access_rules`: `{"user_id": 1, "access_rule_id": 1}`
   * `access_rule_time_zones`: `{"access_rule_id": 1, "time_zone_id": 1}`
   * `portal_access_rules`: `{"portal_id": 1, "access_rule_id": 1}`
   * `holidays`: `{"id": 1, "name": "Natal", "day": 25, "month": 12, "year": 0, "holiday_type": 1}`
   * `pins` e `qrcodes` (caso suportados no firmware do equipamento; se retornar HTTP 400 `"Invalid object"`, ignorar silenciosamente).

### 1.3 Listagem e Download de Fotos Faciais
1. **Listar IDs que possuem foto:** `POST http://{ip}/user_list_images.fcgi?session={token}`
   ```json
   // Request
   {"get_timestamp": true}
   // Response
   {"user_images": [{"user_id": 1, "timestamp": 1710000000}, {"user_id": 2, "timestamp": 1710000500}]}
   ```
   *(Fallback caso `user_list_images.fcgi` não retorne timestamps: filtrar `users` onde `image_timestamp > 0` ou tentar download para todos os `users`).*
2. **Baixar Foto JPG:** `GET http://{ip}/user_get_image.fcgi?user_id={id}&session={token}`
   * Retorna `200 OK` com `Content-Type: image/jpeg` (bytes binários da imagem original).

---

## 2. Mapeamento de Tradução: `iDFace` $\rightarrow$ `MySQL (iDSecure)`

No banco **MySQL do iDSecure**, os nomes das tabelas e colunas seguem convenções específicas (com versionamento de `id` vs `idDevice` na tabela `Users`).

### 2.1 Tabela `Users` (MySQL iDSecure)
| Coluna MySQL (`Users`) | Tipo MySQL | Origem no `iDFace` | Regra de Conversão / Default |
| :--- | :--- | :--- | :--- |
| `id` | `BIGINT AUTO_INCREMENT` | `users.id` | Na carga inicial em banco limpo, usar o próprio `users.id`. |
| `idDevice` | `INT NOT NULL` | `users.id` | **Obrigatório:** Deve ser exatamente o `users.id` da catraca para manter sincronia de hardware. |
| `name` | `VARCHAR(255)` | `users.name` | String UTF-8 limpa. |
| `registration` | `VARCHAR(100)` | `users.registration` | Matrícula do usuário. |
| `cpf` | `VARCHAR(20)` | Extraído se `registration` for CPF (11 dígitos) ou `NULL` | Opcional. |
| `pis` | `VARCHAR(20)` | `NULL` (ou extraído se aplicável) | Opcional. |
| `password` | `VARCHAR(255)` | `users.password` | Senha numérica / hash. |
| `salt` | `VARCHAR(255)` | `users.salt` | Salt da senha. |
| `inativo` / `inactive` | `TINYINT(1)` | `users.expires` / `end_time` | `0` (Ativo) por padrão. |
| `contingency` | `TINYINT(1)` | Constante `1` | `1` (Habilitado offline nos coletores). |
| `deleted` | `TINYINT(1)` | Constante `0` | `0` (Não deletado). |
| `idType` | `TINYINT(1)` | `users.user_type_id` | `0` para Pessoa (`user_type_id == 0` ou `null`), `1` para Visitante (`user_type_id == 1`). |
| `idArea` | `INT` | Constante `1` (ou `NULL`) | Área padrão inicial. |
| `timeOfRegistration` | `BIGINT` | `users.begin_time` ou Timestamp atual | Unix timestamp em segundos. |
| `dataLastLog` | `BIGINT` | `0` | Unix timestamp do último giro. |

### 2.2 Tabela `Cards` (MySQL iDSecure)
| Coluna MySQL (`Cards`) | Tipo MySQL | Origem no `iDFace` | Regra de Conversão |
| :--- | :--- | :--- | :--- |
| `id` | `BIGINT` | `cards.id` | ID original do cartão. |
| `id_user` | `BIGINT` | `cards.user_id` | FK apontando para `Users.id`. |
| `code` | `BIGINT` | `cards.value` | Valor numérico de 64 bits do cartão. |
| `value` | `VARCHAR(100)` | `str(cards.value)` | Representação textual ou Wiegand `area,codigo`. |
| `type` | `INT` | `cards.type` | `0` (ASK), `1` (Mifare), `2` (QR Code). Default: `0` ou `1`. |

### 2.3 Tabelas `Groups` e `UserGroups` (MySQL iDSecure)
* **`Groups`**:
  * `id` $\leftarrow$ `groups.id`
  * `name` $\leftarrow$ `groups.name`
  * `idType` $\leftarrow$ `1` (Grupo de Pessoas) ou `0` (Departamento, se vier de `departments`).
* **`UserGroups`**:
  * `id` $\leftarrow$ Sequencial (`1, 2, 3...`)
  * `idUser` $\leftarrow$ `user_groups.user_id`
  * `idGroup` $\leftarrow$ `user_groups.group_id`

### 2.4 Tabelas de Horários e Regras (`Scheduls`, `AccessRules`, `Devices`)
* **`Scheduls`**: Recebe a combinação de `time_zones` e `time_spans` (horários em segundos desde as `00:00`, ex: `28800` = `08:00`, `64800` = `18:00`).
* **`AccessRules`**: Recebe `access_rules` (`id`, `name`).
* **`Devices`**: Recebe os iDFaces escaneados na rede (`id`, `name`, `ip`, `serial`, `model`), poupando o técnico de recadastrar os IPs das catracas no iDSecure novo.

---

## 3. Introspecção Segura de Schema no MySQL (`INFORMATION_SCHEMA`)

Como o técnico geralmente instala o **iDSecure** novo (que cria as tabelas vazias no MySQL automaticamente na primeira inicialização) e só depois roda a Restauração do Bot:
1. O `mysql_idsecure_service.py` verifica se o banco `idsecure` já possui tabelas criadas pelo instalador oficial.
2. Se as tabelas **já existirem**, o Bot executa:
   ```sql
   SELECT TABLE_NAME, COLUMN_NAME
   FROM INFORMATION_SCHEMA.COLUMNS
   WHERE TABLE_SCHEMA = 'idsecure';
   ```
3. Ele monta os comandos `INSERT INTO ... ON DUPLICATE KEY UPDATE ...` preenchendo **apenas as colunas existentes naquela versão do iDSecure**, garantindo compatibilidade tanto com versões antigas quanto novas do iDSecure!
4. Se o banco estiver **totalmente vazio** (técnico criou apenas o schema MySQL puro antes de abrir o iDSecure), o Bot executa os `CREATE TABLE IF NOT EXISTS` padrão do iDSecure e popula os dados.
