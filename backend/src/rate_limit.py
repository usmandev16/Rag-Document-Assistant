import os
import time

from fastapi import HTTPException, Request

from src.redis_client import redis

CHAT_RATE_LIMIT_PER_MINUTE = int(os.environ.get("CHAT_RATE_LIMIT_PER_MINUTE", "20"))
UPLOAD_RATE_LIMIT_PER_MINUTE = int(os.environ.get("UPLOAD_RATE_LIMIT_PER_MINUTE", "5"))
# Per client IP as well, since a client can make up a new session id at any
# time. Higher than the per-session limits: several people can share one IP.
CHAT_RATE_LIMIT_PER_IP_PER_MINUTE = int(os.environ.get("CHAT_RATE_LIMIT_PER_IP_PER_MINUTE", "60"))
UPLOAD_RATE_LIMIT_PER_IP_PER_MINUTE = int(os.environ.get("UPLOAD_RATE_LIMIT_PER_IP_PER_MINUTE", "15"))
# Load testing only (default off): no chat rate limits, so a load test
# measures the system rather than the limiter.
if os.environ.get("LOADTEST") == "1":
    CHAT_RATE_LIMIT_PER_MINUTE = CHAT_RATE_LIMIT_PER_IP_PER_MINUTE = 0
# Only trust X-Forwarded-For behind a proxy that sets it; otherwise any client
# could send a fake one to dodge the per-IP limit.
TRUSTED_PROXY = os.environ.get("TRUSTED_PROXY") == "1"
# LLM tokens for the whole service per UTC day, across all sessions (0 = off).
# The default stays under Groq's free-tier daily limit for gpt-oss-120b (200k).
DAILY_TOKEN_BUDGET = int(os.environ.get("DAILY_TOKEN_BUDGET", "180000"))
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

    fixed 60s window — allows up to 2x `limit` across a window
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


def client_ip(request: Request) -> str:
    if TRUSTED_PROXY:
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            # The proxy appends the address it saw, so the last entry is the
            # real client; earlier entries can be faked by the client.
            return forwarded.split(",")[-1].strip()
    return request.client.host if request.client else "unknown"


def _token_key(key: str, name: str, seconds: int, now: int) -> str:
    return f"tok:{name}:{key}:{now // seconds}"


def _global_key(now: int) -> str:
    # Separate prefix: a client can't pick a session id that collides with it.
    return f"tokglobal:day:{now // 86400}"


async def check_daily_budget() -> None:
    if DAILY_TOKEN_BUDGET <= 0:
        return
    now = int(time.time())
    if int(await redis.get(_global_key(now)) or 0) >= DAILY_TOKEN_BUDGET:
        raise HTTPException(
            status_code=503,
            detail="The service is busy: today's AI usage limit has been reached. Please try again tomorrow.",
            headers={"Retry-After": str(86400 - now % 86400)},
        )


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
        pipe.incrby(_global_key(now), tokens)
        pipe.expire(_global_key(now), 86400)
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
