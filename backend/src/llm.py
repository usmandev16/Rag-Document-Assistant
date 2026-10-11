import asyncio
import json
import logging
import os
import random
import re
from datetime import datetime
from contextvars import ContextVar
from types import SimpleNamespace

from groq import AsyncGroq

# llama-3.3-70b-versatile and compound-beta aren't available on this Groq
# account; gpt-oss-120b handles both answers and (via its built-in
# browser_search tool) web search. Override with GROQ_MODEL in .env.
MODEL_NAME = os.environ.get("GROQ_MODEL", "openai/gpt-oss-120b")
WEB_SEARCH_TOOL = {"type": "browser_search"}

# browser_search answers cite inline like 【1†L4-L11】; the UI shows sources
# separately, so strip them.
_CITATION_RE = re.compile(r"【[^】]*】")

# How many prior chat messages to feed back into the model as memory. Kept
# small: the Groq free tier allows 8,000 tokens per minute.
MAX_HISTORY_MESSAGES = 4

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
    "knowledge. Only state values written in the sources. Never calculate or "
    "estimate a value the sources don't state; say you don't know instead. "
    "The context passages are numbered [1], [2], and so on. After "
    "each fact, cite the passage it came from by its number in square "
    "brackets, e.g. [2]. Cite only passages you actually used, never cite "
    "the conversation, and use no citations when you answer \"I don't know.\" "
    + STYLE_RULE
)

# Citation markers like [1] or [1, 3] in a model answer. gpt-oss often writes
# full-width 【1】 or browser-style 【1†L31-L38】 instead; accept all of them,
# and keep_cited rewrites them to plain [n].
CITATION_RE = re.compile(r"[\[【](\d+(?:\s*,\s*\d+)*)(?:†[^\]】]*)?[\]】]")

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


_client: AsyncGroq | None = None


def _get_client() -> AsyncGroq:
    # One shared async client, so concurrent requests reuse its connection pool.
    global _client
    if _client is None:
        api_key = os.environ.get("GROQ_API_KEY")
        if not api_key:
            raise RuntimeError("GROQ_API_KEY is not set. Add it to your .env file.")
        _client = AsyncGroq(api_key=api_key)
    return _client


def _tokens(response) -> int:
    return getattr(response.usage, "total_tokens", 0) or 0


# Own handler so the per-request token log shows under uvicorn and celery
# without turning on INFO logging for every library.
log = logging.getLogger("rag.llm")
if not log.handlers:
    _handler = logging.StreamHandler()
    _handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    log.addHandler(_handler)
    log.setLevel(logging.INFO)
    log.propagate = False


def estimate_tokens(text: str) -> int:
    """Rough token count, ~4 characters per token. Good enough to stay under
    the per-minute limit without pulling in a tokenizer dependency."""
    return len(text) // 4


# Load testing only (default off): every Groq call returns a fake reply after
# 1-2 s, so load tests measure this system without spending Groq tokens.
LLM_STUB = os.environ.get("LLM_STUB") == "1"
# Seconds the current request spent in stubbed LLM calls, so a load test can
# separate the system's own time from fake LLM time (see main.py).
stub_seconds: ContextVar[list[float] | None] = ContextVar("stub_seconds", default=None)


async def _stub_reply(kind: str, prompt: str) -> SimpleNamespace:
    delay = random.uniform(1.0, 2.0)
    await asyncio.sleep(delay)
    if (spent := stub_seconds.get()) is not None:
        spent[0] += delay  # any sleep overshoot from a busy event loop counts as system time
    if kind == "route":
        question = prompt.rsplit("Question:", 1)[-1]
        sheet_question = re.search(r"shipment|\bCOD\b", question, re.IGNORECASE)
        content = json.dumps({"route": "spreadsheet" if sheet_question else "documents"})
    elif kind == "plan":
        sheet = re.search(r"Sheet '(.+?)' \(", prompt).group(1)  # from sheets.describe_sheet
        content = json.dumps({"answerable": True, "sheet": sheet, "filters": [], "group_by": None,
                              "aggregate": {"column": None, "func": "count"}})
    elif kind == "title":
        content = "Load test chat"
    else:  # answer, sheet_answer, web_search
        content = "This is a stub answer based on the provided source [1]."
    message = SimpleNamespace(content=content, executed_tools=None)
    usage = SimpleNamespace(prompt_tokens=0, completion_tokens=0, total_tokens=0)
    return SimpleNamespace(choices=[SimpleNamespace(message=message)], usage=usage)


async def _create(kind: str, **kwargs):
    """Every Groq call goes through here so each request's token count is
    logged: an estimate before sending (so a 413 still leaves a record), and
    Groq's actual usage after."""
    if LLM_STUB:
        return await _stub_reply(kind, kwargs["messages"][-1]["content"])
    estimate = sum(estimate_tokens(m["content"]) for m in kwargs["messages"])
    log.info("groq %s request: ~%d input tokens (estimate)", kind, estimate)
    response = await _get_client().chat.completions.create(model=MODEL_NAME, **kwargs)
    usage = response.usage
    log.info(
        "groq %s usage: prompt=%s completion=%s total=%s",
        kind, usage.prompt_tokens, usage.completion_tokens, usage.total_tokens,
    )
    return response


def _history_messages(history: list[dict] | None) -> list[dict]:
    """Turn recent chat turns into Groq messages, capped to the last few turns."""
    if not history:
        return []
    recent = history[-MAX_HISTORY_MESSAGES:]
    # Old answers' [n] markers point at a previous turn's passages; strip them
    # so they can't be confused with this turn's numbering.
    return [{"role": turn["role"], "content": CITATION_RE.sub("", turn["content"])} for turn in recent]


async def answer_question(
    question: str, context_chunks: list[str], history: list[dict] | None = None
) -> tuple[str, int]:
    context = "\n\n---\n\n".join(f"[{i}] {chunk}" for i, chunk in enumerate(context_chunks, 1))
    user_prompt = f"Context:\n{context}\n\nQuestion: {question}"

    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    messages += _history_messages(history)
    messages.append({"role": "user", "content": user_prompt})

    response = await _create("answer", messages=messages, temperature=0)
    return response.choices[0].message.content, _tokens(response)


async def generate_title(question: str, answer: str) -> tuple[str, int]:
    """A short, topic-based chat title (e.g. "Invoice data summary"), not
    just the user's literal first message — "hi" isn't a useful title even
    though it's a perfectly fine thing to say."""
    prompt = (
        "Summarize what this conversation is about in a short chat title: "
        "3 to 6 words, title case, no quotes, no trailing punctuation.\n\n"
        f"User: {question}\nAssistant: {answer}\n\nTitle:"
    )
    response = await _create(
        "title",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.3,
        # gpt-oss reasons before it answers: a tight max_tokens (the old 20)
        # gets spent on reasoning and returns an empty title. Keep reasoning
        # low and the cap generous; the title is trimmed to 48 chars anyway.
        reasoning_effort="low",
        max_tokens=300,
    )
    title = (response.choices[0].message.content or "").strip().strip('"')
    return title[:48], _tokens(response)


def keep_cited(answer: str, passages: list) -> tuple[str, list]:
    """Keep only the passages the answer cites, renumbered 1..n in the order
    they're first cited, and rewrite the answer's markers to match — so the
    answer's [1] is the first entry in the sources list. Out-of-range markers
    are dropped."""
    order: list[int] = []
    for match in CITATION_RE.finditer(answer):
        for n in (int(x) for x in match.group(1).split(",")):
            if 1 <= n <= len(passages) and n not in order:
                order.append(n)
    renumber = {old: new for new, old in enumerate(order, 1)}

    def rewrite(match: re.Match) -> str:
        nums = [renumber[int(x)] for x in match.group(1).split(",") if int(x) in renumber]
        return "".join(f"[{n}]" for n in nums)

    answer = re.sub(r" +([.,;:])", r"\1", CITATION_RE.sub(rewrite, answer))
    return answer.strip(), [passages[n - 1] for n in order]


def _extract_search_trace(message) -> dict:
    """Pull the actual web searches the model ran out of the browser_search
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
            url = getattr(result, "url", None)
            if not url:
                continue  # page-open steps can carry page text without a url
            score = getattr(result, "score", None)
            if url in sources:
                if score is not None and (sources[url]["score"] or 0) < score:
                    sources[url]["score"] = score
            else:
                sources[url] = {"title": getattr(result, "title", None) or url, "url": url, "score": score}

    ranked = sorted(sources.values(), key=lambda s: s["score"] or 0, reverse=True)[:8]
    return {"queries": queries, "sources": ranked}


async def answer_with_web_search(
    question: str, context_chunks: list[str], history: list[dict] | None = None
) -> tuple[str, dict, int]:
    if context_chunks:
        context = "\n\n---\n\n".join(context_chunks)
        user_prompt = f"Document context:\n{context}\n\nQuestion: {question}"
    else:
        user_prompt = question

    messages = [{"role": "system", "content": WEB_SYSTEM_PROMPT}]
    messages += _history_messages(history)
    messages.append({"role": "user", "content": user_prompt})

    response = await _create("web_search", messages=messages, temperature=0, tools=[WEB_SEARCH_TOOL])
    searched_at = datetime.now()
    message = response.choices[0].message

    trace = _extract_search_trace(message)
    trace["searched_at"] = searched_at
    answer = _CITATION_RE.sub("", message.content or "").strip()
    return answer, trace, _tokens(response)
