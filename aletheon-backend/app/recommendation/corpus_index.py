"""
CorpusIndex — TF-IDF recommendation index over a local paper corpus.

Built once by scripts/prepare_offline_bundle.py, saved to models/corpus_index.pkl,
loaded at startup by ArtifactRegistry.

No pretrained weights. Vocabulary and IDF weights are learned exclusively
from the corpus text you supply in corpus/papers.json.

Corpus size context (documented per spec):
  - 10 papers (seed corpus): functional for testing the pipeline, thin results.
  - 100+ papers: recommendations become meaningful.
  - 500+ papers: real usefulness for missing-citation detection.
  Document this expectation in README so it is not a surprise during evaluation.
"""
from __future__ import annotations

import json
import pickle
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, NamedTuple, Optional

import numpy as np
import scipy.sparse as sp
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity


@dataclass
class CorpusPaper:
    paper_id: str
    title: str
    abstract: str


class CorpusMatch(NamedTuple):
    paper_id: str
    title: str
    score: float
    rationale_span: str   # the corpus abstract sentence(s) most similar to the query


@dataclass
class CorpusIndex:
    """
    Serialisable artifact stored in models/corpus_index.pkl.
    Contains:
      - vectorizer: fitted TfidfVectorizer (vocabulary from corpus)
      - matrix: (N_papers, vocab) sparse matrix
      - papers: list of CorpusPaper metadata
    """
    vectorizer: TfidfVectorizer
    matrix: sp.csr_matrix
    papers: List[CorpusPaper]

    @property
    def paper_count(self) -> int:
        return len(self.papers)

    # ── Query interface ───────────────────────────────────────────────────────

    def find_similar(self, query_text: str, top_k: int = 5) -> List[CorpusMatch]:
        """
        Rank corpus papers by cosine similarity to query_text.
        Returns top-k CorpusMatch objects.
        """
        if not query_text.strip() or self.paper_count == 0:
            return []

        q_vec = self.vectorizer.transform([query_text.lower()])
        sims = cosine_similarity(q_vec, self.matrix).flatten()

        n = min(top_k, self.paper_count)
        top_idx = np.argsort(sims)[::-1][:n]

        results = []
        for idx in top_idx:
            score = float(sims[idx])
            if score < 1e-6:
                break   # skip truly zero-similarity results
            paper = self.papers[idx]
            rationale = _best_sentence(query_text, paper.abstract)
            results.append(CorpusMatch(
                paper_id=paper.paper_id,
                title=paper.title,
                score=round(score, 4),
                rationale_span=rationale,
            ))
        return results

    # ── Build ─────────────────────────────────────────────────────────────────

    @classmethod
    def build(cls, corpus_path: Path) -> "CorpusIndex":
        """
        Fit a new CorpusIndex from corpus/papers.json.
        Called by prepare_offline_bundle.py.
        """
        papers = _load_corpus(corpus_path)
        if not papers:
            raise ValueError(f"No papers found in corpus at {corpus_path}")

        texts = [p.abstract.lower() for p in papers]
        vectorizer = TfidfVectorizer(
            analyzer="word",
            ngram_range=(1, 2),
            max_features=15_000,
            sublinear_tf=True,
            min_df=1,
            lowercase=True,
        )
        matrix = vectorizer.fit_transform(texts)
        return cls(vectorizer=vectorizer, matrix=matrix, papers=papers)

    # ── Serialisation ─────────────────────────────────────────────────────────

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "wb") as f:
            pickle.dump(self, f, protocol=pickle.HIGHEST_PROTOCOL)

    @classmethod
    def load(cls, path: Path) -> "CorpusIndex":
        with open(path, "rb") as f:
            return pickle.load(f)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _load_corpus(corpus_path: Path) -> List[CorpusPaper]:
    """Load papers.json (or all .json files) from the corpus directory."""
    papers = []
    target = corpus_path / "papers.json"
    if target.exists():
        with open(target, "r", encoding="utf-8") as f:
            raw = json.load(f)
        for item in raw:
            papers.append(CorpusPaper(
                paper_id=item["paper_id"],
                title=item["title"],
                abstract=item.get("abstract", item.get("text", "")),
            ))
    else:
        # Fallback: load every *.json in the corpus dir
        for jf in sorted(corpus_path.glob("*.json")):
            with open(jf, "r", encoding="utf-8") as f:
                raw = json.load(f)
            if isinstance(raw, list):
                for item in raw:
                    papers.append(CorpusPaper(
                        paper_id=item.get("paper_id", jf.stem),
                        title=item.get("title", jf.stem),
                        abstract=item.get("abstract", item.get("text", "")),
                    ))
    return papers


def _best_sentence(query: str, text: str) -> str:
    """Return the sentence from text most similar to query (crude overlap heuristic)."""
    import re
    sentences = re.split(r'(?<=[.!?])\s+', text.strip())
    if not sentences:
        return text[:200]
    query_words = set(query.lower().split())
    best = max(sentences, key=lambda s: len(set(s.lower().split()) & query_words))
    return best[:300]
