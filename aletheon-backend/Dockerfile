# ── Stage 1: builder ──────────────────────────────────────────────────────────
FROM python:3.11-slim AS builder

WORKDIR /install

# System deps for PyMuPDF + Tesseract
RUN apt-get update && apt-get install -y --no-install-recommends \
        gcc \
        g++ \
        libffi-dev \
        libmupdf-dev \
        tesseract-ocr \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install/packages -r requirements.txt

# ── Stage 2: runtime ──────────────────────────────────────────────────────────
FROM python:3.11-slim AS runtime

# Runtime system deps only
RUN apt-get update && apt-get install -y --no-install-recommends \
        tesseract-ocr \
        libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# Non-root user
RUN useradd --uid 1000 --create-home --shell /bin/bash aletheon

# Copy installed Python packages from builder
COPY --from=builder /install/packages /usr/local

# App directory
WORKDIR /app

# Copy application code (before chown for layer efficiency)
COPY --chown=aletheon:aletheon app/         ./app/
COPY --chown=aletheon:aletheon corpus/      ./corpus/
COPY --chown=aletheon:aletheon training_data/ ./training_data/

# Persistent data directories (models + data mounted as volumes at runtime)
RUN mkdir -p /app/data /app/models && chown -R aletheon:aletheon /app

USER aletheon

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1

# Production: single worker, no reload, trust X-Forwarded-For
CMD ["uvicorn", "app.main:app", \
     "--host", "0.0.0.0", \
     "--port", "8000", \
     "--workers", "1", \
     "--no-access-log", \
     "--forwarded-allow-ips", "*"]
