import os
import time

from fastapi import HTTPException

from src.redis_client import redis

CHAT_RATE_LIMIT_PER_MINUTE = int(os.environ.get("CHAT_RATE_LIMIT_PER_MINUTE", "20"))
UPLOAD_RATE_LIMIT_PER_MINUTE = int(os.environ.get("UPLOAD_RATE_LIMIT_PER_MINUTE", "5"))
# 0 = no cap (usage is still tracked).
TOKEN_WINDOWS = {
    "hour": (3600, int(os.environ.get("TOKEN_LIMIT_PER_HOUR", "0"))),
    "day": (86400, int(os.environ.get("TOKEN_LIMIT_PER_DAY", "0"))),
}


def _too_many(what: str, retry_after: int) -> HTTPException:
    retry_after = max(retry_after, 1)
    return HTTPException(
        status_code=429,
        detail=f"{what} Try again in {retry_after}s.",
        headers={"Retry-After": str(retry_after)},
    )


async def hit(bucket: str, key: str, limit: int) -> None:
    """Count one request against `limit` per minute; 429 when over.

    ponytail: fixed 60s window — allows up to 2x `limit` across a window
    boundary. Swap to a sorted-set sliding window if bursts matter.
    """
    if limit <= 0:
        return
    now = int(time.time())
    rkey = f"rl:{bucket}:{key}:{now // 60}"
    async with redis.pipeline(transaction=True) as pipe:
        pipe.incr(rkey)
        pipe.expire(rkey, 60)
        count, _ = await pipe.execute()
    if count > limit:
        raise _too_many("Too many requests.", 60 - now % 60)


def _token_key(key: str, name: str, seconds: int, now: int) -> str:
    return f"tok:{name}:{key}:{now // seconds}"


async def check_tokens(key: str) -> None:
    """Approximate: checked before the LLM call, so the request that crosses
    the cap still completes."""
    now = int(time.time())
    for name, (seconds, limit) in TOKEN_WINDOWS.items():
        if limit <= 0:
            continue
        used = int(await redis.get(_token_key(key, name, seconds, now)) or 0)
        if used >= limit:
            raise _too_many(f"Token budget for this {name} used up.", seconds - now % seconds)


async def add_tokens(key: str, tokens: int) -> None:
    if tokens <= 0:
        return
    now = int(time.time())
    async with redis.pipeline(transaction=True) as pipe:
        for name, (seconds, _) in TOKEN_WINDOWS.items():
            tkey = _token_key(key, name, seconds, now)
            pipe.incrby(tkey, tokens)
            pipe.expire(tkey, seconds)
        await pipe.execute()


if __name__ == "__main__":
    # Self-check against a running Redis: `python -m src.rate_limit`
    import asyncio
    import uuid

    async def _demo() -> None:
        key = f"selfcheck-{uuid.uuid4().hex}"
        for _ in range(3):
            await hit("test", key, 3)
        try:
            await hit("test", key, 3)
        except HTTPException as exc:
            assert exc.status_code == 429 and 1 <= int(exc.headers["Retry-After"]) <= 60
        else:
            raise AssertionError("4th request should have been rate limited")
        print("rate limiter OK")

    asyncio.run(_demo())
