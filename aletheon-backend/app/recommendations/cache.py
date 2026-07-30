"""
cache.py — SQLite cache for online recommendation results.

Separate from the core pipeline's SQLite database.
Stores raw ranked results JSON keyed by document_id.
TTL enforced at read time (configurable via RECOMMENDATION_CACHE_TTL_HOURS).

This is what makes the hybrid model useful in practice:
look up recommendations once while online, results persist offline.
Cached results are clearly labeled with `source_mode: "cached"` and
the original `fetched_at` timestamp so the UI can show staleness.
"""
from __future__ import annotations

import json
import logging
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from app.config import settings

logger = logging.getLogger(__name__)

_CREATE_SQL = """
CREATE TABLE IF NOT EXISTS recommendation_cache (
    document_id TEXT PRIMARY KEY,
    fetched_at  TEXT NOT NULL,
    results_json TEXT NOT NULL
);
"""


def _get_conn() -> sqlite3.Connection:
    db_path = Path(settings.SQLITE_DB_PATH).parent / "recommendations_cache.db"
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path), check_same_thread=False)
    conn.execute(_CREATE_SQL)
    conn.commit()
    return conn


def get_cached(doc_id: str) -> tuple[list[dict] | None, str | None]:
    """
    Return (results, fetched_at_iso) if a cache entry exists,
    or (None, None) if not found.
    Does NOT enforce TTL — caller decides whether to serve stale.
    """
    try:
        with _get_conn() as conn:
            row = conn.execute(
                "SELECT results_json, fetched_at FROM recommendation_cache WHERE document_id = ?",
                (doc_id,)
            ).fetchone()
            if row:
                return json.loads(row[0]), row[1]
    except Exception as exc:
        logger.warning(f"[RecoCache] get_cached failed: {exc}")
    return None, None


def store_cache(doc_id: str, results: list[dict]) -> str:
    """
    Persist results to cache. Returns the ISO fetched_at timestamp.
    """
    fetched_at = datetime.now(timezone.utc).isoformat()
    try:
        with _get_conn() as conn:
            conn.execute(
                """INSERT INTO recommendation_cache (document_id, fetched_at, results_json)
                   VALUES (?, ?, ?)
                   ON CONFLICT(document_id) DO UPDATE SET
                       fetched_at=excluded.fetched_at,
                       results_json=excluded.results_json""",
                (doc_id, fetched_at, json.dumps(results))
            )
            conn.commit()
    except Exception as exc:
        logger.warning(f"[RecoCache] store_cache failed: {exc}")
    return fetched_at


def is_cache_fresh(fetched_at_iso: str) -> bool:
    """True if the cached result is within the configured TTL."""
    from datetime import timedelta
    try:
        fetched_at = datetime.fromisoformat(fetched_at_iso)
        if fetched_at.tzinfo is None:
            fetched_at = fetched_at.replace(tzinfo=timezone.utc)
        age = datetime.now(timezone.utc) - fetched_at
        ttl = timedelta(hours=settings.RECOMMENDATION_CACHE_TTL_HOURS)
        return age < ttl
    except Exception:
        return False
