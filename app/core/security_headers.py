from typing import Any

from fastapi import Request, Response

# Paths that load external CDN resources (Swagger UI, ReDoc)
_CDN_PATHS = {"/docs", "/redoc"}


async def security_headers_middleware(request: Request, call_next: Any) -> Response:
    """
    Middleware to inject Helmet-like security headers into HTTP responses.
    Swagger UI (/docs) and ReDoc (/redoc) require relaxed CSP to load CDN assets.
    """
    response: Response = await call_next(request)
    response.headers["Strict-Transport-Security"] = (
        "max-age=63072000; includeSubDomains; preload"
    )
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"

    if request.url.path in _CDN_PATHS:
        # Swagger UI / ReDoc load scripts, styles, and fonts from CDN
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
            "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net https://fonts.googleapis.com; "
            "img-src 'self' data: https://fastapi.tiangolo.com; "
            "font-src 'self' https://fonts.gstatic.com; "
            "connect-src 'self'"
        )
    else:
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
            "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com https://fonts.gstatic.com; "
            "img-src 'self' data:; "
            "font-src 'self' https://fonts.gstatic.com; "
            "connect-src 'self'"
        )

    return response
