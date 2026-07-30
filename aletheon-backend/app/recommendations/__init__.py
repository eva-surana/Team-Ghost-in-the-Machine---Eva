"""
app/recommendations/ — The ONLY module in this codebase allowed to make network calls.

Isolation contract (enforced structurally, not just by convention):
  - This package may be imported by app/main.py (router registration) and
    nothing else in the core pipeline.
  - This package may read already-computed job artifacts via app/jobs/manager
    and app/models/schemas — shared data layer only.
  - This package MUST NOT import from:
      app/ingestion/, app/retrieval/, app/generation/, app/verification/
  - Core pipeline modules (ingestion, retrieval, generation, verification)
    MUST NOT import from this package.
  - All network I/O is gated behind ENABLE_ONLINE_RECOMMENDATIONS=false
    (the default). When false, every endpoint short-circuits before
    connectivity.py or client.py are even imported.

The no-pretrained-weights constraint does NOT apply to this module
(it is explicitly network-enabled when opted in). Ranking uses local
TF-IDF cosine similarity — consistent with the core pipeline, no
downloaded embedding model.
"""
