"""
app/main.py
────────────
Application entry point.

Responsibilities
----------------
• Instantiate the FastAPI application.
• Register global exception handlers.
• Mount all API routers under the configured prefix.
• Wire startup / shutdown lifecycle events.
• Expose a health-check endpoint.
• Configure CORS.
"""
from __future__ import annotations

import time
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.routes import (
    auth_router,
    database_router,
    export_router,
    history_router,
    profile_router,
    query_router,
    fast_query_router,
    premium_ai_router,
)
from app.core.config import settings
from app.core.constants import (
    TAG_AUTH,
    TAG_DATABASE,
    TAG_EXPORT,
    TAG_HEALTH,
    TAG_HISTORY,
    TAG_PROFILE,
    TAG_QUERY,
)
from app.core.exceptions import register_exception_handlers
from app.core.logger import app_logger
from app.db.connectors.connection_manager import connection_manager
from app.db.session import init_db
from app.schemas.response_schema import HealthResponse

# ── Application start time ────────────────────────────────────────────────────
_APP_START: float = time.time()


# ══════════════════════════════════════════════════════════════════════════════
#  Lifespan (replaces deprecated on_event)
# ══════════════════════════════════════════════════════════════════════════════

@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Handle startup and shutdown lifecycle."""
    # ── Startup ───────────────────────────────────────────────────────────────
    app_logger.info("━━━ %s is starting ━━━", settings.APP_NAME)

    try:
        init_db()
        app_logger.info("Internal database initialised.")
    except Exception:
        app_logger.exception("Failed to initialise internal database!")
        raise

    app_logger.info(
        "%s ready | prefix=%s | debug=%s",
        settings.APP_NAME,
        settings.API_PREFIX,
        settings.DEBUG,
    )

    yield   # application is running

    # ── Shutdown ──────────────────────────────────────────────────────────────
    app_logger.info("Shutting down — disposing all database connections…")
    connection_manager.dispose_all()
    app_logger.info("━━━ %s stopped ━━━", settings.APP_NAME)


# ══════════════════════════════════════════════════════════════════════════════
#  FastAPI application factory
# ══════════════════════════════════════════════════════════════════════════════

def create_app() -> FastAPI:
    """Create and configure the FastAPI application instance."""

    _app = FastAPI(
        title=settings.APP_NAME,
        description=(
            "Production-ready REST API for AI-powered SQL database analysis. "
            "Supports MySQL and PostgreSQL with secure SELECT-only execution, "
            "dynamic schema introspection, query history, and CSV/Excel exports."
        ),
        version="1.0.0",
        docs_url=f"{settings.API_PREFIX}/docs",
        redoc_url=f"{settings.API_PREFIX}/redoc",
        openapi_url=f"{settings.API_PREFIX}/openapi.json",
        lifespan=lifespan,
        openapi_tags=[
            {"name": TAG_HEALTH,    "description": "Health & readiness checks."},
            {"name": TAG_AUTH,      "description": "User registration & authentication."},
            {"name": TAG_PROFILE,   "description": "User profile management."},
            {"name": TAG_DATABASE,  "description": "Database connection & schema inspection."},
            {"name": TAG_QUERY,     "description": "Secure SQL query execution."},
            {"name": TAG_EXPORT,    "description": "Export results to CSV / Excel."},
            {"name": TAG_HISTORY,   "description": "Query history management & replay."},
        ],
    )

    # ── CORS ──────────────────────────────────────────────────────────────────
    _app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ── Global exception handlers ─────────────────────────────────────────────
    register_exception_handlers(_app)

    # ── Routers ───────────────────────────────────────────────────────────────
    prefix = settings.API_PREFIX
    _app.include_router(auth_router,       prefix=prefix)
    _app.include_router(profile_router,    prefix=prefix)
    _app.include_router(database_router,   prefix=prefix)
    _app.include_router(query_router,      prefix=prefix)
    _app.include_router(fast_query_router, prefix=prefix)  # 🚀 Speed engine
    _app.include_router(premium_ai_router, prefix=prefix)  # ✨ Deep reasoning & reports
    _app.include_router(export_router,     prefix=prefix)
    _app.include_router(history_router,    prefix=prefix)

    # ── Root endpoint ─────────────────────────────────────────────────────────
    @_app.get("/", include_in_schema=False)
    def root() -> JSONResponse:
        return JSONResponse(
            {
                "app": settings.APP_NAME,
                "version": "1.0.0",
                "docs": f"{prefix}/docs",
                "health": f"{prefix}/health",
            }
        )

    # ── Health check ──────────────────────────────────────────────────────────
    @_app.get(
        f"{prefix}/health",
        response_model=HealthResponse,
        tags=[TAG_HEALTH],
        summary="Health check",
        description="Returns the application status and basic runtime metadata.",
    )
    def health_check() -> HealthResponse:
        return HealthResponse(
            status="ok",
            app_name=settings.APP_NAME,
            version="1.0.0",
            active_connections=connection_manager.active_count,
        )

    return _app


# ══════════════════════════════════════════════════════════════════════════════
#  Module-level app instance (used by uvicorn)
# ══════════════════════════════════════════════════════════════════════════════
app: FastAPI = create_app()
