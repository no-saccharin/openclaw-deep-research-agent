"""
FastAPI 服务 — 供 OpenClaw Skill 或其他客户端调用
"""
import logging
from time import perf_counter
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from api.storage import init_database, list_research_records, save_research_record
from research.schemas import (
    ResearchHistoryResponse,
    ResearchRequest,
    ResearchResponse,
)
from research.flow import run_research
from research.config import Config

logging.basicConfig(level=Config.LOG_LEVEL)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_database()
    logger.info("🚀 Deep Research Agent API starting...")
    logger.info(f"   LLM Provider: {Config.LLM_PROVIDER}")
    logger.info(f"   BrightData: {'✅' if Config.BRIGHT_DATA_API_TOKEN else '❌'}")
    logger.info(f"   FireCrawl:  {'✅' if Config.FIRECRAWL_API_KEY else '❌'}")
    logger.info(f"   Stagehand:  {'✅' if Config.STAGEHAND_ENABLED else '❌'}")
    logger.info(f"   SQLite DB: {Config.SQLITE_DB_PATH}")
    yield
    logger.info("Deep Research Agent API shutting down...")


app = FastAPI(
    title="OpenClaw Deep Research Agent",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health():
    return {"status": "ok", "provider": Config.LLM_PROVIDER}


@app.post("/research", response_model=ResearchResponse)
async def research(req: ResearchRequest):
    """执行深度研究"""
    if not req.query.strip():
        raise HTTPException(status_code=400, detail="Query cannot be empty")

    logger.info(f"Research request: {req.query[:100]}...")
    started_at = perf_counter()

    try:
        result = await run_research(
            query=req.query,
            history=req.conversation_history,
        )
        response = ResearchResponse(
            success=True,
            result=result.get("result", "No result"),
            sources_count=result.get("sources_count", 0),
        )
        save_research_record(
            query=req.query,
            conversation_history=req.conversation_history,
            requester_type=req.requester_type,
            requester_user_id=req.requester_user_id,
            requester_chat_id=req.requester_chat_id,
            requester_username=req.requester_username,
            success=True,
            result=response.result,
            sources_count=response.sources_count,
            error=None,
            duration_ms=int((perf_counter() - started_at) * 1000),
        )
        return response
    except Exception as e:
        logger.exception("Research failed")
        response = ResearchResponse(
            success=False,
            result="",
            error=str(e),
        )
        save_research_record(
            query=req.query,
            conversation_history=req.conversation_history,
            requester_type=req.requester_type,
            requester_user_id=req.requester_user_id,
            requester_chat_id=req.requester_chat_id,
            requester_username=req.requester_username,
            success=False,
            result="",
            sources_count=0,
            error=response.error,
            duration_ms=int((perf_counter() - started_at) * 1000),
        )
        return response


@app.get("/research/history", response_model=ResearchHistoryResponse)
async def research_history(limit: int = 20, requester_user_id: int | None = None):
    items = list_research_records(limit=limit, requester_user_id=requester_user_id)
    return ResearchHistoryResponse(items=items, total=len(items))


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "api.server:app",
        host=Config.API_HOST,
        port=Config.API_PORT,
        reload=True,
    )