"""基础集成测试"""
import asyncio
import os
import tempfile
from unittest.mock import patch

import pytest


def test_config_loads():
    """测试配置能正常加载"""
    from research.config import Config
    assert Config.API_PORT == 8088


def test_schemas():
    """测试数据模型"""
    from research.schemas import ResearchRequest, ResearchResponse, URLBuckets, SpecialistOutput

    buckets = URLBuckets(web=["https://example.com"])
    assert len(buckets.web) == 1
    assert len(buckets.instagram) == 0

    req = ResearchRequest(query="test query")
    assert req.query == "test query"

    response = ResearchResponse(success=True, result="ok")
    assert response.success is True


def test_llm_factory():
    """测试 LLM 工厂（不实际调用 API）"""
    from research.llm_factory import create_llm
    # 只测试创建过程不报错
    llm = create_llm("search")
    assert llm is not None


def test_firecrawl_searcher_unavailable():
    """测试 FireCrawl 未配置时的行为"""
    from research.search_tools import FireCrawlSearcher

    with patch.dict("os.environ", {"FIRECRAWL_API_KEY": ""}, clear=False):
        searcher = FireCrawlSearcher()
        # 未配置时应返回空字符串
        result = searcher.search("test")
        assert result == ""


@pytest.mark.asyncio
async def test_api_health():
    """测试 API 健康检查"""
    from httpx import AsyncClient, ASGITransport
    from api.server import app

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/health")
        assert response.status_code == 200
        assert response.json()["status"] == "ok"


def test_storage_persists_history():
    """测试 SQLite 历史记录写入和读取"""
    from api import storage

    with tempfile.TemporaryDirectory() as temp_dir:
        db_path = os.path.join(temp_dir, "history.db")

        with patch.object(storage.Config, "SQLITE_DB_PATH", db_path):
            storage.init_database()
            record_id = storage.save_research_record(
                query="test query",
                conversation_history=[{"role": "user", "content": "hello"}],
                requester_type="telegram",
                requester_user_id=123,
                requester_chat_id=456,
                requester_username="tester",
                success=True,
                result="answer",
                sources_count=2,
                error=None,
                duration_ms=123,
            )

            items = storage.list_research_records(limit=10, requester_user_id=123)

        assert record_id > 0
        assert len(items) == 1
        assert items[0].query == "test query"
        assert items[0].requester_user_id == 123
        assert items[0].conversation_history[0]["content"] == "hello"
        assert items[0].sources_count == 2