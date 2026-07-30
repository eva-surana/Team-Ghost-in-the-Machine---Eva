"""
SQLite-backed job manager for document ingestion status tracking.
Uses Python's built-in sqlite3 — no extra dependency.
"""
from __future__ import annotations

import sqlite3
import uuid
import logging
import json
from pathlib import Path
from typing import Optional, Any

from app.config import settings
from app.models.schemas import DocumentStatusResponse, SourceSpan

logger = logging.getLogger(__name__)


def _get_db_path() -> Path:
    p = settings.resolve_path(settings.SQLITE_DB_PATH)
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def _conn() -> sqlite3.Connection:
    db_path = _get_db_path()
    con = sqlite3.connect(str(db_path), check_same_thread=False)
    con.row_factory = sqlite3.Row
    return con


def _init_db() -> None:
    with _conn() as con:
        con.executescript("""
            CREATE TABLE IF NOT EXISTS jobs (
                doc_id      TEXT PRIMARY KEY,
                status      TEXT NOT NULL DEFAULT 'processing',
                pages_count INTEGER,
                chunks_count INTEGER,
                error       TEXT,
                created_at  TEXT DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS spans (
                source_id        TEXT NOT NULL,
                document_id      TEXT NOT NULL,
                page             INTEGER,
                section          TEXT,
                paragraph_offset INTEGER,
                text             TEXT,
                PRIMARY KEY (source_id, document_id)
            );

            CREATE TABLE IF NOT EXISTS verification_log (
                record_id        TEXT PRIMARY KEY,
                document_id      TEXT NOT NULL,
                claim_text       TEXT,
                cited_source_ids TEXT,   -- JSON array
                verdict          TEXT,
                nli_score        REAL,
                rationale        TEXT,
                created_at       TEXT DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS doc_artifacts (
                doc_id  TEXT NOT NULL,
                key     TEXT NOT NULL,
                value   TEXT NOT NULL,    -- JSON blob
                PRIMARY KEY (doc_id, key)
            );
        """)


# Initialise tables once at import time
_init_db()


class JobManager:
    """
    SQLite-backed document status registry.
    Thread-safe for FastAPI BackgroundTasks (each call opens its own connection).
    """

    # ── Document lifecycle ────────────────────────────────────────────────────

    def create_document_job(self) -> str:
        doc_id = str(uuid.uuid4())
        with _conn() as con:
            con.execute(
                "INSERT INTO jobs (doc_id, status) VALUES (?, 'processing')",
                (doc_id,),
            )
        return doc_id

    def update_status(
        self,
        doc_id: str,
        status: str,
        pages_count: Optional[int] = None,
        chunks_count: Optional[int] = None,
        error: Optional[str] = None,
    ) -> None:
        with _conn() as con:
            con.execute(
                """UPDATE jobs
                   SET status=?, pages_count=COALESCE(?,pages_count),
                       chunks_count=COALESCE(?,chunks_count), error=COALESCE(?,error)
                   WHERE doc_id=?""",
                (status, pages_count, chunks_count, error, doc_id),
            )

    def get_status(self, doc_id: str) -> Optional[DocumentStatusResponse]:
        with _conn() as con:
            row = con.execute(
                "SELECT * FROM jobs WHERE doc_id=?", (doc_id,)
            ).fetchone()
        if not row:
            return None
        return DocumentStatusResponse(
            document_id=row["doc_id"],
            status=row["status"],
            pages_count=row["pages_count"],
            chunks_count=row["chunks_count"],
            error=row["error"],
        )

    def get_recent_documents(self) -> list[dict]:
        with _conn() as con:
            rows = con.execute(
                "SELECT doc_id, status FROM jobs ORDER BY created_at DESC LIMIT 10"
            ).fetchall()
        
        results = []
        for row in rows:
            doc_id = row["doc_id"]
            filename = self.get_artifact(doc_id, "filename") or "Untitled Document"
            records = self.get_verification_records(doc_id)
            if not records:
                fidelity = 100
            else:
                n_total = len(records)
                n_verified = sum(1 for r in records if r["verdict"] == "verified")
                n_partial = sum(1 for r in records if r["verdict"] == "partially_supported")
                fidelity = round(((n_verified + 0.5 * n_partial) / n_total) * 100)
            
            results.append({
                "documentId": doc_id,
                "name": filename,
                "fidelity": fidelity
            })
        return results

    # ── Source span storage ───────────────────────────────────────────────────

    def store_spans(self, doc_id: str, spans: list[SourceSpan]) -> None:
        rows = [
            (
                s.source_id, s.document_id, s.page,
                s.section, s.paragraph_offset, s.text,
            )
            for s in spans
        ]
        with _conn() as con:
            con.executemany(
                """INSERT OR REPLACE INTO spans
                   (source_id, document_id, page, section, paragraph_offset, text)
                   VALUES (?,?,?,?,?,?)""",
                rows,
            )

    def get_span(self, doc_id: str, source_id: str) -> Optional[SourceSpan]:
        with _conn() as con:
            row = con.execute(
                "SELECT * FROM spans WHERE document_id=? AND source_id=?",
                (doc_id, source_id),
            ).fetchone()
        if not row:
            return None
        return SourceSpan(
            source_id=row["source_id"],
            document_id=row["document_id"],
            page=row["page"],
            section=row["section"],
            paragraph_offset=row["paragraph_offset"] or 0,
            text=row["text"],
        )

    def get_all_spans(self, doc_id: str) -> list[SourceSpan]:
        with _conn() as con:
            rows = con.execute(
                "SELECT * FROM spans WHERE document_id=? ORDER BY page, paragraph_offset",
                (doc_id,),
            ).fetchall()
        return [
            SourceSpan(
                source_id=r["source_id"],
                document_id=r["document_id"],
                page=r["page"],
                section=r["section"],
                paragraph_offset=r["paragraph_offset"] or 0,
                text=r["text"],
            )
            for r in rows
        ]

    # ── Artifact store (research DNA, dependency graph) ───────────────────────

    def store_artifact(self, doc_id: str, key: str, data: Any) -> None:
        with _conn() as con:
            con.execute(
                "INSERT OR REPLACE INTO doc_artifacts (doc_id, key, value) VALUES (?,?,?)",
                (doc_id, key, json.dumps(data)),
            )

    def get_artifact(self, doc_id: str, key: str) -> Optional[Any]:
        with _conn() as con:
            row = con.execute(
                "SELECT value FROM doc_artifacts WHERE doc_id=? AND key=?",
                (doc_id, key),
            ).fetchone()
        if not row:
            return None
        return json.loads(row["value"])

    # ── Verification audit log ────────────────────────────────────────────────

    def log_verification(
        self,
        record_id: str,
        doc_id: str,
        claim_text: str,
        cited_source_ids: list[str],
        verdict: str,
        nli_score: float,
        rationale: str,
    ) -> None:
        with _conn() as con:
            con.execute(
                """INSERT OR REPLACE INTO verification_log
                   (record_id, document_id, claim_text, cited_source_ids,
                    verdict, nli_score, rationale)
                   VALUES (?,?,?,?,?,?,?)""",
                (
                    record_id, doc_id, claim_text,
                    json.dumps(cited_source_ids), verdict, nli_score, rationale,
                ),
            )

    def get_verification_records(self, doc_id: str) -> list[dict]:
        with _conn() as con:
            rows = con.execute(
                "SELECT * FROM verification_log WHERE document_id=?", (doc_id,)
            ).fetchall()
        return [dict(r) for r in rows]

    # ── Convenience wrappers kept for backward-compat ─────────────────────────

    def store_research_dna(self, doc_id: str, data: Any) -> None:
        self.store_artifact(doc_id, "research_dna", data)

    def get_research_dna(self, doc_id: str) -> Optional[Any]:
        return self.get_artifact(doc_id, "research_dna")

    def store_dependency_graph(self, doc_id: str, data: Any) -> None:
        self.store_artifact(doc_id, "dependency_graph", data)

    def get_dependency_graph(self, doc_id: str) -> Optional[Any]:
        return self.get_artifact(doc_id, "dependency_graph")


job_manager = JobManager()
