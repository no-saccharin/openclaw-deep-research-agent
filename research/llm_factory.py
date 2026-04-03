"""LLM 工厂 - 一处配置，全局统一切换 LLM 提供商"""
from crewai import LLM
from research.config import Config


def create_llm(role: str = "search") -> LLM:
    """
    根据角色创建对应的 LLM 实例。
    role: "search" | "specialist" | "response"
    """
    model_map = {
        "search": Config.LLM_MODEL_SEARCH,
        "specialist": Config.LLM_MODEL_SPECIALIST,
        "response": Config.LLM_MODEL_RESPONSE,
    }
    model_name = model_map.get(role, Config.LLM_MODEL_SEARCH)

    provider = Config.LLM_PROVIDER

    if provider == "dashscope":
        return LLM(
            model=f"dashscope/{model_name}",
            base_url=Config.DASHSCOPE_BASE_URL,
            api_key=Config.DASHSCOPE_API_KEY,
            temperature=0.1 if role == "search" else 0.3,
        )
    elif provider == "openai":
        return LLM(
            model=f"openai/{model_name}",
            api_key=Config.OPENAI_API_KEY,
            temperature=0.1 if role == "search" else 0.3,
        )
    elif provider == "ollama":
        return LLM(
            model=f"ollama/{model_name}",
            base_url=Config.OLLAMA_BASE_URL,
            temperature=0.1 if role == "search" else 0.3,
        )
    else:
        raise ValueError(f"Unknown LLM provider: {provider}")