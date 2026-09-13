"""
Application entrypoint. Run with:
    uvicorn app.main:app --reload                 (dev)
    gunicorn app.main:app -k uvicorn.workers.UvicornWorker  (prod, see Dockerfile)
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.admin import router as admin_router
from app.api.auth import router as auth_router
from app.api.chat import router as chat_router
from app.api.deps import require_admin
from app.api.documents import router as documents_router
from app.api.knowledge_bases import router as knowledge_bases_router
from app.core.config import get_settings
from app.core.usage_logging import ApiUsageLoggingMiddleware
from app.db.session import engine

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("KnowledgeGPT API starting up (environment=%s)", settings.ENVIRONMENT)
    if settings.ENVIRONMENT == "production":
        from app.db.contract import check_embedding_contract
        async with engine.connect() as conn:
            await check_embedding_contract(conn, settings)
    yield
    logger.info("KnowledgeGPT API shutting down")
    from app.services.llm.factory import get_llm_provider
    if get_llm_provider.cache_info().currsize:
        await get_llm_provider().aclose()
        get_llm_provider.cache_clear()
    await engine.dispose()


app = FastAPI(
    title="KnowledgeGPT API",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(ApiUsageLoggingMiddleware)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    # Flattens Pydantic's nested error format into something a frontend form
    # can map straight to fields without walking `loc` arrays itself.
    errors = [{"field": ".".join(str(p) for p in e["loc"][1:]), "message": e["msg"]} for e in exc.errors()]
    return JSONResponse(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, content={"detail": errors})


@app.get("/health", tags=["system"])
async def health_check():
    """Liveness/readiness probe for the ALB target group and container
    orchestrator. Deliberately does NOT check the database/Redis here —
    that belongs in a separate /health/deep endpoint so a transient DB
    hiccup doesn't cause the orchestrator to kill and restart every
    container simultaneously."""
    return {"status": "ok", "service": "knowledgegpt-api"}


@app.get("/health/deep", tags=["system"])
async def deep_health_check(current_user=Depends(require_admin)):
    checks: dict[str, str] = {}

    try:
        from sqlalchemy import text

        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        checks["database"] = "ok"
    except Exception:  # noqa: BLE001
        checks["database"] = "unavailable"

    try:
        import redis.asyncio as redis

        client = redis.from_url(settings.REDIS_URL)
        await client.ping()
        await client.aclose()
        checks["redis"] = "ok"
    except Exception:  # noqa: BLE001
        checks["redis"] = "unavailable"

    try:
        import asyncio

        from app.services.llm.factory import get_llm_provider
        checks["provider"] = "ok" if await asyncio.wait_for(get_llm_provider().health_check(), timeout=10) else "unavailable"
    except Exception:
        checks["provider"] = "unavailable"
    overall_ok = all(v == "ok" for v in checks.values())
    return JSONResponse(
        status_code=status.HTTP_200_OK if overall_ok else status.HTTP_503_SERVICE_UNAVAILABLE,
        content={"status": "ok" if overall_ok else "degraded", "checks": checks},
    )


app.include_router(auth_router)
app.include_router(admin_router)
app.include_router(knowledge_bases_router)
app.include_router(documents_router)
app.include_router(chat_router)
