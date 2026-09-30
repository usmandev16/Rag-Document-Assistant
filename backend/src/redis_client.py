import os
from urllib.parse import quote

import redis.asyncio as aioredis

_password = os.environ.get("REDIS_PASSWORD", "")
_auth = f":{quote(_password, safe='')}@" if _password else ""

# One URL for everything: Celery broker + result backend, chats, rate limits.
REDIS_URL = f"redis://{_auth}{os.environ.get('REDIS_HOST', 'localhost')}:{os.environ.get('REDIS_PORT', '6379')}/0"

redis = aioredis.from_url(REDIS_URL, decode_responses=True)
