import json
import uuid
from datetime import datetime, timedelta

from src.redis_client import redis

# Redis layout (shared by every API worker, so no lost writes between them):
#   chat:{id}             hash  id, session_id, title, created_at, updated_at
#   chat:{id}:msgs        list  JSON messages (RPUSH = atomic append)
#   session:{sid}:chats   set   chat ids owned by that session
#   chats:updated         zset  chat id -> updated_at timestamp (stale sweep)
NEW_TITLE = "New chat"
UPDATED = "chats:updated"


def _key(chat_id: str) -> str:
    return f"chat:{chat_id}"


def _msgs_key(chat_id: str) -> str:
    return f"chat:{chat_id}:msgs"


def _session_key(session_id: str) -> str:
    return f"session:{session_id}:chats"


async def _save_new(chat_id: str, session_id: str) -> dict:
    now = datetime.now()
    chat = {
        "id": chat_id,
        "session_id": session_id,
        "title": NEW_TITLE,
        "created_at": now.isoformat(),
        "updated_at": now.isoformat(),
    }
    async with redis.pipeline(transaction=True) as pipe:
        pipe.hset(_key(chat_id), mapping=chat)
        pipe.sadd(_session_key(session_id), chat_id)
        pipe.zadd(UPDATED, {chat_id: now.timestamp()})
        await pipe.execute()
    return chat


async def create_chat(session_id: str) -> dict:
    chat = await _save_new(uuid.uuid4().hex[:12], session_id)
    return {**chat, "messages": []}


async def list_chats(session_id: str) -> list[dict]:
    chat_ids = await redis.smembers(_session_key(session_id))
    if not chat_ids:
        return []
    async with redis.pipeline() as pipe:
        for chat_id in chat_ids:
            pipe.hgetall(_key(chat_id))
            pipe.lindex(_msgs_key(chat_id), -1)
        rows = await pipe.execute()

    result = []
    for chat, last_raw in zip(rows[::2], rows[1::2]):
        if not chat:
            continue
        last = json.loads(last_raw)["content"] if last_raw else "No messages yet."
        result.append({
            "id": chat["id"],
            "title": chat["title"],
            "updated_at": chat["updated_at"],
            "preview": last[:140] + ("..." if len(last) > 140 else ""),
        })
    result.sort(key=lambda c: c["updated_at"], reverse=True)
    return result


async def get_chat(chat_id: str) -> dict | None:
    chat = await redis.hgetall(_key(chat_id))
    if not chat:
        return None
    messages = await redis.lrange(_msgs_key(chat_id), 0, -1)
    return {**chat, "messages": [json.loads(m) for m in messages]}


async def owns_chat(chat_id: str, session_id: str) -> bool:
    return await redis.hget(_key(chat_id), "session_id") == session_id


async def needs_title(chat_id: str) -> bool:
    title = await redis.hget(_key(chat_id), "title")
    return title is None or title == NEW_TITLE


async def append_messages(
    chat_id: str,
    user_message: dict,
    assistant_message: dict,
    title: str | None = None,
    session_id: str | None = None,
) -> None:
    """Append a user/assistant turn to a chat, auto-titling it on the first
    turn. Pass `title` (e.g. an LLM-generated topic summary) when the caller
    has something better than the raw first question — "hi" makes a poor
    title even though it's a fine first message."""
    chat = await redis.hgetall(_key(chat_id)) or await _save_new(chat_id, session_id or "")

    now = datetime.now()
    fields = {"updated_at": now.isoformat()}
    if chat["title"] == NEW_TITLE:
        question = user_message["content"]
        fields["title"] = title or (question[:48] + ("..." if len(question) > 48 else ""))

    async with redis.pipeline(transaction=True) as pipe:
        pipe.rpush(_msgs_key(chat_id), json.dumps(user_message), json.dumps(assistant_message))
        pipe.hset(_key(chat_id), mapping=fields)
        pipe.zadd(UPDATED, {chat_id: now.timestamp()})
        await pipe.execute()


async def delete_chat(chat_id: str) -> None:
    session_id = await redis.hget(_key(chat_id), "session_id")
    async with redis.pipeline(transaction=True) as pipe:
        pipe.delete(_key(chat_id), _msgs_key(chat_id))
        pipe.zrem(UPDATED, chat_id)
        if session_id is not None:
            pipe.srem(_session_key(session_id), chat_id)
        await pipe.execute()


async def session_chat_ids(session_id: str) -> list[str]:
    return list(await redis.smembers(_session_key(session_id)))


async def stale_chat_ids(max_age_hours: float) -> list[str]:
    """Chats untouched for longer than max_age_hours — this is what actually
    makes "the data goes away after I leave" true, since a per-tab session id
    alone only hides other people's chats, it doesn't remove them."""
    cutoff = datetime.now() - timedelta(hours=max_age_hours)
    return await redis.zrangebyscore(UPDATED, "-inf", cutoff.timestamp())
