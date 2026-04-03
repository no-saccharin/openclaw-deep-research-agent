"""统一配置管理，从环境变量读取所有配置项"""
import os
from pathlib import Path
from research.secrets import load_environment, read_secret

load_environment()


class Config:
    # LLM
    LLM_PROVIDER = os.getenv("LLM_PROVIDER", "dashscope")
    DASHSCOPE_API_KEY = read_secret("DASHSCOPE_API_KEY")
    DASHSCOPE_BASE_URL = os.getenv(
        "DASHSCOPE_BASE_URL",
        "https://dashscope.aliyuncs.com/compatible-mode/v1",
    )
    OPENAI_API_KEY = read_secret("OPENAI_API_KEY")
    OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")

    LLM_MODEL_SEARCH = os.getenv("LLM_MODEL_SEARCH", "qwen-max")
    LLM_MODEL_SPECIALIST = os.getenv("LLM_MODEL_SPECIALIST", "qwen-plus")
    LLM_MODEL_RESPONSE = os.getenv("LLM_MODEL_RESPONSE", "qwen-max")

    # 搜索工具
    BRIGHT_DATA_API_TOKEN = read_secret("BRIGHT_DATA_API_TOKEN")
    FIRECRAWL_API_KEY = read_secret("FIRECRAWL_API_KEY")
    STAGEHAND_ENABLED = os.getenv("STAGEHAND_ENABLED", "false").lower() == "true"
    MODEL_API_KEY = read_secret("MODEL_API_KEY")

    # 服务
    API_HOST = os.getenv("API_HOST", "0.0.0.0")
    API_PORT = int(os.getenv("API_PORT", "8088"))
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

    # 存储
    SQLITE_DB_PATH = os.getenv(
        "SQLITE_DB_PATH",
        str(Path(__file__).resolve().parent.parent / "data" / "research_history.db"),
    )