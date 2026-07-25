import functools
import json
import time
from collections.abc import Callable
from typing import Any, cast

import redis

from app.core.config import settings

# Initialize Redis client if URL is provided
redis_client: redis.Redis | None = None
if settings.REDIS_URL:
    redis_client = redis.Redis.from_url(settings.REDIS_URL, decode_responses=True)

# In-Memory fallback cache
# Schema: {key: (serialized_value, expire_at_timestamp)}
_local_cache: dict[str, tuple[str, float]] = {}


def get_cache(key: str) -> str | None:
    if redis_client:
        try:
            return cast(str | None, redis_client.get(key))
        except Exception:
            return None
    else:
        if key in _local_cache:
            val, expire_at = _local_cache[key]
            if expire_at > time.time():
                return val
            else:
                _local_cache.pop(key, None)
        return None


def set_cache(key: str, value: str, ttl: int = 3600) -> None:
    if redis_client:
        try:
            redis_client.set(key, value, ex=ttl)
        except Exception:
            pass
    else:
        _local_cache[key] = (value, time.time() + ttl)


def invalidate_cache(pattern: str) -> None:
    """
    Invalidate all keys matching the pattern.
    pattern should be prefix-based, e.g., 'products:list:*' or 'products:detail:123'
    """
    full_pattern = f"antigravity:{pattern}"
    if redis_client:
        try:
            keys = cast(list[str], redis_client.keys(full_pattern))
            if keys:
                redis_client.delete(*keys)
        except Exception:
            pass
    else:
        # In-memory index matching
        # Convert glob * to startswith check
        if full_pattern.endswith("*"):
            prefix = full_pattern[:-1]
            to_remove = [k for k in _local_cache if k.startswith(prefix)]
        else:
            to_remove = [k for k in _local_cache if k == full_pattern]

        for k in to_remove:
            _local_cache.pop(k, None)


def serialize_cache_value(value: Any) -> str:
    from fastapi.encoders import jsonable_encoder

    return json.dumps(jsonable_encoder(value))


def cached(prefix: str, ttl: int = 3600) -> Callable[..., Any]:
    """
    Caching decorator for FastAPI endpoints.
    Prefixes the key as 'antigravity:{prefix}:...'
    Skips the 'db' parameter when constructing keys.
    """

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        @functools.wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            # Construct a unique cache key based on inputs
            key_parts = [f"antigravity:{prefix}"]

            for arg in args:
                if hasattr(arg, "id"):
                    key_parts.append(str(arg.id))
                elif isinstance(arg, int | str | float | bool):
                    key_parts.append(str(arg))

            for k, v in sorted(kwargs.items()):
                if k not in ("db", "request", "response") and v is not None:
                    # If parameter is a Pydantic model
                    if hasattr(v, "model_dump"):
                        # Serialize it or skip it
                        continue
                    key_parts.append(str(v))

            cache_key = ":".join(key_parts)

            # Try to fetch from cache
            val = get_cache(cache_key)

            request = kwargs.get("request")
            response = kwargs.get("response")

            if val is not None:
                try:
                    import hashlib

                    etag = f'W/"{hashlib.md5(val.encode()).hexdigest()}"'

                    if response:
                        response.headers["ETag"] = etag
                        response.headers["Cache-Control"] = f"public, max-age={ttl}"

                    if request:
                        if_none_match = request.headers.get("If-None-Match")
                        if if_none_match == etag:
                            from fastapi import Response as FastapiResponse

                            return FastapiResponse(status_code=304)

                    return json.loads(val)
                except Exception:
                    pass

            # Execute the function
            result = await func(*args, **kwargs)

            # Cache the result
            try:
                serialized = serialize_cache_value(result)
                set_cache(cache_key, serialized, ttl=ttl)

                if response:
                    import hashlib

                    etag = f'W/"{hashlib.md5(serialized.encode()).hexdigest()}"'
                    response.headers["ETag"] = etag
                    response.headers["Cache-Control"] = f"public, max-age={ttl}"
            except Exception:
                pass

            return result

        return wrapper

    return decorator
