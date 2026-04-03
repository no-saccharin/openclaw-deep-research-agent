"""
OpenClaw Deep Research Flow
整合 BrightData MCP 多平台搜索 + FireCrawl 补充 + Stagehand 浏览器自动化
"""
import json
import logging
import os
from typing import Any, Dict, List

from crewai import Agent, Crew, Task
from crewai.flow.flow import Flow, listen, start
from crewai_tools import MCPServerAdapter
from mcp import StdioServerParameters

from research.schemas import (
    Platform,
    URLBuckets,
    SpecialistOutput,
    ResearchFlowState,
)
from research.llm_factory import create_llm
from research.search_tools import FireCrawlSearcher, StagehandBrowser
from research.config import Config

logger = logging.getLogger(__name__)


def brightdata_server_params() -> StdioServerParameters:
    """BrightData MCP 服务器参数"""
    token = Config.BRIGHT_DATA_API_TOKEN
    if not token:
        raise RuntimeError("BRIGHT_DATA_API_TOKEN is not set")
    return StdioServerParameters(
        command="npx",
        args=["@brightdata/mcp"],
        env={"API_TOKEN": token, "PRO_MODE": "true"},
    )


class DeepResearchFlow(Flow[ResearchFlowState]):
    """
    四步 Flow：
    1. start_flow       → 接收用户 query
    2. collect_urls      → BrightData MCP 多平台搜索 + FireCrawl 补充
    3. dispatch_to_specialists → 按平台分发 Specialist Agent 提取内容
    4. synthesize_response     → 综合所有结果生成结构化报告
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.search_llm = create_llm("search")
        self.specialist_llm = create_llm("specialist")
        self.response_llm = create_llm("response")
        self.firecrawl = FireCrawlSearcher()
        self.stagehand = StagehandBrowser()

    # ────────────────── Step 1 ──────────────────
    @start()
    def start_flow(self) -> Dict[str, Any]:
        logger.info(f"[Step 1] Research started: {self.state.query}")
        return {"query": self.state.query}

    # ────────────────── Step 2 ──────────────────
    @listen(start_flow)
    def collect_urls(self) -> Dict[str, Any]:
        """
        主搜索：BrightData MCP
        补充搜索：FireCrawl（当 BrightData 的 web 结果不足 2 条时自动触发）
        """
        logger.info("[Step 2] Collecting URLs from BrightData MCP...")
        url_buckets = URLBuckets()

        # ── 2a: BrightData MCP 搜索 ──
        try:
            with MCPServerAdapter(brightdata_server_params()) as mcp_tools:
                search_agent = Agent(
                    role="Multiplatform Web Discovery Specialist",
                    goal=(
                        "Identify and return a JSON object of public, relevant links "
                        "grouped by platform: instagram, linkedin, youtube, x, web."
                    ),
                    backstory=(
                        "Expert web researcher. Verify all links are public and relevant. "
                        "No duplicates, no fabrication. Empty list for no results."
                    ),
                    tools=[mcp_tools["search_engine"]],
                    llm=self.search_llm,
                )

                search_task = Task(
                    description=f"""
Collect public URLs for: "{self.state.query}"

Return ONLY JSON matching URLBuckets schema:
["instagram","linkedin","youtube","x","web"], each a list of HTTPS URLs.

Rules:
- instagram: instagram.com/*
- linkedin: linkedin.com/*
- youtube: youtube.com/*
- x: x.com/* or twitter.com/*
- web: article/blog pages only (exclude landing pages and above domains)
- Max 3 URLs per platform, ordered by relevance.
- Empty list [] if nothing found.
- Pure JSON, no commentary.
""",
                    agent=search_agent,
                    output_pydantic=URLBuckets,
                    expected_output="Strict JSON for URLBuckets.",
                )

                crew = Crew(agents=[search_agent], tasks=[search_task], verbose=True)
                result = crew.kickoff()

                # CrewAI kickoff 返回的是 CrewOutput，提取 pydantic 对象
                if hasattr(result, "pydantic") and result.pydantic:
                    url_buckets = result.pydantic
                elif hasattr(result, "raw"):
                    raw = result.raw if isinstance(result.raw, str) else json.dumps(result.raw)
                    url_buckets = URLBuckets.model_validate_json(raw)

        except Exception as e:
            logger.error(f"BrightData MCP failed: {e}")

        # ── 2b: FireCrawl 补充搜索 ──
        if len(url_buckets.web) < 2 and self.firecrawl.available:
            logger.info("[Step 2b] FireCrawl supplement search...")
            fc_results = self.firecrawl.search(self.state.query, limit=5)
            if fc_results:
                # 从 FireCrawl 结果中提取 URL
                for line in fc_results.split("\n"):
                    if line.startswith("URL: ") and len(url_buckets.web) < 5:
                        extracted_url = line.replace("URL: ", "").strip()
                        if extracted_url and extracted_url not in url_buckets.web:
                            url_buckets.web.append(extracted_url)

        total = sum(
            len(getattr(url_buckets, p))
            for p in ["instagram", "linkedin", "youtube", "x", "web"]
        )
        logger.info(f"[Step 2] Collected {total} URLs total")

        return {"url_buckets": url_buckets.model_dump()}

    # ────────────────── Step 3 ──────────────────
    @listen(collect_urls)
    def dispatch_to_specialists(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """按平台分发 Specialist Agent 提取内容"""
        logger.info("[Step 3] Dispatching to platform specialists...")
        results: List[SpecialistOutput] = []
        url_buckets = inputs["url_buckets"]

        for platform, urls in url_buckets.items():
            if not urls:
                continue

            logger.info(f"  Processing {platform}: {len(urls)} URLs")

            try:
                specialist_results = self._process_platform(platform, urls)
                results.extend(specialist_results)
            except Exception as e:
                logger.error(f"  {platform} specialist failed: {e}")
                results.append(
                    SpecialistOutput(
                        platform=platform,
                        url=urls[0] if urls else "unknown",
                        summary=f"Error processing {platform}: {e}",
                        metadata={"error": str(e)},
                    )
                )

        logger.info(f"[Step 3] Got {len(results)} specialist outputs")
        return {"specialist_results": [r.model_dump() for r in results]}

    def _process_platform(
        self, platform: str, urls: List[str]
    ) -> List[SpecialistOutput]:
        """处理单个平台的 URLs"""
        if not urls:
            return []

        # 对于 web 平台，优先尝试 FireCrawl 直接抓取
        if platform == "web" and self.firecrawl.available:
            return self._process_web_with_firecrawl(urls)

        # 其他平台用 BrightData MCP Specialist
        try:
            return self._process_with_brightdata(platform, urls)
        except Exception as e:
            logger.warning(f"BrightData specialist failed for {platform}, trying FireCrawl: {e}")
            if self.firecrawl.available:
                return self._process_web_with_firecrawl(urls)
            return []

    def _process_with_brightdata(
        self, platform: str, urls: List[str]
    ) -> List[SpecialistOutput]:
        """使用 BrightData MCP 处理特定平台"""
        with MCPServerAdapter(brightdata_server_params()) as mcp_tools:
            tools_map = {
                "instagram": "web_data_instagram_posts",
                "linkedin": "web_data_linkedin_posts",
                "youtube": "web_data_youtube_videos",
                "x": "web_data_x_posts",
                "web": "scrape_as_markdown",
            }
            tool_name = tools_map.get(platform, "scrape_as_markdown")

            agent = Agent(
                role=f"{platform.capitalize()} Research Specialist",
                goal=f"Extract key facts and insights from {platform} content.",
                backstory="Deep-research specialist. Accurate, no speculation.",
                tools=[mcp_tools[tool_name]],
                llm=self.specialist_llm,
            )

            task = Task(
                description=f"""
Process these {platform} URLs: {urls}
- Use tools to fetch content.
- Summarize in 300-500 words with bullet points.
- Return JSON: {{"platform":"{platform}","url":"<url>","summary":"<summary>","metadata":{{}}}}
""",
                agent=agent,
                output_pydantic=SpecialistOutput,
                expected_output="Strict JSON for SpecialistOutput.",
            )

            crew = Crew(agents=[agent], tasks=[task], verbose=True)
            result = crew.kickoff()

            if hasattr(result, "pydantic") and result.pydantic:
                return [result.pydantic]

            return [
                SpecialistOutput(
                    platform=platform,
                    url=urls[0],
                    summary=str(result.raw) if hasattr(result, "raw") else str(result),
                )
            ]

    def _process_web_with_firecrawl(self, urls: List[str]) -> List[SpecialistOutput]:
        """使用 FireCrawl 抓取网页内容"""
        results = []
        for url in urls[:3]:  # 限制最多 3 个
            content = self.firecrawl.scrape_url(url)
            if content:
                # 截取前 2000 字作为摘要输入
                truncated = content[:2000]
                results.append(
                    SpecialistOutput(
                        platform="web",
                        url=url,
                        summary=truncated,
                        metadata={"source": "firecrawl", "full_length": len(content)},
                    )
                )
        return results

    # ────────────────── Step 4 ──────────────────
    @listen(dispatch_to_specialists)
    def synthesize_response(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """综合所有 Specialist 结果，生成结构化研究报告"""
        logger.info("[Step 4] Synthesizing final response...")

        specialist_data = inputs["specialist_results"]

        # 构建对话历史上下文（支持多轮追问）
        history_context = ""
        if self.state.conversation_history:
            history_lines = []
            for msg in self.state.conversation_history[-6:]:  # 最近 3 轮
                history_lines.append(f"{msg['role']}: {msg['content'][:500]}")
            history_context = f"\n\nPrevious conversation:\n" + "\n".join(history_lines)

        response_agent = Agent(
            role="Deep Research Synthesis Specialist",
            goal=(
                "Synthesize research findings into a comprehensive, well-structured "
                "markdown response that directly answers the user's query."
            ),
            backstory=(
                "Expert research analyst. Create clear, actionable, well-sourced reports."
            ),
            llm=self.response_llm,
        )

        response_task = Task(
            description=f"""
Original Query: "{self.state.query}"
{history_context}

Research Findings:
{json.dumps(specialist_data, ensure_ascii=False, indent=2)}

Create a comprehensive markdown response:
1. **Executive Summary** (2-3 key points)
2. **Detailed Findings** (organized by topic, with bullet points)
3. **Key Insights & Implications**
4. **Sources & References** (with links)

Requirements:
- Answer in the SAME LANGUAGE as the user's query.
- If the query is in Chinese, respond in Chinese.
- Be comprehensive yet readable (~800-1500 words).
- Include source URLs where available.
""",
            expected_output="Comprehensive markdown research report.",
            agent=response_agent,
            markdown=True,
        )

        crew = Crew(agents=[response_agent], tasks=[response_task], verbose=True)
        final_result = crew.kickoff()

        result_text = str(final_result.raw) if hasattr(final_result, "raw") else str(final_result)
        self.state.final_response = result_text

        logger.info("[Step 4] Research complete!")
        return {"result": result_text, "sources_count": len(specialist_data)}


# ────────────────── 独立运行入口 ──────────────────
async def run_research(query: str, history: List[Dict[str, str]] = None) -> Dict[str, Any]:
    """供外部调用的入口函数"""
    flow = DeepResearchFlow()
    flow.state.query = query
    if history:
        flow.state.conversation_history = history

    payload = await flow.kickoff_async()
    return payload