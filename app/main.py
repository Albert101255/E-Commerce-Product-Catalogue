import logging
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.exc import SQLAlchemyError

from app.api.v1.api import api_router
from app.core.config import settings
from app.core.monitoring import (
    init_sentry,
    metrics_endpoint,
    prometheus_middleware,
    setup_logging,
)
from app.core.rate_limit import rate_limiting_middleware
from app.core.security_headers import security_headers_middleware

# Initialize Monitoring & Logging
init_sentry()
setup_logging()

logger = logging.getLogger("app")

app = FastAPI(
    title="Apex Commerce API",
    openapi_url=None,
    docs_url=None,
    redoc_url=None,
)

# Register CORS Middleware
if settings.BACKEND_CORS_ORIGINS:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[str(origin) for origin in settings.BACKEND_CORS_ORIGINS],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

# Register Prometheus request tracking middleware
app.middleware("http")(prometheus_middleware)

# Register Security Headers middleware
app.middleware("http")(security_headers_middleware)

# Register Rate Limiting middleware
app.middleware("http")(rate_limiting_middleware)


@app.exception_handler(SQLAlchemyError)
async def sqlalchemy_exception_handler(
    request: Request, exc: SQLAlchemyError
) -> JSONResponse:
    """
    Handle database exceptions by logging them in JSON format.
    """
    logger.error("Database exception occurred", exc_info=exc)
    return JSONResponse(
        status_code=500,
        content={"detail": "Database error occurred."},
    )


@app.get("/health", tags=["health"])
async def health_check() -> dict[str, str]:
    """
    Basic health check endpoint returning 200 OK.
    """
    return {"status": "ok", "project": settings.PROJECT_NAME}


@app.get("/metrics", tags=["monitoring"])
def get_metrics() -> Any:
    """
    Prometheus metrics endpoint.
    """
    return metrics_endpoint()


# Mount static files
STATIC_DIR = Path(__file__).parent.parent / "static"
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

    @app.get("/", include_in_schema=False)
    async def serve_frontend() -> FileResponse:
        return FileResponse(str(STATIC_DIR / "index.html"))

    @app.get("/products", include_in_schema=False)
    async def serve_products() -> FileResponse:
        return FileResponse(str(STATIC_DIR / "products.html"))

    @app.get("/orders", include_in_schema=False)
    async def serve_orders_page() -> FileResponse:
        return FileResponse(str(STATIC_DIR / "orders.html"))

    @app.get("/tracking", include_in_schema=False)
    async def serve_tracking_page() -> FileResponse:
        return FileResponse(str(STATIC_DIR / "tracking.html"))


app.include_router(api_router, prefix=settings.API_V1_STR)
