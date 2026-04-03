"""三级搜索工具封装：BrightData → FireCrawl → Stagehand"""
import logging
import requests
from typing import Optional
from research.config import Config

logger = logging.getLogger(__name__)


class FireCrawlSearcher:
    """FireCrawl 补充搜索 - 当 BrightData 结果不足时使用"""

    def __init__(self):
        self.api_key = Config.FIRECRAWL_API_KEY
        self.base_url = "https://api.firecrawl.dev/v1/search"

    @property
    def available(self) -> bool:
        return bool(self.api_key)

    def search(self, query: str, limit: int = 5) -> str:
        """执行 FireCrawl 搜索，返回拼接后的文本结果"""
        if not self.available:
            logger.warning("FireCrawl API key not configured, skipping")
            return ""

        payload = {"query": query, "limit": limit, "timeout": 60000}
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        try:
            response = requests.post(
                self.base_url, json=payload, headers=headers, timeout=60
            )
            response.raise_for_status()
            data = response.json()

            if data.get("success") and data.get("data"):
                results = []
                for item in data["data"]:
                    title = item.get("title", "")
                    desc = item.get("description", "")
                    url = item.get("url", "")
                    if title or desc:
                        results.append(
                            f"Title: {title}\nDescription: {desc}\nURL: {url}"
                        )
                return "\n---\n".join(results)

        except Exception as e:
            logger.error(f"FireCrawl search failed: {e}")

        return ""

    def scrape_url(self, url: str) -> str:
        """抓取单个 URL 的内容"""
        if not self.available:
            return ""

        scrape_url = "https://api.firecrawl.dev/v1/scrape"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {"url": url, "formats": ["markdown"]}

        try:
            response = requests.post(
                scrape_url, json=payload, headers=headers, timeout=60
            )
            response.raise_for_status()
            data = response.json()
            if data.get("success") and data.get("data"):
                return data["data"].get("markdown", "")
        except Exception as e:
            logger.error(f"FireCrawl scrape failed for {url}: {e}")

        return ""


class StagehandBrowser:
    """Stagehand 浏览器自动化 - 处理需要 JS 渲染的动态页面"""

    def __init__(self):
        self.enabled = Config.STAGEHAND_ENABLED
        self.model_api_key = Config.MODEL_API_KEY

    @property
    def available(self) -> bool:
        return self.enabled and bool(self.model_api_key)

    async def browse(self, task_description: str, website_url: str) -> str:
        """执行浏览器自动化任务"""
        if not self.available:
            logger.warning("Stagehand not enabled, skipping")
            return ""

        try:
            from stagehand import Stagehand, StagehandConfig

            config = StagehandConfig(
                env="LOCAL",
                model_name="gpt-4o",
                self_heal=True,
                system_prompt="You are a browser automation assistant.",
                model_client_options={"apiKey": self.model_api_key},
                verbose=0,
            )

            stagehand = Stagehand(config)
            await stagehand.init()

            try:
                agent = stagehand.agent(
                    model="computer-use-preview",
                    provider="openai",
                    instructions="Extract the requested information. Do not ask follow-up questions.",
                    options={"apiKey": self.model_api_key},
                )

                await stagehand.page.goto(website_url)
                result = await agent.execute(
                    instruction=task_description,
                    max_steps=15,
                    auto_screenshot=True,
                )
                return result.message or ""
            finally:
                await stagehand.close()

        except ImportError:
            logger.error("Stagehand not installed. Install with: pip install stagehand")
            return ""
        except Exception as e:
            logger.error(f"Stagehand browse failed: {e}")
            return ""