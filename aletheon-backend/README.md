# Aletheon Backend — Classical ML & Extractive Pipeline

## Evidence-first research intelligence backend  
**Fully air-gapped · CPU-only · Zero pretrained model weights**

---

## Architectural Principle

Every AI-generated claim is:
1. **Extracted** verbatim from a retrieved source span in the original document (`source_id`), or composed of multiple extracted spans separated by ` [...] `. No language model (LLM) is used to freely generate text.
2. **Verified** by an independent self-trained Logistic Regression classifier trained on project-supplied labeled triples (not a pretrained NLI/cross-encoder).
3. **Scored** with a confidence value derived from TF-IDF retrieval cosine similarity + entailment classifier probability.
4. **Checked for Contradictions** within the document using batched TF-IDF cosine similarity candidate filtering to prevent $O(n^2)$ classifier invocations.

---

## Zero Pretrained Weights Constraint

This build enforces a strict constraint: **no pretrained weights anywhere in the core system**.
- **No downloaded LLM** (no `llama-cpp-python`, no GGUF weights).
- **No downloaded embedding models** (no `sentence-transformers`, no HuggingFace Hub encoders).
- **No downloaded vector database** (no `faiss-cpu`; replaced by `scipy.sparse` TF-IDF matrices + `sklearn` cosine similarity).
- **No downloaded NLI models** (replaced by `app/verification/train_entailment_classifier.py` trained on `training_data/entailment_triples.jsonl`).

### Known Exceptions (Documented)
- **Tesseract OCR (`eng.traineddata`)**: PyMuPDF handles native vector PDF text. If a scanned page is encountered, `pytesseract` uses the locally vendored Tesseract language pack `models/tessdata/eng.traineddata`. Character-level OCR is a low-level vision utility and not part of the grounding/generation/verification chain.
- **Online Recommendation Module (Optional)**: A separate, isolated module (`app/recommendations/`) disabled by default (`ENABLE_ONLINE_RECOMMENDATIONS=false`). It is the ONLY module allowed to make network calls when explicitly enabled by operator setting.

---

## System Architecture

```
Upload PDF
   │
   ▼
[Ingestion] PyMuPDF + pytesseract OCR → SourceSpans → SQLite
   │
   ▼
[Vectorization] TfidfVectorizer (fitted per-document) → scipy.sparse matrix (.npz)
   │
   ▼
[Retrieval] Sparse cosine similarity → top-k SourceSpans + section affinity weights
   │
   ├──▶ [Extractive Generation] Select top span (single_span) or join top-N (extractive_composite)
   │
   ├──▶ [Contradiction Detector] Batched claim-pair similarity filtering → NLI contradiction classifier → Evidence & Explanation
   │
   ▼
[Verification Engine] Self-trained Logistic Regression classifier on 6 lexical features:
   [tfidf_cosine, word_overlap, bigram_overlap, negation_mismatch, length_ratio, numeric_mismatch]
   │
   ▼
[Confidence Aggregator] 0.4 × retrieval_score + 0.6 × entailment_score → per-claim confidence
   │
   ▼
[API Response] JSON with GroundedClaim (text, cited_spans, composition_method, verification_status)
```

---

## Setup — Two-Phase Offline Install

### Phase A — Train & Vendor Artifacts (run ONCE on any machine)

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Train self-trained classifier & build corpus recommendation index
python scripts/prepare_offline_bundle.py

# This creates:
#   models/entailment_classifier.pkl  ← self-trained Logistic Regression model
#   models/corpus_index.pkl            ← TF-IDF index over corpus/papers.json
#   models/tessdata/eng.traineddata    ← Tesseract language pack (OCR exception)
#   wheelhouse/                        ← all .whl files for offline pip install
```

Transfer `models/`, `corpus/`, and `wheelhouse/` to the air-gapped target machine.

### Phase B — Install on Air-Gapped Target Machine

```bash
# 1. Create virtual environment
python -m venv .venv
.venv\Scripts\activate       # Windows
# source .venv/bin/activate  # Linux/macOS

# 2. Install from local wheelhouse (no internet required)
pip install --no-index --find-links=./wheelhouse -r requirements.txt

# 3. Start the server
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

---

## Containerized Deployment (Docker)

To run in production via Docker:

```bash
# Build & start container
docker compose up -d

# Check status
docker compose ps
```

---

## API Reference

| Category | Method | Path | Description |
|---|---|---|---|
| **System** | GET | `/health` | Basic health check |
| **System** | GET | `/system/health` | Artifact load status & offline compliance check |
| **Documents** | POST | `/documents` | Upload PDF → `{document_id, status}` |
| **Documents** | GET | `/documents/{id}/status` | Poll document ingestion status |
| **Evidence** | GET | `/documents/{id}/evidence/{source_id}` | Exact source text for highlight-on-hover |
| **Extraction** | GET | `/documents/{id}/research-dna` | Grounded Research DNA (problem, gap, method, contribution) |
| **Extraction** | GET | `/documents/{id}/dependency-graph` | Extracted claim dependency graph |
| **Verification** | GET | `/documents/{id}/fidelity` | DocumentFidelityReport |
| **Contradiction** | GET | `/documents/{id}/contradictions` | Within-paper contradiction detection report |
| **Q&A** | POST | `/documents/{id}/ask` | Extractive Q&A over paper |
| **Recommendations** | GET | `/documents/{id}/recommendations/similar-papers` | Local corpus paper recommendations |
| **Recommendations** | GET | `/documents/{id}/recommendations/missing-citations` | Local corpus citation suggestions |
| **Online Recs** | GET | `/documents/{id}/recommendations` | Online recommendations (gated by feature flag) |
| **Online Recs** | POST | `/documents/{id}/recommendations/refresh` | Force refresh online recommendations |
| **Debug** | GET | `/debug/retrieve` | Debug TF-IDF retrieval scores |

---

## Running Tests

```bash
# Unit tests
pytest tests/unit/ -v

# No Pretrained Weights compliance gate (scans codebase & requirements.txt)
pytest tests/no_pretrained_weights/ -v

# Offline socket-blocking compliance gate
pytest tests/offline_compliance/ -v

# Grounding & Recommendation evaluation harness
pytest tests/eval/ -v -s

# Standalone offline audit script
python scripts/verify_offline.py

# Run complete test suite
pytest -v
```

---

## Self-Trained Classifier Ceiling & Provenance

- **Classifier**: `sklearn.linear_model.LogisticRegression` trained on 117 labeled triples in `training_data/entailment_triples.jsonl`.
- **Features**: TF-IDF cosine similarity, word Jaccard, bigram Jaccard, negation mismatch flag, length ratio, numeric mismatch flag.
- **Known ceiling**: Reliably catches numeric hallucinations, negation flips, and unrelated text. Does not detect subtle semantic re-framing where vocabulary matches but proposition differs. Expand `training_data/entailment_triples.jsonl` to increase domain coverage.
