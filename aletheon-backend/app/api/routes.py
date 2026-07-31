"""FastAPI REST API routes — clean endpoints for frontend consumption."""
from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, BackgroundTasks, File, Header, HTTPException, Query, UploadFile

from app.config import settings
from app.jobs.manager import job_manager
from app.models.registry import ArtifactRegistry
from app.models.schemas import (
    ClaimGraphResponse,
    ContradictionReport,
    DocumentFidelityReport,
    DocumentStatusResponse,
    DocumentUploadResponse,
    MissingCitationSuggestion,
    QARequest,
    QAResponse,
    RecommendedPaper,
    ResearchDNA,
    SourceSpan,
    SystemHealthResponse,
)

router = APIRouter()


# ── System ────────────────────────────────────────────────────────────────────

@router.get("/system/health", response_model=SystemHealthResponse, tags=["System"])
async def system_health():
    reg = ArtifactRegistry.get()
    # Check last recommendation fetch from cache (if any) for display
    last_checked = None
    if settings.ENABLE_ONLINE_RECOMMENDATIONS:
        try:
            from app.recommendations.cache import get_cached
            # Aggregate last checked across any cached doc — just check the DB exists
            import sqlite3, os
            from pathlib import Path
            db_path = Path(settings.SQLITE_DB_PATH).parent / "recommendations_cache.db"
            if db_path.exists():
                conn = sqlite3.connect(str(db_path))
                row = conn.execute(
                    "SELECT MAX(fetched_at) FROM recommendation_cache"
                ).fetchone()
                conn.close()
                last_checked = row[0] if row and row[0] else None
        except Exception:
            pass

    return SystemHealthResponse(
        status="ok",
        offline_mode=settings.OFFLINE_MODE,
        pretrained_weights_used=settings.PRETRAINED_WEIGHTS_USED,
        entailment_classifier_loaded=reg.classifier_loaded,
        corpus_index_loaded=reg.corpus_index_loaded,
        entailment_classifier_path=settings.ENTAILMENT_CLASSIFIER_PATH,
        corpus_index_path=settings.CORPUS_INDEX_PATH,
        corpus_paper_count=reg.corpus_paper_count,
        recommendations_enabled=settings.ENABLE_ONLINE_RECOMMENDATIONS,
        recommendations_last_checked=last_checked,
    )


@router.get("/health", tags=["System"])
async def health_check():
    return {"status": "ok", "service": "Aletheon Backend", "version": "2.0.0"}


# ── Document Ingestion ────────────────────────────────────────────────────────

@router.get("/documents", tags=["Documents"])
async def list_documents():
    return job_manager.get_recent_documents()

@router.post("/documents", response_model=DocumentUploadResponse, status_code=202, tags=["Documents"])
async def upload_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(..., description="PDF file to upload"),
    x_user_id: Optional[str] = Header(default=None, include_in_schema=False),
):
    if not file or not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are supported. Please select a valid .pdf file.")

    file_bytes = await file.read()
    if len(file_bytes) > settings.MAX_UPLOAD_BYTES:
        limit_mb = settings.MAX_UPLOAD_BYTES // (1024 * 1024)
        raise HTTPException(status_code=413, detail=f"Upload exceeds the {limit_mb} MB limit.")

    doc_id = job_manager.create_document_job()

    from app.ingestion.service import process_document_background
    background_tasks.add_task(process_document_background, doc_id, file_bytes, file.filename)

    return DocumentUploadResponse(document_id=doc_id, status="processing")


@router.get("/documents/{doc_id}/status", response_model=DocumentStatusResponse, tags=["Documents"])
async def get_status(doc_id: str):
    status = job_manager.get_status(doc_id)
    if not status:
        raise HTTPException(status_code=404, detail=f"Document '{doc_id}' not found.")
    return status

@router.get("/documents/{doc_id}/file", tags=["Documents"])
async def get_document_file(doc_id: str):
    _assert_exists(doc_id)
    from pathlib import Path
    from app.config import settings
    from fastapi.responses import FileResponse
    pdf_path = Path(settings.SQLITE_DB_PATH).parent / "uploads" / f"{doc_id}.pdf"
    if not pdf_path.exists():
        raise HTTPException(status_code=404, detail="PDF file not found on server.")
    return FileResponse(pdf_path, media_type="application/pdf")


# ── Evidence Lookup ───────────────────────────────────────────────────────────

@router.get("/documents/{doc_id}/evidence/{source_id}", response_model=SourceSpan, tags=["Evidence"])
async def get_evidence(doc_id: str, source_id: str):
    span = job_manager.get_span(doc_id, source_id)
    if not span:
        raise HTTPException(
            status_code=404,
            detail=f"source_id '{source_id}' not found for document '{doc_id}'.",
        )
    return span


# ── Extractions ───────────────────────────────────────────────────────────────

@router.get("/documents/{doc_id}/research-dna", response_model=ResearchDNA, tags=["Extraction"])
async def get_research_dna(doc_id: str):
    _assert_completed(doc_id)

    cached = job_manager.get_research_dna(doc_id)
    if cached:
        return ResearchDNA.model_validate(cached)

    from app.extraction.research_dna import extract_research_dna
    dna = await extract_research_dna(doc_id)
    job_manager.store_research_dna(doc_id, dna.model_dump())
    return dna


@router.get("/documents/{doc_id}/dependency-graph", response_model=ClaimGraphResponse, tags=["Extraction"])
async def get_dependency_graph(doc_id: str):
    _assert_completed(doc_id)

    cached = job_manager.get_dependency_graph(doc_id)
    if cached:
        return ClaimGraphResponse.model_validate(cached)

    from app.extraction.dependency_graph import extract_dependency_graph
    graph = await extract_dependency_graph(doc_id)
    job_manager.store_dependency_graph(doc_id, graph.model_dump())
    return graph


@router.get("/documents/{doc_id}/fidelity", response_model=DocumentFidelityReport, tags=["Verification"])
async def get_fidelity(doc_id: str):
    _assert_exists(doc_id)
    from app.verification.confidence import compute_document_fidelity
    return await compute_document_fidelity(doc_id)


# ── Q&A ───────────────────────────────────────────────────────────────────────

@router.post("/documents/{doc_id}/ask", tags=["Q&A"])
async def ask(doc_id: str, req: QARequest, accept: Optional[str] = Header(None)):
    _assert_completed(doc_id)
    if not req.question or not req.question.strip():
        raise HTTPException(status_code=400, detail="Question cannot be empty.")
    if len(req.question) > settings.MAX_QUESTION_CHARS:
        raise HTTPException(
            status_code=400,
            detail=f"Question exceeds maximum allowed length of {settings.MAX_QUESTION_CHARS} characters.",
        )
    if accept and "text/event-stream" in accept:
        from fastapi.responses import StreamingResponse
        from app.generation.grounded_generator import generate_grounded_qa_stream
        return StreamingResponse(
            generate_grounded_qa_stream(doc_id, req.question),
            media_type="text/event-stream",
        )
    from app.generation.grounded_generator import generate_grounded_qa
    return await generate_grounded_qa(doc_id, req.question)


# ── Recommendations ───────────────────────────────────────────────────────────

@router.get(
    "/documents/{doc_id}/recommendations/similar-papers",
    response_model=List[RecommendedPaper],
    tags=["Recommendations"],
)
async def recommend_similar_papers(doc_id: str, top_k: int = Query(5, ge=1, le=20)):
    _assert_completed(doc_id)
    from app.recommendation.recommender import recommendation_engine
    return recommendation_engine.similar_papers(doc_id, top_k=top_k)


@router.get(
    "/documents/{doc_id}/recommendations/missing-citations",
    response_model=List[MissingCitationSuggestion],
    tags=["Recommendations"],
)
async def suggest_missing_citations(doc_id: str, top_k: int = Query(5, ge=1, le=20)):
    _assert_completed(doc_id)
    from app.recommendation.recommender import recommendation_engine
    return recommendation_engine.missing_citations(doc_id, top_k=top_k)


# ── Contradiction Detection ───────────────────────────────────────────────────

@router.get(
    "/documents/{doc_id}/contradictions",
    response_model=ContradictionReport,
    tags=["Contradiction"],
    summary="Detect within-paper contradictions",
    description=(
        "Identifies conflicting claims within the uploaded paper. "
        "Uses TF-IDF similarity filtering to avoid O(n\u00b2) classifier calls, "
        "then applies the existing entailment classifier to score each candidate pair. "
        "Results are cached after the first call. "
        "Contradiction confidence is \u2208 [0,1]; pairs below "
        "CONTRADICTION_CONFIDENCE_THRESHOLD (default 0.35) are not reported."
    ),
)
async def get_contradictions(doc_id: str):
    _assert_completed(doc_id)
    from app.contradiction.pipeline import contradiction_pipeline
    return await contradiction_pipeline.detect(doc_id)


# ── Debug Retrieval ───────────────────────────────────────────────────────────

@router.get(
    "/debug/retrieve",
    tags=["Debug"],
    include_in_schema=settings.ENVIRONMENT.lower() != "production",
)
async def debug_retrieve(
    doc_id: str,
    query: str,
    top_k: int = Query(5, ge=1, le=20),
):
    from app.retrieval.sparse_store import sparse_retriever
    results = sparse_retriever.search(doc_id=doc_id, query=query, top_k=top_k)
    return {
        "document_id": doc_id,
        "query": query,
        "results": [
            {
                "source_id": r.span.source_id,
                "page": r.span.page,
                "section": r.span.section,
                "similarity_score": r.score,
                "text": r.span.text[:200],
            }
            for r in results
        ],
    }


# ── Helpers ───────────────────────────────────────────────────────────────────

def _assert_exists(doc_id: str) -> None:
    if not job_manager.get_status(doc_id):
        raise HTTPException(status_code=404, detail=f"Document '{doc_id}' not found.")


def _assert_completed(doc_id: str) -> None:
    status = job_manager.get_status(doc_id)
    if not status:
        raise HTTPException(status_code=404, detail=f"Document '{doc_id}' not found.")
    if status.status == "processing":
        raise HTTPException(status_code=202, detail="Document ingestion still in progress.")
    if status.status == "failed":
        raise HTTPException(status_code=422, detail=f"Document ingestion failed: {status.error}")
