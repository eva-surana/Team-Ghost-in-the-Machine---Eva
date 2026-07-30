"""Background ingestion orchestrator — parse → segment → TF-IDF fit → index."""
from __future__ import annotations

import logging

from app.ingestion.pdf_parser import parse_pdf_bytes
from app.ingestion.segmenter import segment_blocks
from app.jobs.manager import job_manager
from app.vectorization.tfidf_service import tfidf_service

logger = logging.getLogger(__name__)


async def process_document_background(doc_id: str, pdf_bytes: bytes, filename: str) -> None:
    """
    Full ingestion pipeline:
      1. Parse PDF (text + OCR fallback)
      2. Segment into SourceSpans with stable source_ids
      3. Persist spans to SQLite
      4. Fit TF-IDF vectorizer and store sparse matrix (replaces FAISS indexing)
      5. Update job status
    """
    try:
        logger.info(f"[Ingestion] Starting pipeline for doc={doc_id} file={filename}")

        blocks = parse_pdf_bytes(pdf_bytes)
        spans = segment_blocks(doc_id, blocks)
        pages_count = max((s.page for s in spans), default=0)

        job_manager.store_spans(doc_id, spans)

        # TF-IDF fit: vocabulary + IDF weights learned from THIS document's own text.
        # No pretrained vocabulary, no hub download.
        tfidf_service.fit_and_store(doc_id, spans)

        job_manager.update_status(
            doc_id=doc_id,
            status="completed",
            pages_count=pages_count,
            chunks_count=len(spans),
        )
        logger.info(
            f"[Ingestion] Completed doc={doc_id}: {pages_count} pages, {len(spans)} chunks"
        )
    except Exception as exc:
        logger.error(f"[Ingestion] FAILED doc={doc_id}: {exc}", exc_info=True)
        job_manager.update_status(doc_id=doc_id, status="failed", error=str(exc))
