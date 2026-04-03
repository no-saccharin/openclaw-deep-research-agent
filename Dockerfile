FROM python:3.11-slim

# 系统依赖
RUN apt-get update && apt-get install -y \
    curl \
    git \
    && curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y nodejs \
    && rm -rf /var/lib/apt/lists/*

# 预安装 BrightData MCP（避免每次运行时下载）
RUN npx @brightdata/mcp --help || true

WORKDIR /app

# 复制依赖文件并安装
COPY pyproject.toml .
RUN pip install --no-cache-dir -e ".[dev]"

# 复制源代码
COPY . .

# 暴露端口
EXPOSE 8088

# 启动命令
CMD ["python", "-m", "api.server"]