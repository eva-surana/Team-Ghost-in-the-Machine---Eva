"""
Extractive span composer.

This module converts ranked SourceSpans into GroundedClaim objects.
It is the ONLY "generation" path in this system, and it is explicitly
extractive — it never writes text that is not verbatim from the source.

composition_method values:
  single_span          — claim.text == span.text exactly
  extractive_composite — claim.text == spans joined by " [...] " separator;
                         every segment is a real extracted span with its source_id
                         preserved.  The separator signals to the reader that
                         segments were selected, not written.

Design ceiling (documented per spec):
  Output reads as excerpted/compiled text, not fluent prose. This is intentional.
  The tradeoff is: every word in the output is traceable to a source_id.
  A freely-generated LLM response would read better but could hallucinate.
  This system cannot hallucinate by construction — the ceiling is the honesty floor.
"""
from __future__ import annotations

import uuid
from typing import List, Tuple

from app.generation.span_selector import SearchResult
from app.models.schemas import GroundedClaim, SourceSpan

# Maximum number of spans stitched together in extractive_composite mode
_MAX_COMPOSITE_SPANS = 3

# Separator used to signal that composite text is multi-span extracted, not written
_COMPOSITE_SEP = " [...] "


def compose_claim(
    ranked_spans: List[Tuple[SearchResult, float]],
    min_score: float = 0.0,
    composite_threshold: int = 1,
) -> GroundedClaim | None:
    """
    Build a GroundedClaim from pre-ranked (SearchResult, boosted_score) pairs.

    Args:
        ranked_spans:        Output of span_selector.rank_spans().
        min_score:           Minimum boosted_score to consider a span.
        composite_threshold: If only 1 span qualifies → single_span.
                             If >1 qualifies → extractive_composite (up to _MAX_COMPOSITE_SPANS).

    Returns:
        GroundedClaim (verification_status set to "verified" placeholder;
        actual verification happens in the verifier module downstream).
        Returns None if no spans pass the min_score filter.
    """
    filtered = [(r, s) for r, s in ranked_spans if s >= min_score]
    if not filtered:
        return None

    if len(filtered) == 1 or composite_threshold <= 1:
        result, score = filtered[0]
        return _single_span_claim(result, score)

    # Use up to _MAX_COMPOSITE_SPANS spans
    top = filtered[:_MAX_COMPOSITE_SPANS]
    return _composite_claim(top)


def _single_span_claim(result: SearchResult, boosted_score: float) -> GroundedClaim:
    span = result.span
    return GroundedClaim(
        claim_id=str(uuid.uuid4()),
        text=span.text,
        cited_spans=[span],
        composition_method="single_span",
        verification_status="verified",   # placeholder — verifier will update
        confidence=0.0,                   # placeholder — confidence module fills this
        retrieval_score=round(result.score, 4),
        entailment_score=0.0,             # placeholder
    )


def _composite_claim(
    ranked: List[Tuple[SearchResult, float]]
) -> GroundedClaim:
    parts = [r.span.text for r, _ in ranked]
    cited = [r.span for r, _ in ranked]
    avg_retrieval = sum(r.score for r, _ in ranked) / len(ranked)
    avg_boosted = sum(s for _, s in ranked) / len(ranked)

    text = _COMPOSITE_SEP.join(parts)

    return GroundedClaim(
        claim_id=str(uuid.uuid4()),
        text=text,
        cited_spans=cited,
        composition_method="extractive_composite",
        verification_status="verified",  # placeholder
        confidence=0.0,                  # placeholder
        retrieval_score=round(avg_retrieval, 4),
        entailment_score=0.0,            # placeholder
    )


def extract_precise_answer_sentence(question: str, span_text: str) -> str:
    """
    Extract the pinpoint sentence(s) from a paragraph span_text that best match the question.
    Preserves exact verbatim text of extracted sentences.
    """
    import re
    if not span_text or not span_text.strip():
        return span_text

    # Split into sentences
    sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", span_text) if s.strip()]
    if len(sentences) <= 1:
        return span_text

    q_words = set(re.findall(r"\b[a-z0-9]+\b", question.lower()))
    _STOPWORDS = {"what", "which", "where", "when", "who", "whom", "whose", "why", "how",
                  "is", "are", "was", "were", "be", "been", "being", "have", "has", "had",
                  "do", "does", "did", "the", "a", "an", "and", "or", "but", "in", "on",
                  "at", "to", "for", "with", "about", "against", "between", "into", "through",
                  "during", "before", "after", "above", "below", "from", "up", "down", "of",
                  "off", "over", "under", "again", "further", "then", "once", "this", "that"}
    keywords = q_words - _STOPWORDS

    if not keywords:
        return sentences[0]

    sentence_scores = []
    for idx, sent in enumerate(sentences):
        sent_words = set(re.findall(r"\b[a-z0-9]+\b", sent.lower()))
        overlap = len(sent_words & keywords)
        score = overlap / max(len(keywords), 1)
        sentence_scores.append((score, idx, sent))

    sentence_scores.sort(key=lambda x: x[0], reverse=True)

    top_score = sentence_scores[0][0]
    if top_score == 0:
        return sentences[0]

    # Pick top 1 or top 2 consecutive matching sentences
    selected_indices = [sentence_scores[0][1]]
    if len(sentence_scores) > 1 and sentence_scores[1][0] >= top_score * 0.75:
        selected_indices.append(sentence_scores[1][1])

    selected_indices.sort()
    return " ".join(sentences[i] for i in selected_indices)

