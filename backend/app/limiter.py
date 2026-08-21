import collections
import logging
import time
from typing import Callable, Optional
from fastapi import HTTPException, Request, status

from app.config import settings

logger = logging.getLogger(__name__)

# In-memory sliding window fallback store: {key: [timestamp1, timestamp2, ...]}
_in_memory_store: dict[str, list[float]] = collections.defaultdict(list)


class RateLimiter:
    """
    Distributed Redis-backed sliding window rate limiter with graceful in-memory fallback.
    """

    def __init__(self):
        self._redis_client = None
        self._redis_tested = False

    async def get_redis(self):
        if self._redis_client is not None:
            return self._redis_client

        redis_url = (settings.REDIS_URL or "").strip()
        if not redis_url:
            return None

        try:
            import redis.asyncio as aioredis
            client = aioredis.from_url(
                redis_url,
                encoding="utf-8",
                decode_responses=True,
                socket_timeout=2.0,
                socket_connect_timeout=2.0,
            )
            await client.ping()
            self._redis_client = client
            logger.info("Connected to Redis rate-limiting cluster successfully.")
            return self._redis_client
        except Exception as err:
            if not self._redis_tested:
                logger.warning(
                    "Redis rate limiter connection failed (%s), falling back to in-memory window: %s",
                    type(err).__name__,
                    err,
                )
                self._redis_tested = True
            return None

    async def is_allowed(self, key: str, limit: int, window_seconds: int) -> tuple[bool, int]:
        """
        Evaluates sliding window limit for given key.
        Returns (is_allowed, retry_after_seconds).
        """
        now = time.time()
        window_start = now - window_seconds

        redis = await self.get_redis()
        if redis:
            try:
                pipe = redis.pipeline()
                pipe.zremrangebyscore(key, 0, window_start)
                pipe.zcard(key)
                pipe.zadd(key, {str(now): now})
                pipe.expire(key, window_seconds + 5)
                results = await pipe.execute()

                current_count = results[1]
                if current_count >= limit:
                    # Remove the timestamp we just added since it exceeded limit
                    await redis.zrem(key, str(now))
                    return False, int(window_seconds)
                return True, 0
            except Exception as err:
                logger.warning("Redis rate check error: %s. Using in-memory fallback.", err)

        # In-memory sliding window fallback
        timestamps = _in_memory_store[key]
        _in_memory_store[key] = [t for t in timestamps if t > window_start]

        if len(_in_memory_store[key]) >= limit:
            oldest = _in_memory_store[key][0]
            retry_after = max(1, int(oldest + window_seconds - now))
            return False, retry_after

        _in_memory_store[key].append(now)
        return True, 0


limiter = RateLimiter()


def rate_limit(limit_count: int = 15, window_seconds: int = 60, tag: str = "default") -> Callable:
    """
    FastAPI dependency generating sliding-window rate limit checks per client IP.
    """
    async def dependency(request: Request):
        client_ip = (
            request.headers.get("x-forwarded-for", "").split(",")[0].strip()
            or getattr(request.client, "host", "127.0.0.1")
        )
        rate_key = f"ratelimit:{client_ip}:{tag}"

        allowed, retry_after = await limiter.is_allowed(rate_key, limit_count, window_seconds)
        if not allowed:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Rate limit exceeded: max {limit_count} requests per {window_seconds}s. Try again in {retry_after}s.",
                headers={"Retry-After": str(retry_after)},
            )

    return dependency
