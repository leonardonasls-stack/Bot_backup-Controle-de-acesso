# 🛡️ Bot Backup Catraca (Control iD iDFace ➔ iDSecure)

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/)
[![Flet](https://img.shields.io/badge/UI-Flet%201.0-4527a0.svg)](https://flet.dev/)
[![Control iD](https://img.shields.io/badge/Hardware-Control%20iD%20iDFace-00b4d8.svg)](https://www.controlid.com.br/)
[![MySQL](https://img.shields.io/badge/Database-MySQL%205.7%20%2F%208.0-orange.svg)](https://www.mysql.com/)
[![Tests](https://img.shields.io/badge/Tests-Pytest%20Passing-success.svg)](https://docs.pytest.org/)

Aplicação desktop profissional projetada para técnicos de campo e administradores de controle de acesso. O **Bot Backup Catraca** automatiza a varredura na rede local, a extração integral de bancos de contingência de leitores faciais **Control iD (iDFace)**, a consolidação inteligente com deduplicação de biometrias faciais em SQLite e a restauração completa no software servidor **iDSecure** (via injeção direta em MySQL, script SQL Dump ou sincronização via Web API).

---

## 🚀 Principais Funcionalidades

### 1. 🔍 Descoberta e Extração de Terminais
* **Auto-Discovery de Rede Local:** Detecta a sub-rede ativa e realiza varredura paralela multithread nos IPs à procura de equipamentos Control iD (portas HTTP 80/8080/443).
* **Autenticação e Sessão de Contingência:** Faz login via API nativa do dispositivo (`/login.fcgi`) e extrai:
  * Usuários (`users`)
  * Cartões (`cards`)
  * Grupos de acesso (`groups`)
  * Vínculos (`user_groups`)
  * Regras de acesso (`access_rules`)
  * Dispositivos (`devices`)
* **Download Massivo de Biometrias Faciais:** Extrai fotos faciais JPEG em lote diretamente do hardware (`/user_get_image.fcgi` / `/load_user_image.fcgi`) com reintento automático e checagem de integridade.

### 2. 🗄️ Consolidação e Deduplicação Inteligente (SQLite)
* **Storage Local Transacional:** Cria um banco `backup_controlid.sqlite` padronizado e auditável na pasta de destino escolhida.
* **Resolução de Conflitos:** Ao consolidar múltiplos terminais, aplica regra de precedência temporal baseada no timestamp de registro, evitando perda de dados recentes.
* **Checkpoint e Retomada:** Se a conexão cair, a extração pode ser pausada, retomada ou reexecutada a partir do último estado salvo.

### 3. 🔄 Restauração e Integração com o iDSecure
O bot oferece 3 métodos robustos para envio dos dados:
1. **Injeção Direta no MySQL do iDSecure (Porta 3306):**
   * Compatível com **MySQL 5.7 e 8.0** em modo estrito (`STRICT_TRANS_TABLES`, `ONLY_FULL_GROUP_BY`).
   * **Introspecção Dinâmica de Schema:** Consulta `INFORMATION_SCHEMA.COLUMNS` para adaptar inserts à versão do banco de dados iDSecure da máquina.
   * Conversão automática de timestamps para strings `DATETIME` (`YYYY-MM-DD HH:MM:SS`).
   * Mapeamento de modelo (`iDFace` ➔ `15`) e preenchimento de campos obrigatórios (`pis`, `inativo`, `timeOfRegistration`).
   * Barra de progresso visual em tempo real mostrando a injeção tabela por tabela (`Users`, `Cards`, `Groups`, `UserGroups`, `Devices`).
2. **Sincronização de Fotos Faciais via Web API (Porta 30443):**
   * Conecta à API HTTPS local do iDSecure (`/api/login/`).
   * Relaciona fotos por ID/Matrícula com os usuários ativos no servidor.
   * Injeta as imagens em Base64 ativando o parâmetro `canUseFacial = True`.
3. **Exportação de Scripts e Pacote ZIP:**
   * **SQL Dump (`dump_idsecure_mysql.sql`):** Script SQL pronto para execução manual no MySQL Workbench ou terminal.
   * **Pacote ZIP de Importação (`importacao_idsecure.zip`):** Contém a planilha padrão `usuarios.csv` formatada com máscara de importação do iDSecure e pasta com todas as fotos faciais.

### 4. 🖥️ Interface Moderna e Acessível (Flet)
* Design escuro de alta legibilidade técnico-operacional.
* Seleção de pastas de destino e de restauração através da **janela nativa de navegação do Windows Explorer** (com botão `Escolher Pasta...`).
* Monitoramento de progresso com porcentagem dinâmica, estatísticas de download e console de logs em tempo real.
* Sistema de logs rotativos gravados em `logs/bot_backup.log`.

---

## 📁 Estrutura do Projeto

```text
Bot Backup Catraca/
│
├── backend/
│   ├── core/
│   │   ├── exceptions.py          # Exceções customizadas do pipeline
│   │   ├── logger.py              # Configuração do Logger rotativo
│   │   └── network_utils.py       # Descoberta de IP/Subrede e varredura de portas
│   ├── extractors/
│   │   └── idface_extractor.py    # Cliente HTTP API para terminais Control iD
│   ├── merger/
│   │   └── merger_engine.py       # Motor de consolidação e resolução de duplicatas
│   ├── models/
│   │   └── backup_models.py       # Dataclasses (User, Card, Group, BackupConfig, etc.)
│   └── services/
│       ├── backup_manager.py      # Orquestrador do fluxo de backup ponta a ponta
│       ├── sqlite_storage.py      # Camada de persistência local SQLite
│       ├── mysql_idsecure_service.py # Injeção direta no MySQL e gerador de Dump
│       └── idsecure_api_restorer.py  # Integração com a API do iDSecure e gerador de ZIP
│
├── frontend/
│   ├── components/
│   │   ├── audit_summary.py       # Exibição do relatório final de auditoria
│   │   ├── device_selector.py     # Grid e seleção de leitores faciais descobertos
│   │   ├── header.py              # Cabeçalho da aplicação com status de rede
│   │   ├── progress_panel.py      # Painel de execução da Aba 1 (Backup)
│   │   └── restore_mysql_panel.py # Painel de execução da Aba 2 (Restauração iDSecure)
│   ├── styles/
│   │   └── theme.py               # Paleta de cores, tipografia e design tokens
│   └── app.py                     # Montagem das abas e navegação principal
│
├── backups/                       # Diretório padrão para armazenamento dos backups
├── logs/                          # Logs de execução (bot_backup.log)
├── tests/                         # Suíte de testes automatizados (Pytest)
├── build.ps1                      # Script PowerShell para testes e compilação (.exe)
├── main.py                        # Ponto de entrada da aplicação
└── requirements.txt               # Dependências do projeto
```

---

## 🛠️ Pré-requisitos

* **Sistema Operacional:** Windows 10 ou Windows 11 (64-bit).
* **Python:** 3.10 ou superior.
* **Acesso à Rede:** Conexão na mesma rede local que as catracas/leitores faciais e o servidor iDSecure.

---

## ⚙️ Instalação e Configuração

1. **Clone ou extraia o repositório:**
   ```bash
   git clone <url-do-repositorio>
   cd "Bot Backup Catraca"
   ```

2. **Crie e ative um ambiente virtual (recomendado):**
   ```powershell
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
   ```

3. **Instale as dependências:**
   ```bash
   pip install -r requirements.txt
   ```

---

## 🧪 Executando os Testes Automatizados

O projeto conta com uma suíte de testes unitários e de integração validando desde os modelos, persistência em SQLite, geração de dumps SQL até o pipeline ponta a ponta:

```bash
python -m pytest tests -v
```

---

## ▶️ Como Usar a Aplicação

Inicie a aplicação executando:
```bash
python main.py
```

### Aba 1: Backup dos Leitores Faciais
1. **Escanear Rede:** Clique no botão de varredura ou adicione o IP do terminal manualmente (ex: `192.168.3.89`).
2. **Credenciais do Leitor:** Insira o usuário e senha do dispositivo (padrão de fábrica: `admin` / `admin`).
3. **Pasta de Destino:** Use o botão **"Escolher Pasta..."** para selecionar onde os dados e fotos serão gravados.
4. **Iniciar Backup:** Acompanhe a barra de progresso e o download de fotos em tempo real. Ao final, um relatório de auditoria é gerado.

### Aba 2: Restauração no iDSecure
1. **Selecionar Pasta do Backup:** Clique em **"Escolher Pasta..."** e selecione a pasta do backup que contém o arquivo `backup_controlid.sqlite`.
2. **Configurar Acesso:**
   * **MySQL:** Informe Host (`localhost`), Porta (`3306`), Usuário (`root`), Senha e Banco (`idsecure`). Teste a conexão.
   * **API iDSecure:** Informe a URL (`https://localhost:30443`), Usuário (`admin`) e Senha. Teste a conexão.
3. **Executar a Restauração:**
   * Clique em **"Restaurar Diretamente no MySQL"** para injetar usuários, cartões, grupos e dispositivos.
   * Clique em **"Sincronizar Fotos via API"** para anexar as fotos faciais aos usuários no iDSecure.
   * (Opcional) Use **"Gerar dump_idsecure_mysql.sql"** ou **"Gerar ZIP de Importação"** para procedimentos manuais.

---

## 📦 Compilando Executável Standalone (.exe)

Para gerar uma versão executável portátil (sem dependência de Python instalado na máquina cliente):

Execute o script de automação no PowerShell:
```powershell
.\build.ps1
```

O script executará a bateria completa de testes e empacotará o sistema via PyInstaller. O executável standalone será gerado em:
```text
dist/BACKUP-BOT-iDFace/BACKUP-BOT-iDFace.exe
```

---

## 📋 Licença e Suporte
Desenvolvido para operações de manutenção e gestão de equipamentos de controle de acesso **Control iD**.
Para dúvidas, relatórios de auditoria ou sugestões, consulte os arquivos de especificação `PRD.md` e `TRD.md` inclusos na raiz do repositório.
