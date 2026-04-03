# OpenClaw Deep Research Agent

A scaffold project that provides:

- A core research flow with pluggable search providers
- A FastAPI service callable by OpenClaw
- Optional Telegram bot and Streamlit frontend
- Dockerized local deployment

## Quick Start

1. Create env file:

   cp .env.example .env

2. Provide secrets without writing plaintext into config files:

   export OPENCLAW_DASHSCOPE_API_KEY="your-dashscope-key"
   export OPENCLAW_BRIGHTDATA_API_TOKEN="your-brightdata-token"
   export OPENCLAW_TELEGRAM_BOT_TOKEN="your-telegram-bot-token"

   Or store them in the system keyring and reference them as
   `keyring:openclaw-deep-research-agent/<secret_name>`.

3. Install dependencies:

   pip install -e .[dev]

4. Run API:

   make dev

5. Run tests:

   make test

## Secret References

Sensitive values support these formats in [.env.example](.env.example) and [.env](.env):

- `env:OPENCLAW_DASHSCOPE_API_KEY`
- `keyring:openclaw-deep-research-agent/dashscope_api_key`

Examples for Linux Secret Service / macOS Keychain with Python keyring:

```bash
python -c "import keyring; keyring.set_password('openclaw-deep-research-agent', 'dashscope_api_key', input('DashScope API Key: '))"
python -c "import keyring; keyring.set_password('openclaw-deep-research-agent', 'brightdata_api_token', input('BrightData Token: '))"
python -c "import keyring; keyring.set_password('openclaw-deep-research-agent', 'telegram_bot_token', input('Telegram Bot Token: '))"
```

Then configure:

```dotenv
DASHSCOPE_API_KEY=keyring:openclaw-deep-research-agent/dashscope_api_key
BRIGHT_DATA_API_TOKEN=keyring:openclaw-deep-research-agent/brightdata_api_token
TELEGRAM_BOT_TOKEN=keyring:openclaw-deep-research-agent/telegram_bot_token
```

## Structure

- research/: core research logic
- api/: HTTP and bot interfaces
- openclaw-skill/: OpenClaw skill prompt and contract
- web/: optional Streamlit UI
- tests/: unit tests


# ═══════════════════════════════════════════
# 步骤 1: 克隆 & 配置
# ═══════════════════════════════════════════
mkdir openclaw-deep-research-agent && cd openclaw-deep-research-agent

# 把上面所有文件按目录结构创建好后：
cp .env.example .env
# 编辑 .env，填入你的 API Key

# ═══════════════════════════════════════════
# 步骤 2: 安装依赖
# ═══════════════════════════════════════════
# 确保 Python 3.11+ 和 Node.js 20+
python --version   # >= 3.11
node --version     # >= 20

pip install -e ".[dev]"
npx @brightdata/mcp --help   # 预下载 BrightData MCP

# ═══════════════════════════════════════════
# 步骤 3: 启动研究 API
# ═══════════════════════════════════════════
make run
# 或 Docker 方式：
make docker-build && make docker-up

# 验证
curl http://localhost:8000/health

# ═══════════════════════════════════════════
# 步骤 4: 测试研究功能
# ═══════════════════════════════════════════
make test-research

# ═══════════════════════════════════════════
# 步骤 5: 安装 OpenClaw + 接入 Telegram
# ═══════════════════════════════════════════
npm install -g openclaw@latest
openclaw            # 首次运行，按提示配置 LLM provider + API key

# 安装 Skill
make openclaw-install-skill

# 添加 Telegram 渠道
openclaw channels add
# 选择 Telegram，粘贴 Bot Token

# 配置执行权限（本地服务器不需要 gateway 模式）
openclaw config set tools.exec.security full

# 重启
openclaw restart