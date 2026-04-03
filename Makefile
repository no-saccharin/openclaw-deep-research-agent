.PHONY: install run dev docker-build docker-up docker-down test openclaw-sync-env

# ── 本地开发 ──
install:
	pip install -e ".[dev]"
	npx @brightdata/mcp --help || true

run:
	python -m api.server

dev:
	python -m uvicorn api.server:app --host 0.0.0.0 --port 8088 --reload

# ── Docker ──
docker-build:
	docker compose build

docker-up:
	docker compose up -d

docker-down:
	docker compose down

docker-logs:
	docker compose logs -f research-api

# ── 测试 ──
test:
	python -m pytest tests/ -v

# ── 快速测试研究功能 ──
test-research:
	curl -s -X POST http://localhost:8088/research \
		-H "Content-Type: application/json" \
		-d '{"query": "2026年AI Agent工程师岗位要求有哪些"}' | python -c 'import sys, json; print(json.dumps(json.load(sys.stdin), ensure_ascii=False, indent=2))'

# ── OpenClaw 相关 ──
openclaw-install:
	npm install -g openclaw@latest

openclaw-start:
	openclaw start

openclaw-add-telegram:
	openclaw channels add

openclaw-install-skill:
	mkdir -p ~/.openclaw/skills
	rm -rf ~/.openclaw/skills/openclaw-skill
	cp -r openclaw-skill ~/.openclaw/skills/openclaw-skill
	@echo "✅ Skill installed. Restart OpenClaw to activate."

openclaw-sync-env:
	systemctl --user import-environment OPENCLAW_DASHSCOPE_API_KEY OPENCLAW_TELEGRAM_BOT_TOKEN HTTP_PROXY HTTPS_PROXY
	systemctl --user restart openclaw-gateway.service
	@echo "✅ Synced current shell env to OpenClaw gateway and restarted service."