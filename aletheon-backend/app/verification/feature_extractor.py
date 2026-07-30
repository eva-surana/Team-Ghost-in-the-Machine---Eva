"""
Runtime feature extractor for the entailment verification engine.

Mirrors exactly the features in train_entailment_classifier.py.
Having this in a shared module ensures training and inference
use identical feature definitions — a common source of train/serve skew.
"""
from __future__ import annotations

import re
from typing import Optional

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

_NEGATION_WORDS = frozenset([
    "not", "no", "never", "neither", "nor", "cannot", "can't", "doesn't",
    "don't", "didn't", "isn't", "aren't", "wasn't", "weren't", "without",
    "none", "nothing", "nobody", "nowhere"
])

_NUMBER_RE = re.compile(r"\b\d+(?:\.\d+)?(?:%|million|billion|thousand)?\b", re.IGNORECASE)


def extract_features(
    claim: str,
    source: str,
    vectorizer: Optional[TfidfVectorizer] = None,
) -> tuple[list[float], dict[str, float]]:
    """
    Extract the 6 entailment features for a (claim, source) pair.

    Args:
        claim:      The claim text to verify.
        source:     The source text (concatenated cited span texts).
        vectorizer: The shared TF-IDF vectorizer from the classifier artifact.
                    If None, tfidf_cosine defaults to word_overlap (graceful fallback).

    Returns:
        (feature_vector: list[float], feature_dict: dict[str, float])
        feature_dict is returned for logging/inspectability.
    """
    claim_lower = claim.lower()
    source_lower = source.lower()

    claim_words = set(claim_lower.split())
    source_words = set(source_lower.split())

    # 1. TF-IDF cosine similarity
    if vectorizer is not None:
        try:
            vecs = vectorizer.transform([claim_lower, source_lower])
            tfidf_cos = float(cosine_similarity(vecs[0], vecs[1])[0, 0])
        except Exception:
            tfidf_cos = _word_jaccard(claim_words, source_words)
    else:
        tfidf_cos = _word_jaccard(claim_words, source_words)

    # 2. Word Jaccard overlap
    word_overlap = _word_jaccard(claim_words, source_words)

    # 3. Bigram Jaccard overlap
    c_bg = _bigrams(claim_lower)
    s_bg = _bigrams(source_lower)
    union_bg = c_bg | s_bg
    bigram_overlap = len(c_bg & s_bg) / len(union_bg) if union_bg else 0.0

    # 4. Negation mismatch — negation in source but not in claim
    source_has_neg = bool(source_words & _NEGATION_WORDS)
    claim_has_neg = bool(claim_words & _NEGATION_WORDS)
    negation_mismatch = float(source_has_neg and not claim_has_neg)

    # 5. Length ratio (shorter / longer)
    len_c = max(1, len(claim_lower.split()))
    len_s = max(1, len(source_lower.split()))
    length_ratio = min(len_c, len_s) / max(len_c, len_s)

    # 6. Numeric mismatch — numbers in claim absent from source
    claim_nums = set(_NUMBER_RE.findall(claim))
    source_nums = set(_NUMBER_RE.findall(source))
    numeric_mismatch = float(bool(claim_nums - source_nums))

    vec = [tfidf_cos, word_overlap, bigram_overlap, negation_mismatch, length_ratio, numeric_mismatch]
    feat_dict = {
        "tfidf_cosine": round(tfidf_cos, 4),
        "word_overlap": round(word_overlap, 4),
        "bigram_overlap": round(bigram_overlap, 4),
        "negation_mismatch": negation_mismatch,
        "length_ratio": round(length_ratio, 4),
        "numeric_mismatch": numeric_mismatch,
    }
    return vec, feat_dict


def _word_jaccard(a: set, b: set) -> float:
    union = a | b
    return len(a & b) / len(union) if union else 0.0


def _bigrams(text: str) -> set:
    words = text.split()
    return {(words[i], words[i + 1]) for i in range(len(words) - 1)}
