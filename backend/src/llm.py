import json
import os
from datetime import datetime

from groq import Groq

MODEL_NAME = "llama-3.3-70b-versatile"
SEARCH_MODEL_NAME = "compound-beta"

# How many prior chat turns to feed back into the model as memory.
MAX_HISTORY_MESSAGES = 8

STYLE_RULE = (
    "Write in plain text: no emoji, and no em dashes (use a comma or period "
    "instead)."
)

SYSTEM_PROMPT = (
    "You are a helpful assistant chatting with the user about their uploaded "
    "documents. Answer using the provided context and the earlier conversation. "
    "Resolve follow-up references (like \"it\", \"she\", \"that\") from the "
    "conversation so far. If the answer is not in the context or the "
    "conversation, respond exactly with \"I don't know.\" Do not use outside "
    "knowledge. " + STYLE_RULE
)

WEB_SYSTEM_PROMPT = (
    "You are a helpful assistant chatting with the user. You may be given "
    "context extracted from the user's uploaded document, the earlier "
    "conversation, and you have live web search available for anything current "
    "or external to that document (e.g. today's job market, current trends, "
    "prices, or news). Use the conversation so far to resolve follow-up "
    "references. Ground document-specific facts in the provided context, and "
    "use web search for anything current or not covered by it. " + STYLE_RULE
)

MARKET_KEYWORDS = ("market",)


def needs_web_search(question: str) -> bool:
    lowered = question.lower()
    return any(keyword in lowered for keyword in MARKET_KEYWORDS)


def _get_client() -> Groq:
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        raise RuntimeError("GROQ_API_KEY is not set. Add it to your .env file.")
    return Groq(api_key=api_key)


def _history_messages(history: list[dict] | None) -> list[dict]:
    """Turn recent chat turns into Groq messages, capped to the last few turns."""
    if not history:
        return []
    recent = history[-MAX_HISTORY_MESSAGES:]
    return [{"role": turn["role"], "content": turn["content"]} for turn in recent]


def answer_question(
    question: str, context_chunks: list[str], history: list[dict] | None = None
) -> str:
    context = "\n\n---\n\n".join(context_chunks)
    user_prompt = f"Context:\n{context}\n\nQuestion: {question}"

    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    messages += _history_messages(history)
    messages.append({"role": "user", "content": user_prompt})

    client = _get_client()
    response = client.chat.completions.create(
        model=MODEL_NAME,
        messages=messages,
        temperature=0,
    )
    return response.choices[0].message.content


def generate_title(question: str, answer: str) -> str:
    """A short, topic-based chat title (e.g. "Invoice data summary"), not
    just the user's literal first message — "hi" isn't a useful title even
    though it's a perfectly fine thing to say."""
    prompt = (
        "Summarize what this conversation is about in a short chat title: "
        "3 to 6 words, title case, no quotes, no trailing punctuation.\n\n"
        f"User: {question}\nAssistant: {answer}\n\nTitle:"
    )
    client = _get_client()
    response = client.chat.completions.create(
        model=MODEL_NAME,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.3,
        max_tokens=20,
    )
    title = (response.choices[0].message.content or "").strip().strip('"')
    return title[:48]


def _extract_search_trace(message) -> dict:
    """Pull the actual web searches the model ran out of the compound-beta
    response: the exact queries, and the ranked sources (title, url, relevance
    score) it read. This is what turns the feature from a black box into
    something the user can verify."""
    queries: list[str] = []
    sources: dict[str, dict] = {}  # keyed by url, so duplicates collapse

    for tool in getattr(message, "executed_tools", None) or []:
        raw_args = getattr(tool, "arguments", None)
        if raw_args:
            try:
                query = json.loads(raw_args).get("query")
            except (ValueError, TypeError):
                query = None
            if query and query not in queries:
                queries.append(query)

        results = getattr(tool.search_results, "results", None) if tool.search_results else None
        for result in results or []:
            url = result.url
            score = getattr(result, "score", None)
            if url in sources:
                if score is not None and (sources[url]["score"] or 0) < score:
                    sources[url]["score"] = score
            else:
                sources[url] = {"title": result.title, "url": url, "score": score}

    ranked = sorted(sources.values(), key=lambda s: s["score"] or 0, reverse=True)[:8]
    return {"queries": queries, "sources": ranked}


def answer_with_web_search(
    question: str, context_chunks: list[str], history: list[dict] | None = None
) -> tuple[str, dict]:
    if context_chunks:
        context = "\n\n---\n\n".join(context_chunks)
        user_prompt = f"Document context:\n{context}\n\nQuestion: {question}"
    else:
        user_prompt = question

    messages = [{"role": "system", "content": WEB_SYSTEM_PROMPT}]
    messages += _history_messages(history)
    messages.append({"role": "user", "content": user_prompt})

    client = _get_client()
    response = client.chat.completions.create(
        model=SEARCH_MODEL_NAME,
        messages=messages,
        temperature=0,
    )
    searched_at = datetime.now()
    message = response.choices[0].message

    trace = _extract_search_trace(message)
    trace["searched_at"] = searched_at
    return message.content, trace
