"""
app/contradiction/ — Within-paper contradiction detection.

Identifies conflicting claims inside a single research paper.

Architecture constraints:
  - Fully offline, CPU-only, zero new dependencies.
  - Reuses: TF-IDF sparse matrix (data/sparse_vectors/{doc_id}.npz),
             per-doc vectorizer (data/doc_vectorizers/{doc_id}.pkl),
             entailment LogisticRegression + global vectorizer (ArtifactRegistry).
  - Avoids O(n²) classifier calls via TF-IDF batched cosine similarity
    candidate filtering (O(n²·vocab) matrix multiply, then top-K pruning).
  - Explanation generator only runs on confirmed contradiction pairs.

Pipeline:
  spans → normalize → candidate pairs (similarity ≥ θ) → classify
       → score → evidence extract → explain → ContradictionReport
"""
