"""
Aletheon FastAPI application entrypoint — production-hardened.

Startup sequence:
  1. Configure structured logging (JSON or text, from LOG_FORMAT env var).
  2. Enforce HuggingFace offline env vars (safety net against transitive downloads).
  3. Verify required directories exist (data/, models/).
  4. Enable SQLite WAL mode for better concurrent-read performance.
  5. Load self-trained artifacts via ArtifactRegistry (entailment classifier, corpus index).

Middleware stack (applied in order, outermost first):
  FileSizeLimitMiddleware  → reject oversized uploads before body is read
  RequestIdMiddleware      → attach X-Request-ID to every request/response
  CORSMiddleware           → locked to CORS_ORIGINS (wildcard only in development)

Security:
  - Global exception handler sanitises all unhandled errors: logs full
    traceback internally, returns only {"error": "internal_server_error",
    "request_id": "..."} to the client.
  - Debug endpoints hidden in production (ENVIRONMENT=production).
  - File size limit enforced at middleware level (before body streaming).

No pretrained weights loaded. No model hub contacted.
"""
from __future__ import annotations

import logging
import uuid
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from app.config import settings
from app.logging_config import configure_logging, request_id_var

# ── Logging must be configured before any other import ───────────────────────
configure_logging(log_format=settings.LOG_FORMAT, log_level=settings.LOG_LEVEL)
logger = logging.getLogger(__name__)


# ── Middleware ────────────────────────────────────────────────────────────────

class RequestIdMiddleware(BaseHTTPMiddleware):
    """
    Attach a unique X-Request-ID to every request and response.
    The ID is stored in a context variable so it is available in log records.
    """
    async def dispatch(self, request: Request, call_next):
        rid = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        token = request_id_var.set(rid)
        try:
            response = await call_next(request)
            response.headers["X-Request-ID"] = rid
            return response
        finally:
            request_id_var.reset(token)


class FileSizeLimitMiddleware(BaseHTTPMiddleware):
    """
    Reject requests whose Content-Length exceeds MAX_UPLOAD_BYTES before
    the body is streamed. Protects against OOM from huge file uploads.
    """
    async def dispatch(self, request: Request, call_next):
        cl = request.headers.get("content-length")
        if cl and int(cl) > settings.MAX_UPLOAD_BYTES:
            limit_mb = settings.MAX_UPLOAD_BYTES // (1024 * 1024)
            return JSONResponse(
                status_code=413,
                content={
                    "error": "file_too_large",
                    "message": f"Upload exceeds the {limit_mb} MB limit.",
                },
            )
        return await call_next(request)


# ── Lifespan ──────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    # ── Startup ────────────────────────────────────────────────────────────
    logger.info("=" * 60)
    logger.info(
        "Aletheon Backend starting — OFFLINE_MODE=%s | PRETRAINED_WEIGHTS_USED=%s | ENV=%s",
        settings.OFFLINE_MODE,
        settings.PRETRAINED_WEIGHTS_USED,
        settings.ENVIRONMENT,
    )
    logger.info("=" * 60)

    # Verify critical directories
    _check_directories()

    # Enable SQLite WAL mode for better concurrent read performance
    _enable_wal()

    # Load self-trained artifacts
    from app.models.registry import ArtifactRegistry
    reg = ArtifactRegistry.get()
    reg.load_all()

    logger.info(
        "Artifact status — Classifier: %s | Corpus Index: %s (%d papers)",
        "loaded" if reg.classifier_loaded else "MISSING — using heuristic fallback",
        "loaded" if reg.corpus_index_loaded else "MISSING — recommendations empty",
        reg.corpus_paper_count,
    )
    logger.info("Startup complete — ready to serve on port %d", settings.PORT)

    yield

    # ── Shutdown ────────────────────────────────────────────────────────────
    logger.info("Shutting down Aletheon Backend gracefully.")


def _check_directories() -> None:
    """Warn clearly if expected directories are missing — don't crash startup."""
    for rel_path in ["./data", "./models"]:
        p = settings.resolve_path(rel_path)
        if not p.exists():
            logger.warning(
                "Directory '%s' does not exist. Run scripts/prepare_offline_bundle.py "
                "before serving requests that require artifacts.",
                p,
            )
        else:
            p.mkdir(parents=True, exist_ok=True)


def _enable_wal() -> None:
    """Enable SQLite WAL journal mode for better concurrent read performance."""
    try:
        import sqlite3
        from app.config import settings as s
        db_path = s.resolve_path(s.SQLITE_DB_PATH)
        db_path.parent.mkdir(parents=True, exist_ok=True)
        con = sqlite3.connect(str(db_path))
        con.execute("PRAGMA journal_mode=WAL")
        con.close()
        logger.debug("SQLite WAL mode enabled.")
    except Exception as exc:
        logger.warning("Could not enable SQLite WAL mode: %s", exc)


# ── Application factory ───────────────────────────────────────────────────────

_is_production = settings.ENVIRONMENT.lower() == "production"

app = FastAPI(
    title="Aletheon Research Intelligence API",
    description=(
        "Evidence-first research intelligence backend. "
        "Fully air-gapped, CPU-only. Zero pretrained weights.\n\n"
        "Every emitted claim is extractively grounded to a source span "
        "(`source_id`) in the original document and independently verified "
        "by a self-trained entailment classifier."
    ),
    version="2.0.0",
    docs_url="/docs" if settings.DOCS_ENABLED else None,
    redoc_url="/redoc" if settings.DOCS_ENABLED else None,
    openapi_url="/openapi.json" if settings.DOCS_ENABLED else None,
    lifespan=lifespan,
)

# ── Middleware (outermost first) ───────────────────────────────────────────────

app.add_middleware(FileSizeLimitMiddleware)
app.add_middleware(RequestIdMiddleware)

# CORS: locked to allowed origins in production; wildcard only in development
_cors_origins = (
    ["*"] if settings.ENVIRONMENT.lower() == "development"
    else settings.CORS_ORIGINS
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=False,         # credentials incompatible with wildcard
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", "X-Request-ID", "X-User-ID"],
)

# ── Global exception handler ──────────────────────────────────────────────────

@app.exception_handler(Exception)
async def _global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    rid = request_id_var.get("-")
    logger.error(
        "Unhandled exception on %s %s — request_id=%s",
        request.method, request.url.path, rid,
        exc_info=True,
    )
    return JSONResponse(
        status_code=500,
        content={
            "error": "internal_server_error",
            "request_id": rid,
            "message": "An unexpected error occurred. Check server logs for details.",
        },
    )

# ── Routers ───────────────────────────────────────────────────────────────────

from app.api.routes import router                           # noqa: E402
app.include_router(router)

# Online Recommendations — registered unconditionally for consistent response shape;
# feature flag gates actual network activity inside the router itself.
from app.recommendations.router import router as reco_router  # noqa: E402
app.include_router(reco_router)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.ENVIRONMENT.lower() != "production",
        log_level=settings.LOG_LEVEL.lower(),
    )
