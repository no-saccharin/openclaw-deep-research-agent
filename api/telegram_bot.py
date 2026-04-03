import os
import logging
from typing import List, Dict, Any
from urllib.parse import urlsplit, urlunsplit, urlencode

import httpx
from telegram import Update
from telegram.constants import ChatAction
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

from research.secrets import load_environment, read_secret

load_environment()
# ─────────────────────────────
# 基础配置
# ─────────────────────────────
logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger("telegram-bot")

logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)

TELEGRAM_BOT_TOKEN = read_secret("TELEGRAM_BOT_TOKEN")
TELEGRAM_ALLOWED_USERS_RAW = os.getenv("TELEGRAM_ALLOWED_USERS", "").strip()

RESEARCH_API_URL = os.getenv("RESEARCH_API_URL", "http://localhost:8088/research").strip()

# 允许用户白名单
ALLOWED_USERS = {
    int(x.strip())
    for x in TELEGRAM_ALLOWED_USERS_RAW.split(",")
    if x.strip().isdigit()
}

# 简单内存对话上下文
# 格式:
# {
#   user_id: [
#       {"role": "user", "content": "..."},
#       {"role": "assistant", "content": "..."}
#   ]
# }
USER_HISTORY: Dict[int, List[Dict[str, str]]] = {}

MAX_HISTORY_MESSAGES = 8


# ─────────────────────────────
# 工具函数
# ─────────────────────────────
def check_env():
    if not TELEGRAM_BOT_TOKEN:
        raise ValueError("TELEGRAM_BOT_TOKEN 未配置，请先在 .env 中填写。")


def is_user_allowed(user_id: int) -> bool:
    # 如果你没有配置白名单，默认允许所有人
    if not ALLOWED_USERS:
        return True
    return user_id in ALLOWED_USERS


def get_history(user_id: int) -> List[Dict[str, str]]:
    return USER_HISTORY.get(user_id, [])


def append_history(user_id: int, role: str, content: str):
    if user_id not in USER_HISTORY:
        USER_HISTORY[user_id] = []

    USER_HISTORY[user_id].append({"role": role, "content": content})

    # 截断上下文，避免无限增长
    if len(USER_HISTORY[user_id]) > MAX_HISTORY_MESSAGES:
        USER_HISTORY[user_id] = USER_HISTORY[user_id][-MAX_HISTORY_MESSAGES:]


def clear_history(user_id: int):
    USER_HISTORY[user_id] = []


async def call_research_api(
    query: str,
    conversation_history: List[Dict[str, str]],
    *,
    requester_user_id: int,
    requester_chat_id: int,
    requester_username: str | None,
) -> str:
    payload = {
        "query": query,
        "conversation_history": conversation_history,
        "requester_type": "telegram",
        "requester_user_id": requester_user_id,
        "requester_chat_id": requester_chat_id,
        "requester_username": requester_username,
    }

    async with httpx.AsyncClient(timeout=180.0) as client:
        resp = await client.post(RESEARCH_API_URL, json=payload)
        resp.raise_for_status()
        data = resp.json()

    if not data.get("success"):
        error_msg = data.get("error", "未知错误")
        return f"研究失败：{error_msg}"

    return data.get("result", "没有返回结果")


def build_history_api_url(user_id: int, limit: int) -> str:
    parsed = urlsplit(RESEARCH_API_URL)
    query = urlencode({"requester_user_id": user_id, "limit": limit})
    return urlunsplit((parsed.scheme, parsed.netloc, "/research/history", query, ""))


async def fetch_history(user_id: int, limit: int = 5) -> List[Dict[str, Any]]:
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.get(build_history_api_url(user_id=user_id, limit=limit))
        resp.raise_for_status()
        data = resp.json()
    return data.get("items", [])


def split_text(text: str, max_length: int = 3500) -> List[str]:
    """
    Telegram 单条消息长度有限，做分段发送。
    尽量按段落切分。
    """
    if len(text) <= max_length:
        return [text]

    chunks = []
    current = ""

    for paragraph in text.split("\n"):
        if len(current) + len(paragraph) + 1 <= max_length:
            current += paragraph + "\n"
        else:
            if current.strip():
                chunks.append(current.strip())
            # 如果单段本身超长，再硬切
            if len(paragraph) > max_length:
                for i in range(0, len(paragraph), max_length):
                    chunks.append(paragraph[i:i + max_length])
                current = ""
            else:
                current = paragraph + "\n"

    if current.strip():
        chunks.append(current.strip())

    return chunks


# ─────────────────────────────
# Telegram 命令处理
# ─────────────────────────────
async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not user:
        return

    if not is_user_allowed(user.id):
        await update.message.reply_text(
            f"你没有权限使用这个机器人。\n你的 user id: {user.id}"
        )
        return

    text = (
        "你好，我是 OpenClaw Deep Research Agent 🤖\n\n"
        "你可以直接给我发送研究任务，例如：\n"
        "1. 帮我调研最近 AI Agent 工程师岗位要求\n"
        "2. 帮我比较 OpenClaw、LangGraph、AutoGen\n"
        "3. 帮我总结某个网站上的产品信息\n\n"
        "可用命令：\n"
        "/help 查看帮助\n"
        "/clear 清空上下文\n"
        "/id 查看你的 Telegram user id\n"
        "/history 查看最近提问记录"
    )
    await update.message.reply_text(text)


async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not user:
        return

    if not is_user_allowed(user.id):
        await update.message.reply_text("你没有权限使用这个机器人。")
        return

    text = (
        "使用说明：\n\n"
        "直接发送你的问题即可，我会调用 Deep Research API 帮你做调研。\n\n"
        "示例：\n"
        "- 帮我调研本周 AI Agent 相关热门开源项目\n"
        "- 帮我比较 LangGraph 和 AutoGen 的优缺点\n"
        "- 帮我总结 https://xxx 网站上的产品功能\n\n"
        "命令：\n"
        "/clear 清空上下文\n"
        "/id 查看你的用户ID\n"
        "/history 查看最近提问记录"
    )
    await update.message.reply_text(text)


async def clear_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not user:
        return

    if not is_user_allowed(user.id):
        await update.message.reply_text("你没有权限使用这个机器人。")
        return

    clear_history(user.id)
    await update.message.reply_text("上下文已清空。")


async def id_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not user:
        return

    await update.message.reply_text(f"你的 Telegram user id 是：{user.id}")


async def history_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    message = update.message

    if not user or not message:
        return

    if not is_user_allowed(user.id):
        await message.reply_text("你没有权限使用这个机器人。")
        return

    limit = 5
    if context.args and context.args[0].isdigit():
        limit = max(1, min(int(context.args[0]), 10))

    try:
        items = await fetch_history(user.id, limit=limit)
    except httpx.HTTPStatusError as e:
        logger.exception("History API HTTP error")
        await message.reply_text(f"查询历史失败（HTTP {e.response.status_code}）。")
        return
    except httpx.RequestError:
        logger.exception("History API request error")
        await message.reply_text("历史服务无法连接，请检查 research API 是否启动。")
        return

    if not items:
        await message.reply_text("还没有查到你的历史记录。")
        return

    lines = ["最近研究记录："]
    for item in items:
        status = "成功" if item.get("success") else "失败"
        query = (item.get("query") or "")[:80]
        created_at = item.get("created_at", "")
        sources_count = item.get("sources_count", 0)
        duration_ms = item.get("duration_ms", 0)
        lines.append(
            f"#{item.get('id')} [{status}] {query}\n时间: {created_at}\n来源数: {sources_count} | 耗时: {duration_ms} ms"
        )

    await message.reply_text("\n\n".join(lines))


# ─────────────────────────────
# 主消息处理
# ─────────────────────────────
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    message = update.message

    if not user or not message or not message.text:
        return

    user_id = user.id
    user_text = message.text.strip()

    logger.info(f"收到消息 | user_id={user_id} | text={user_text[:100]}")

    if not is_user_allowed(user_id):
        await message.reply_text(
            f"你没有权限使用这个机器人。\n你的 user id: {user_id}"
        )
        return

    # 回复一个处理中状态
    processing_msg = await message.reply_text("收到，正在开始深度调研，请稍等...")

    try:
        await context.bot.send_chat_action(
            chat_id=message.chat_id,
            action=ChatAction.TYPING,
        )

        history = get_history(user_id)

        # 把用户当前问题先追加到历史里（给 API 用时，也可以只传旧历史，这里我建议传旧历史）
        result = await call_research_api(
            query=user_text,
            conversation_history=history,
            requester_user_id=user_id,
            requester_chat_id=message.chat_id,
            requester_username=user.username,
        )

        # 更新历史
        append_history(user_id, "user", user_text)
        append_history(user_id, "assistant", result[:4000])

        # 删除“处理中”提示
        try:
            await processing_msg.delete()
        except Exception:
            pass

        # 分段返回结果
        chunks = split_text(result, max_length=3500)
        for i, chunk in enumerate(chunks):
            prefix = ""
            if len(chunks) > 1:
                prefix = f"({i+1}/{len(chunks)})\n\n"
            await message.reply_text(prefix + chunk)

    except httpx.HTTPStatusError as e:
        logger.exception("Research API HTTP error")
        await processing_msg.edit_text(
            f"调用研究服务失败（HTTP {e.response.status_code}）。"
        )
    except httpx.RequestError as e:
        logger.exception("Research API request error")
        await processing_msg.edit_text(
            "研究服务无法连接，请检查 research API 是否启动。"
        )
    except Exception as e:
        logger.exception("Unhandled error")
        await processing_msg.edit_text(f"处理失败：{str(e)}")


# ─────────────────────────────
# 启动入口
# ─────────────────────────────
def main():
    check_env()

    logger.info("启动 Telegram Bot...")
    logger.info(f"Research API URL: {RESEARCH_API_URL}")
    logger.info(
        f"Allowed users: {sorted(list(ALLOWED_USERS)) if ALLOWED_USERS else 'ALL'}"
    )

    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start_cmd))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("clear", clear_cmd))
    app.add_handler(CommandHandler("id", id_cmd))
    app.add_handler(CommandHandler("history", history_cmd))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    logger.info("Telegram Bot 已启动，开始轮询...")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()