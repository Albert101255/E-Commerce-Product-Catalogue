import json
import logging
import time
from typing import Any

import sentry_sdk
from fastapi import Request, Response
from prometheus_client import (
    CONTENT_TYPE_LATEST,
    Counter,
    Gauge,
    Histogram,
    generate_latest,
)
from sentry_sdk.integrations.fastapi import FastApiIntegration

from app.core.config import settings

# Prometheus Metrics
ORDER_COUNT = Counter(
    "antigravity_orders_total", "Total count of orders placed", ["status"]
)
CHECKOUT_LATENCY = Histogram(
    "antigravity_checkout_latency_seconds", "Checkout latency in seconds"
)
CART_ADDITIONS = Counter(
    "antigravity_cart_additions_total", "Total additions to shopping carts"
)
ACTIVE_SESSIONS = Gauge(
    "antigravity_active_sessions", "Estimated active customer sessions"
)

HTTP_REQUEST_LATENCY = Histogram(
    "antigravity_http_request_duration_seconds",
    "HTTP request duration in seconds",
    ["method", "path", "status"],
)


class JSONFormatter(logging.Formatter):
    """
    Formatter to output logs in structured JSON format.
    """

    def format(self, record: logging.LogRecord) -> str:
        log_data = {
            "timestamp": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "message": record.getMessage(),
            "module": record.module,
            "filename": record.filename,
            "line": record.lineno,
        }
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)
        return json.dumps(log_data)


def setup_logging() -> None:
    """
    Setup root logger with structured JSON logging formatting.
    """
    logger = logging.getLogger("app")
    logger.setLevel(logging.INFO)

    for handler in list(logger.handlers):
        logger.removeHandler(handler)

    handler = logging.StreamHandler()
    handler.setFormatter(JSONFormatter())
    logger.addHandler(handler)


def init_sentry() -> None:
    """
    Initialize Sentry SDK for error logging and tracing.
    """
    if settings.SENTRY_DSN:
        sentry_sdk.init(
            dsn=settings.SENTRY_DSN,
            integrations=[FastApiIntegration()],
            traces_sample_rate=1.0,
            profiles_sample_rate=1.0,
        )


async def prometheus_middleware(request: Request, call_next: Any) -> Response:
    """
    FastAPI middleware to measure HTTP request latency and update prometheus metrics.
    """
    start_time = time.perf_counter()
    method = request.method
    path = request.url.path

    # Keep active session counter updated
    if request.headers.get("Authorization"):
        ACTIVE_SESSIONS.inc()
        try:
            response: Response = await call_next(request)
        finally:
            ACTIVE_SESSIONS.dec()
    else:
        response = await call_next(request)

    latency = time.perf_counter() - start_time
    status = str(response.status_code)
    HTTP_REQUEST_LATENCY.labels(method=method, path=path, status=status).observe(
        latency
    )
    return response


def metrics_endpoint() -> Response:
    """
    Expose prometheus metrics endpoint.
    """
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)
