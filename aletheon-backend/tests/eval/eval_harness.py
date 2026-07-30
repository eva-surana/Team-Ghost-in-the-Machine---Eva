"""
Grounding & Recommendation Evaluation Harness + CPU Latency Benchmark

Run with:  pytest tests/eval/ -v -s

Prints a summary table of:
  - Verifier precision/recall/F1 at catching unsupported claims
  - Classifier provenance & training data size report
  - Recommendation engine accuracy (checking if known related papers surface)
  - CPU latency per document for the full pipeline
"""
from __future__ import annotations

import asyncio
import time
from typing import Any

import pytest
from tabulate import tabulate

from app.models.schemas import SourceSpan
from app.verification.verifier import VerificationEngine
from app.recommendation.corpus_index import CorpusIndex
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.parent
CORPUS_DIR = PROJECT_ROOT / "corpus"

# ── Ground-truth evaluation dataset ──────────────────────────────────────────

EVAL_DATASET = [
    {
        "doc_id": "eval_p1",
        "title": "Attention Is All You Need",
        "spans": [
            SourceSpan(
                source_id="p1_s1", document_id="eval_p1", page=1, section="Abstract",
                text="We propose the Transformer, a model architecture relying entirely on self-attention mechanisms, dispensing with recurrence entirely."
            ),
            SourceSpan(
                source_id="p1_s2", document_id="eval_p1", page=1, section="Results",
                text="Our model achieves 28.4 BLEU on WMT 2014 English-to-German translation."
            ),
        ],
        "claims": [
            {
                "text": "The Transformer relies on self-attention and dispenses with recurrence.",
                "cited_ids": ["p1_s1"], "expected": "verified"
            },
            {
                "text": "The model achieves 28.4 BLEU on WMT 2014 English-German translation.",
                "cited_ids": ["p1_s2"], "expected": "verified"
            },
            {
                "text": "The Transformer model was invented in 1920 for telegraph routing.",
                "cited_ids": ["p1_s1"], "expected": "unsupported"
            },
            {
                "text": "The model achieves zero latency using quantum circuits.",
                "cited_ids": ["p1_s2"], "expected": "unsupported"
            },
        ],
    },
    {
        "doc_id": "eval_p2",
        "title": "BERT: Pre-training of Deep Bidirectional Transformers",
        "spans": [
            SourceSpan(
                source_id="p2_s1", document_id="eval_p2", page=1, section="Introduction",
                text="BERT is designed to pre-train deep bidirectional representations by jointly conditioning on both left and right context in all layers."
            ),
            SourceSpan(
                source_id="p2_s2", document_id="eval_p2", page=2, section="Results",
                text="BERT sets new state-of-the-art results on eleven NLP tasks."
            ),
        ],
        "claims": [
            {
                "text": "BERT pre-trains deep bidirectional representations conditioning on both context directions.",
                "cited_ids": ["p2_s1"], "expected": "verified"
            },
            {
                "text": "BERT achieves state-of-the-art on eleven NLP benchmarks.",
                "cited_ids": ["p2_s2"], "expected": "verified"
            },
            {
                "text": "BERT requires no fine-tuning and runs exclusively on blockchain nodes.",
                "cited_ids": ["p2_s1"], "expected": "unsupported"
            },
        ],
    },
]


async def _run_eval() -> dict[str, Any]:
    ve = VerificationEngine()
    spans_lookup: dict[str, dict[str, SourceSpan]] = {
        p["doc_id"]: {s.source_id: s for s in p["spans"]}
        for p in EVAL_DATASET
    }

    tp = fp = fn = tn = 0
    total_latency_ms = 0.0
    paper_rows = []

    for paper in EVAL_DATASET:
        doc_id = paper["doc_id"]
        p_total = p_verified = p_unsupported = 0

        t0 = time.perf_counter()
        for item in paper["claims"]:
            p_total += 1
            cited_spans = [
                spans_lookup[doc_id][sid]
                for sid in item["cited_ids"]
                if sid in spans_lookup[doc_id]
            ]
            verdict, _, _ = ve.verify(doc_id, item["text"], cited_spans)
            expected = item["expected"]

            if verdict == "unsupported":
                p_unsupported += 1
                if expected == "unsupported":
                    tp += 1
                else:
                    fp += 1
            else:
                p_verified += 1
                if expected == "unsupported":
                    fn += 1
                else:
                    tn += 1

        elapsed_ms = (time.perf_counter() - t0) * 1000
        total_latency_ms += elapsed_ms
        paper_rows.append([doc_id, paper["title"][:42], p_total, p_verified, p_unsupported, f"{elapsed_ms:.2f} ms"])

    precision = tp / (tp + fp) if (tp + fp) > 0 else 1.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 1.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0
    avg_latency = total_latency_ms / len(EVAL_DATASET)

    headers = ["Doc ID", "Paper Title", "Total", "Verified", "Unsupported", "Latency"]
    table = tabulate(paper_rows, headers=headers, tablefmt="github")

    # Recommendation eval
    rec_pass = False
    if CORPUS_DIR.exists():
        idx = CorpusIndex.build(CORPUS_DIR)
        m = idx.find_similar("Attention Is All You Need Transformer self-attention mechanisms", top_k=2)
        rec_pass = len(m) > 0 and m[0].paper_id == "vaswani2017attention"

    report = f"""
{'=' * 70}
         ALETHEON GROUNDING & EVALUATION REPORT (NO PRETRAINED WEIGHTS)
{'=' * 70}
{table}

{'─' * 70}
VERIFIER METRICS (Self-Trained LogisticRegression):
  Total claims evaluated : {tp + fp + tn + fn}
  Precision (unsupported): {precision:.4f}  ({precision * 100:.1f}%)
  Recall    (unsupported): {recall:.4f}  ({recall * 100:.1f}%)
  F1 Score               : {f1:.4f}
  Avg latency / doc      : {avg_latency:.2f} ms

RECOMMENDATION ENGINE EVAL:
  Top-1 Match Test       : {'PASS' if rec_pass else 'FAIL'} (query: 'transformer attention')

HONEST CEILING & PROVENANCE SUMMARY:
  - Verifier model: LogisticRegression on 6 lexical features (TF-IDF cos, Jaccard, negation, etc.)
  - Training dataset size: 117 labeled triples from training_data/entailment_triples.jsonl
  - Scope: High precision on numeric mismatch & negation flips; relies on corpus expansion for domain coverage.
{'=' * 70}
"""
    print(report)
    return {
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "avg_latency_ms": avg_latency,
        "recommendation_test_pass": rec_pass,
    }


@pytest.mark.asyncio
async def test_grounding_eval_harness():
    results = await _run_eval()
    assert results["precision"] >= 0.70, f"Precision too low: {results['precision']:.2%}"
    assert results["recall"] >= 0.70, f"Recall too low: {results['recall']:.2%}"
    assert results["avg_latency_ms"] < 5_000, f"Latency too high: {results['avg_latency_ms']:.0f}ms"


if __name__ == "__main__":
    asyncio.run(_run_eval())
