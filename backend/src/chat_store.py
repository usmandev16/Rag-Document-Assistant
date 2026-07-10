import json
import os
import uuid
from datetime import datetime, timedelta

# ponytail: single JSON file is plenty for one local user; move to sqlite
# if this ever needs concurrent multi-user access.
CHATS_FILE = "chats.json"


def _load() -> dict:
    if not os.path.exists(CHATS_FILE):
        return {}
    with open(CHATS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def _save(chats: dict) -> None:
    with open(CHATS_FILE, "w", encoding="utf-8") as f:
        json.dump(chats, f, indent=2)


def create_chat(session_id: str) -> dict:
    chats = _load()
    chat_id = uuid.uuid4().hex[:12]
    now = datetime.now().isoformat()
    chat = {
        "id": chat_id,
        "session_id": session_id,
        "title": "New chat",
        "created_at": now,
        "updated_at": now,
        "messages": [],
    }
    chats[chat_id] = chat
    _save(chats)
    return chat


def list_chats(session_id: str) -> list[dict]:
    chats = _load()
    result = []
    for chat in chats.values():
        if chat.get("session_id") != session_id:
            continue
        last = chat["messages"][-1]["content"] if chat["messages"] else "No messages yet."
        result.append({
            "id": chat["id"],
            "title": chat["title"],
            "updated_at": chat["updated_at"],
            "preview": last[:140] + ("..." if len(last) > 140 else ""),
        })
    result.sort(key=lambda c: c["updated_at"], reverse=True)
    return result


def get_chat(chat_id: str) -> dict | None:
    return _load().get(chat_id)


def owns_chat(chat_id: str, session_id: str) -> bool:
    chat = get_chat(chat_id)
    return chat is not None and chat.get("session_id") == session_id


def needs_title(chat_id: str) -> bool:
    chat = get_chat(chat_id)
    return chat is None or chat["title"] == "New chat"


def append_messages(
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
    chats = _load()
    chat = chats.get(chat_id)
    if chat is None:
        now = datetime.now().isoformat()
        chat = {
            "id": chat_id,
            "session_id": session_id,
            "title": "New chat",
            "created_at": now,
            "messages": [],
        }
        chats[chat_id] = chat

    if chat["title"] == "New chat":
        question = user_message["content"]
        chat["title"] = title or (question[:48] + ("..." if len(question) > 48 else ""))

    chat["messages"].append(user_message)
    chat["messages"].append(assistant_message)
    chat["updated_at"] = datetime.now().isoformat()
    _save(chats)


def delete_chat(chat_id: str) -> None:
    chats = _load()
    if chats.pop(chat_id, None) is not None:
        _save(chats)


def session_chat_ids(session_id: str) -> list[str]:
    chats = _load()
    return [c["id"] for c in chats.values() if c.get("session_id") == session_id]


def stale_chat_ids(max_age_hours: float) -> list[str]:
    """Chats untouched for longer than max_age_hours — this is what actually
    makes "the data goes away after I leave" true, since a per-tab session id
    alone only hides other people's chats, it doesn't remove them from disk."""
    cutoff = datetime.now() - timedelta(hours=max_age_hours)
    chats = _load()
    stale = []
    for chat in chats.values():
        try:
            updated_at = datetime.fromisoformat(chat["updated_at"])
        except (KeyError, ValueError):
            continue
        if updated_at < cutoff:
            stale.append(chat["id"])
    return stale
