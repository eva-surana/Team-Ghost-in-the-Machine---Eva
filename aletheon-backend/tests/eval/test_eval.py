"""Thin test runner that imports from the new eval_harness."""
import pytest
from tests.eval.eval_harness import _run_eval


@pytest.mark.asyncio
async def test_grounding_eval_harness():
    results = await _run_eval()
    assert results["precision"] >= 0.75, f"Precision too low: {results['precision']:.2%}"
    assert results["recall"] >= 0.75, f"Recall too low: {results['recall']:.2%}"
    assert results["avg_latency_ms"] < 10_000
