"""
Aletheon Backend — Configuration

All settings come from environment variables / .env file.
No API keys. No cloud endpoints. No model hub identifiers.
Every artifact is a locally trained file produced by this project.
"""
import os
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # ── Offline + pretrained-weights enforcement ──────────────────────────────
    OFFLINE_MODE: bool = True
    PRETRAINED_WEIGHTS_USED: bool = False   # must stay False; tested by compliance gate

    # These env vars are set even though this build does not import transformers/HF.
    # They act as a safety net: if a transitive dependency ever silently tries to
    # download from HuggingFace, it will fail loudly instead of silently.
    HF_HUB_OFFLINE: str = "1"
    TRANSFORMERS_OFFLINE: str = "1"
    HF_DATASETS_OFFLINE: str = "1"
    TOKENIZERS_PARALLELISM: str = "false"

    # ── Self-trained artifact paths ───────────────────────────────────────────
    # These files are produced by scripts/prepare_offline_bundle.py.
    # If any is missing at startup, the server raises a clear error.
    ENTAILMENT_CLASSIFIER_PATH: str = "./models/entailment_classifier.pkl"
    CORPUS_INDEX_PATH: str = "./models/corpus_index.pkl"

    # ── Storage paths ─────────────────────────────────────────────────────────
    SQLITE_DB_PATH: str = "./data/aletheon.db"
    SPARSE_VECTORS_DIR: str = "./data/sparse_vectors"   # .npz files per document
    DOC_VECTORIZERS_DIR: str = "./data/doc_vectorizers"  # per-doc TF-IDF .pkl

    # ── Corpus paths ──────────────────────────────────────────────────────────
    CORPUS_TEXT_DIR: str = "./corpus"
    TESSERACT_DATA_PATH: str = "./models/tessdata"

    # ── Retrieval ─────────────────────────────────────────────────────────────
    RETRIEVAL_TOP_K: int = 5

    # ── Entailment classifier thresholds ─────────────────────────────────────
    # entailment_prob >= VERIFIED   → "verified"
    # PARTIAL <= prob < VERIFIED    → "partially_supported"
    # prob < PARTIAL                → "unsupported"
    ENTAILMENT_VERIFIED_THRESHOLD: float = 0.60
    ENTAILMENT_PARTIAL_THRESHOLD: float = 0.30

    # ── Recommendation engine (local corpus) ─────────────────────────────────
    RECOMMENDATION_TOP_K: int = 5
    MISSING_CITATION_TOP_K: int = 5

    # ── Contradiction Detection ───────────────────────────────────────────────
    # Minimum TF-IDF cosine similarity for a claim pair to enter the candidate
    # set. Below this threshold claims are provably not contradicting each other.
    CONTRADICTION_SIMILARITY_THRESHOLD: float = 0.25
    # Minimum contradiction_confidence (P(contra) × sim_weight) to surface a pair.
    # Keeps evidence extraction and explanation from running on weak candidates.
    CONTRADICTION_CONFIDENCE_THRESHOLD: float = 0.35
    # Hard cap on candidate pairs forwarded to the classifier.
    # Prevents runaway on very long documents (n >> 100 claims).
    CONTRADICTION_MAX_PAIRS: int = 50

    # ── Online Recommendations (network-enabled, disabled by default) ─────────
    # Structural boundary: only app/recommendations/ may use these settings.
    # Flip to true only when network access is intentionally enabled.
    ENABLE_ONLINE_RECOMMENDATIONS: bool = False
    RECOMMENDATION_CACHE_TTL_HOURS: int = 6
    SEMANTIC_SCHOLAR_BASE_URL: str = "https://api.semanticscholar.org/graph/v1"
    ARXIV_BASE_URL: str = "https://export.arxiv.org/api/query"

    # ── API ────────────────────────────────────────────────────────────────────
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    ENVIRONMENT: str = "development"

    # ── Security ──────────────────────────────────────────────────────────
    # Maximum file size accepted by the upload endpoint (bytes).
    # Oversized requests are rejected at the middleware layer before body streaming.
    MAX_UPLOAD_BYTES: int = 50 * 1024 * 1024    # 50 MB
    # Allowed CORS origins in production. In development (ENVIRONMENT=development)
    # app/main.py overrides this with ["*"] automatically.
    CORS_ORIGINS: list = ["http://localhost:3000", "http://localhost:8080"]
    # Maximum length of a Q&A question (characters)
    MAX_QUESTION_CHARS: int = 500

    # ── Logging ───────────────────────────────────────────────────────────
    # "json" → newline-delimited JSON (recommended for production / log aggregators)
    # "text" → human-readable with colour codes (default for development)
    LOG_FORMAT: str = "text"
    LOG_LEVEL: str = "INFO"

    # ── API Docs ───────────────────────────────────────────────────────────
    # Set DOCS_ENABLED=false in production to hide /docs, /redoc, /openapi.json.
    DOCS_ENABLED: bool = True

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    def enforce_offline_env_vars(self) -> None:
        """Force offline env vars into process environment so any stray transitive
        import that touches HuggingFace will fail loudly rather than silently fetching."""
        os.environ["HF_HUB_OFFLINE"] = self.HF_HUB_OFFLINE
        os.environ["TRANSFORMERS_OFFLINE"] = self.TRANSFORMERS_OFFLINE
        os.environ["HF_DATASETS_OFFLINE"] = self.HF_DATASETS_OFFLINE
        os.environ["TOKENIZERS_PARALLELISM"] = self.TOKENIZERS_PARALLELISM

    def resolve_path(self, relative: str) -> Path:
        p = Path(relative)
        return p if p.is_absolute() else Path.cwd() / p


settings = Settings()
settings.enforce_offline_env_vars()
