"""
FastAPI app factory and lifespan.
"""
from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response

from app.config import get_settings
from app.api.auth import router as auth_router
from app.api.documents import router as documents_router
from app.api.query import router as query_router
from app.api.admin import router as admin_router


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Startup: ensure local SQLite directory exists and tables are present."""
    from pathlib import Path
    from app.config import get_settings
    from app.db.base import Base
    from app.db.session import _engine
    from app.db import models  # noqa: F401 — register tables with Base.metadata

    settings = get_settings()
    if "sqlite" in settings.DATABASE_URL:
        path = settings.DATABASE_URL.replace("sqlite+aiosqlite:///", "").split("?")[0]
        if not path.startswith("/") and ":" not in path[:2]:
            data_dir = Path(path).parent
            data_dir.mkdir(parents=True, exist_ok=True)
    async with _engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="ARQIVE",
        description="AI-powered audit document intelligence",
        version="0.1.0",
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[settings.FRONTEND_URL],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(auth_router)
    app.include_router(documents_router)
    app.include_router(query_router)
    app.include_router(admin_router)

    @app.get("/")
    async def root() -> dict[str, str]:
        return {"message": "ARQIVE API", "docs": "/docs", "health": "/api/health"}

    @app.get("/favicon.ico", include_in_schema=False)
    async def favicon() -> Response:
        return Response(status_code=204)

    @app.get("/api/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/api/health/ready")
    async def ready() -> dict[str, str]:
        """Readiness: DB + Ollama."""
        checks = {}
        try:
            from sqlalchemy import text
            from app.db.session import _async_session_factory
            async with _async_session_factory() as s:
                await s.execute(text("SELECT 1"))
            checks["database"] = "ok"
        except Exception as e:
            checks["database"] = str(e)[:80]
        try:
            import httpx
            r = await httpx.AsyncClient(timeout=5).get("http://127.0.0.1:11434/api/tags")
            checks["ollama"] = "ok" if r.status_code == 200 else str(r.status_code)
        except Exception as e:
            checks["ollama"] = str(e)[:80]
        return checks

    return app


app = create_app()
