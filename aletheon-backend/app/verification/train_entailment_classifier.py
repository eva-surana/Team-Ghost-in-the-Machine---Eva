"""
Train and save the entailment classifier.

This script is the authoritative trainer for the verification engine.
Run it during Phase A (prepare_offline_bundle.py calls this internally)
or standalone:
  python verification/train_entailment_classifier.py

Input:  training_data/entailment_triples.jsonl
Output: models/entailment_classifier.pkl  (dict with 'classifier' and 'vectorizer')

Features extracted per (claim, source) pair:
  1. tfidf_cosine        — cosine similarity between TF-IDF vectors of claim and source
  2. word_overlap        — Jaccard coefficient over lowercased word sets
  3. bigram_overlap      — Jaccard coefficient over bigram sets
  4. negation_mismatch   — 1 if negation word(s) present in source but absent in claim, else 0
  5. length_ratio        — min/max of (claim_len, source_len) in words
  6. numeric_mismatch    — 1 if numbers in claim are absent from source, else 0

Why these features?
  - tfidf_cosine: captures overall lexical and topical overlap
  - word/bigram overlap: direct n-gram grounding signal
  - negation_mismatch: catches "source says X does not" / "claim says X does" contradictions
  - length_ratio: very short claims vs. long sources often indicate paraphrase or omission
  - numeric_mismatch: numeric hallucination is the most common factual error in extractive systems

Classifier: LogisticRegression (sklearn), C=1.0, max_iter=1000.
Labels: entailed (2), neutral (1), contradicted (0).

Honest ceiling note (written to classifier metadata):
  A logistic regression over lexical features catches obvious contradictions
  (numeric mismatch, negation flip, clearly unrelated content) reliably.
  It misses subtler forms of misrepresentation — e.g., correct facts assembled
  to imply an unsupported causal link, or two claims that share vocabulary but
  differ in scope. This is documented in the eval harness output.
"""
from __future__ import annotations

import json
import pickle
import re
import sys
from pathlib import Path

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import classification_report
from sklearn.model_selection import cross_val_score, StratifiedKFold

PROJECT_ROOT = Path(__file__).parent.parent
TRAINING_DATA_PATH = PROJECT_ROOT / "training_data" / "entailment_triples.jsonl"
OUTPUT_PATH = PROJECT_ROOT / "models" / "entailment_classifier.pkl"


# ── Feature extraction ────────────────────────────────────────────────────────

_NEGATION_WORDS = frozenset([
    "not", "no", "never", "neither", "nor", "cannot", "can't", "doesn't",
    "don't", "didn't", "isn't", "aren't", "wasn't", "weren't", "without",
    "none", "nothing", "nobody", "nowhere"
])

_NUMBER_RE = re.compile(r"\b\d+(?:\.\d+)?(?:%|million|billion|thousand)?\b", re.IGNORECASE)


def extract_features_single(claim: str, source: str, vectorizer: TfidfVectorizer) -> list[float]:
    """Extract the 6 features for a single (claim, source) pair."""
    claim_lower = claim.lower()
    source_lower = source.lower()

    claim_words = set(claim_lower.split())
    source_words = set(source_lower.split())

    # 1. TF-IDF cosine similarity
    vecs = vectorizer.transform([claim_lower, source_lower])
    from sklearn.metrics.pairwise import cosine_similarity
    tfidf_cos = float(cosine_similarity(vecs[0], vecs[1])[0, 0])

    # 2. Word Jaccard overlap
    union_w = claim_words | source_words
    word_overlap = len(claim_words & source_words) / len(union_w) if union_w else 0.0

    # 3. Bigram Jaccard overlap
    def bigrams(s: str) -> set:
        words = s.split()
        return {(words[i], words[i + 1]) for i in range(len(words) - 1)}
    c_bg = bigrams(claim_lower)
    s_bg = bigrams(source_lower)
    union_bg = c_bg | s_bg
    bigram_overlap = len(c_bg & s_bg) / len(union_bg) if union_bg else 0.0

    # 4. Negation mismatch — negation in source but not in claim (likely contradiction)
    source_has_neg = bool(claim_words & _NEGATION_WORDS == set() and source_words & _NEGATION_WORDS)
    negation_mismatch = float(source_has_neg)

    # 5. Length ratio (min/max word count)
    len_claim = max(1, len(claim_lower.split()))
    len_source = max(1, len(source_lower.split()))
    length_ratio = min(len_claim, len_source) / max(len_claim, len_source)

    # 6. Numeric mismatch — numbers in claim absent from source
    claim_nums = set(_NUMBER_RE.findall(claim))
    source_nums = set(_NUMBER_RE.findall(source))
    numeric_mismatch = float(bool(claim_nums - source_nums))

    return [tfidf_cos, word_overlap, bigram_overlap, negation_mismatch, length_ratio, numeric_mismatch]


FEATURE_NAMES = [
    "tfidf_cosine", "word_overlap", "bigram_overlap",
    "negation_mismatch", "length_ratio", "numeric_mismatch"
]

LABEL_MAP = {"entailed": 2, "neutral": 1, "contradicted": 0}
LABEL_MAP_INV = {v: k for k, v in LABEL_MAP.items()}


def load_training_data(path: Path) -> tuple[list[str], list[str], list[int]]:
    claims, sources, labels = [], [], []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            claims.append(row["claim"])
            sources.append(row["source"])
            labels.append(LABEL_MAP[row["label"]])
    return claims, sources, labels


def train(training_data_path: Path = TRAINING_DATA_PATH,
          output_path: Path = OUTPUT_PATH) -> dict:
    print(f"[train_entailment_classifier] Loading data from {training_data_path}")
    claims, sources, labels = load_training_data(training_data_path)
    print(f"  -> {len(claims)} examples: "
          f"{labels.count(2)} entailed, {labels.count(1)} neutral, {labels.count(0)} contradicted")

    # Fit a shared TF-IDF vectorizer over all claim+source text
    all_texts = claims + sources
    vectorizer = TfidfVectorizer(
        analyzer="word",
        ngram_range=(1, 2),
        max_features=10_000,
        sublinear_tf=True,
        lowercase=True,
    )
    vectorizer.fit(all_texts)
    print(f"  -> Vectorizer vocab size: {len(vectorizer.vocabulary_)}")

    # Extract features
    X = np.array([extract_features_single(c, s, vectorizer) for c, s in zip(claims, sources)])
    y = np.array(labels)

    print(f"  -> Feature matrix: {X.shape}")

    # Cross-validate before final fit
    clf = LogisticRegression(C=1.0, max_iter=1000, class_weight="balanced", random_state=42)
    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
    cv_scores = cross_val_score(clf, X, y, cv=cv, scoring="f1_macro")
    print(f"  -> 5-fold CV macro-F1: {cv_scores.mean():.3f} +/- {cv_scores.std():.3f}")

    # Final fit on all data
    clf.fit(X, y)
    y_pred = clf.predict(X)
    print("\n  -> Training set classification report:")
    print(classification_report(y, y_pred, target_names=["contradicted", "neutral", "entailed"]))

    # Save artifact
    output_path.parent.mkdir(parents=True, exist_ok=True)
    artifact = {
        "classifier": clf,
        "vectorizer": vectorizer,
        "feature_names": FEATURE_NAMES,
        "label_map": LABEL_MAP,
        "label_map_inv": LABEL_MAP_INV,
        "training_set_size": len(claims),
        "cv_f1_mean": float(cv_scores.mean()),
        "cv_f1_std": float(cv_scores.std()),
        "training_data_path": str(training_data_path),
        "known_ceiling": (
            "LogisticRegression over 6 lexical features. Catches: numeric mismatch, "
            "negation flip, clearly unrelated content. Misses: subtle scope/causal misrepresentation, "
            "paraphrases that share vocabulary but differ in implication. "
            "Expand training_data/entailment_triples.jsonl to improve coverage."
        ),
    }
    with open(output_path, "wb") as f:
        pickle.dump(artifact, f, protocol=pickle.HIGHEST_PROTOCOL)

    print(f"\n  -> Saved classifier artifact to {output_path}")
    return artifact


if __name__ == "__main__":
    train()
