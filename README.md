# Aletheon: Evidence-First Research Intelligence

Aletheon is a comprehensive, air-gapped research intelligence platform designed to extract, verify, and present claims from documents with absolute fidelity. The system ensures transparency and traceability by relying solely on exact source spans and classical machine learning, avoiding the hallucinations and opacity of pretrained Large Language Models (LLMs).

## Project Structure

This repository is organized into two main components:

- **[`aletheon-backend`](./aletheon-backend/)**: A fully air-gapped, CPU-only Python backend that handles document ingestion (PyMuPDF + Tesseract), vectorization (TF-IDF), extraction, and verification (self-trained Logistic Regression). It enforces a strict "zero pretrained weights" constraint.
- **[`aletheon-frontend`](./aletheon-frontend/)**: A modern web interface built with Next.js, allowing users to upload documents, view extracted Research DNA, explore dependency graphs, and verify claims with exact text highlights.

## Features

- **Extractive Generation**: AI-generated claims are built directly from verbatim source spans—no free-text LLM generation.
- **Self-Trained Verification**: Claims are scored and verified using an independent, self-trained Logistic Regression classifier.
- **Contradiction Detection**: Batched TF-IDF cosine similarity filters candidate pairs to detect contradictions efficiently.
- **Air-Gapped & Secure**: Requires zero network access or external APIs after the initial offline bundle preparation.
- **Zero Pretrained Weights**: No downloaded LLMs, embedding models, vector databases, or NLI models.

## Getting Started

### 1. Backend Setup
Navigate to the backend directory and follow the two-phase offline install:
```bash
cd aletheon-backend
# Phase A: Train models & download dependencies (requires internet once)
pip install -r requirements.txt
python scripts/prepare_offline_bundle.py

# Phase B: Run on air-gapped machine
python -m venv .venv
# Activate venv (e.g., .venv\Scripts\activate on Windows)
pip install --no-index --find-links=./wheelhouse -r requirements.txt
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```
*(Alternatively, use Docker: `docker compose up -d`)*
See the [Backend README](./aletheon-backend/README.md) for full details.

### 2. Frontend Setup
Navigate to the frontend directory and start the Next.js development server:
```bash
cd aletheon-frontend
npm install
npm run dev
```
Access the application at [http://localhost:3000](http://localhost:3000).
See the [Frontend README](./aletheon-frontend/README.md) for more details.

## Documentation

- [Backend API Reference & Architecture](./aletheon-backend/README.md)
- [Frontend Documentation](./aletheon-frontend/README.md)
