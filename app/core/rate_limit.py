import time
from typing import Any, cast

from fastapi import Request, Response

from app.core.cache import redis_client

# Local fallback store: {key: [timestamps]}
_local_limits: dict[str, list[float]] = {}
CLEANUP_INTERVAL = 300
_last_cleanup = time.time()


def check_rate_limit(key: str, limit: int = 100, window: int = 60) -> bool:
    """
    Check rate limit for a key. Returns True if request is allowed, False otherwise.
    """
    global _last_cleanup
    now = time.time()

    # Periodic cleanup of expired local limits
    if now - _last_cleanup > CLEANUP_INTERVAL:
        for k in list(_local_limits.keys()):
            _local_limits[k] = [t for t in _local_limits[k] if now - t < window]
            if not _local_limits[k]:
                del _local_limits[k]
        _last_cleanup = now

    if redis_client:
        try:
            redis_key = f"rate_limit:{key}"
            pipe = redis_client.pipeline()
            pipe.zremrangebyscore(redis_key, 0, now - window)
            pipe.zcard(redis_key)
            pipe.zadd(redis_key, {str(now): now})
            pipe.expire(redis_key, window)
            _, count, _, _ = pipe.execute()
            return int(count) < limit
        except Exception:
            pass

    # Local in-memory sliding window rate limiting
    if key not in _local_limits:
        _local_limits[key] = []

    _local_limits[key] = [t for t in _local_limits[key] if now - t < window]

    if len(_local_limits[key]) >= limit:
        return False

    _local_limits[key].append(now)
    return True


async def rate_limiting_middleware(request: Request, call_next: Any) -> Response:
    """
    Rate limiting middleware supporting IP-based and Token-based limits.
    """
    import os
    import sys

    if "pytest" in sys.modules and not os.environ.get("ENABLE_RATE_LIMIT"):
        return cast(Response, await call_next(request))

    auth = request.headers.get("Authorization")
    if auth and auth.startswith("Bearer "):
        token = auth.split(" ")[1]
        # Use last 12 chars of token for safety and uniqueness
        key = f"token:{token[-12:]}"
        limit = 100
    else:
        client_ip = request.client.host if request.client else "unknown"
        key = f"ip:{client_ip}"
        limit = 20

    path = request.url.path
    if (
        path.startswith("/metrics")
        or path.startswith("/docs")
        or path.startswith("/openapi.json")
    ):
        return cast(Response, await call_next(request))

    if not check_rate_limit(key, limit=limit, window=60):
        # To avoid starlette middleware swallowing HTTPExceptions, we can return
        # a JSONResponse directly.
        from fastapi.responses import JSONResponse

        return JSONResponse(
            status_code=429,
            content={"detail": "Too Many Requests. Rate limit exceeded."},
        )

    return cast(Response, await call_next(request))
