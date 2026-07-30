"""
router.py — FastAPI routes for the online recommendations feature.

This is the only router in the codebase that may make network calls.
All network I/O is gated behind ENABLE_ONLINE_RECOMMENDATIONS (default: false).

When disabled:
  Every request returns {"available": false, "reason": "feature_disabled"}
  without importing connectivity.py or any HTTP client.

When enabled but offline:
  Returns {"available": false, "reason": "offline"} plus any cached
  results (source_mode: "cached"), labeled with their fetch date.

When enabled and online:
  Builds a search profile from already-ingested DNA data, fetches from
  Semantic Scholar + arXiv, re-ranks locally via TF-IDF cosine similarity,
  caches results, and returns source_mode: "live".

Rate limiting:
  POST /refresh is rate-limited client-side via cache TTL.
  If a fresh cache exists, refresh is a no-op that returns the cached results.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, HTTPException

from app.config import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/documents", tags=["Online Recommendations"])

_DISABLED_RESPONSE: dict[str, Any] = {
    "available": False,
    "reason": "feature_disabled",
    "source_mode": "unavailable",
    "checked_at": None,
    "recommendations": [],
}


def _build_unavailable(reason: str, cached_results: list | None = None,
                        fetched_at: str | None = None) -> dict:
    cache_age_hours = None
    if fetched_at:
        try:
            fetched_dt = datetime.fromisoformat(fetched_at)
            now_dt = datetime.now(timezone.utc)
            cache_age_hours = round(max(0.0, (now_dt - fetched_dt).total_seconds() / 3600.0), 1)
        except Exception:
            pass

    return {
        "available": False,
        "reason": reason,
        "source_mode": "cached" if cached_results else "unavailable",
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "recommendations": cached_results or [],
        "cache_fetched_at": fetched_at,
        "cache_age_hours": cache_age_hours,
    }


async def _get_recommendations(doc_id: str, force_refresh: bool = False) -> dict:
    """Core logic shared between GET and POST/refresh endpoints."""
    # ── Feature gate — short circuit before any network import ───────────────
    if not settings.ENABLE_ONLINE_RECOMMENDATIONS:
        return dict(_DISABLED_RESPONSE)

    # Lazy imports — only loaded when feature is enabled
    from app.recommendations import cache as reco_cache
    from app.recommendations.client import fetch_candidates
    from app.recommendations.connectivity import is_online
    from app.recommendations.ranking import build_profile_text, rank_candidates

    # ── Check cache first ────────────────────────────────────────────────────
    cached_results, fetched_at = reco_cache.get_cached(doc_id)

    if cached_results and not force_refresh and reco_cache.is_cache_fresh(fetched_at):
        cache_age_hours = None
        if fetched_at:
            try:
                fetched_dt = datetime.fromisoformat(fetched_at)
                now_dt = datetime.now(timezone.utc)
                cache_age_hours = round(max(0.0, (now_dt - fetched_dt).total_seconds() / 3600.0), 1)
            except Exception:
                pass
        return {
            "available": True,
            "source_mode": "cached",
            "checked_at": datetime.now(timezone.utc).isoformat(),
            "recommendations": cached_results,
            "cache_fetched_at": fetched_at,
            "cache_age_hours": cache_age_hours,
        }

    # ── Connectivity check ───────────────────────────────────────────────────
    checked_at = datetime.now(timezone.utc).isoformat()
    if not is_online():
        return _build_unavailable("offline", cached_results, fetched_at)

    # ── Build search profile (local, no network) ─────────────────────────────
    profile_text = build_profile_text(doc_id)
    if not profile_text.strip():
        return _build_unavailable("no_profile", cached_results, fetched_at)

    # Extract a concise keyword query from the profile
    import re
    keywords = " ".join(re.findall(r"\b[a-z]{4,}\b", profile_text.lower()))[:200]
    if not keywords.strip():
        keywords = profile_text[:100]

    # ── Fetch from external APIs ─────────────────────────────────────────────
    candidates = fetch_candidates(keywords, ss_limit=15, arxiv_limit=10)
    if not candidates:
        return _build_unavailable("api_empty", cached_results, fetched_at)

    # ── Local re-ranking ─────────────────────────────────────────────────────
    ranked = rank_candidates(profile_text, candidates, top_k=8)

    # ── Cache and return ─────────────────────────────────────────────────────
    new_fetched_at = reco_cache.store_cache(doc_id, ranked)

    return {
        "available": True,
        "source_mode": "live",
        "checked_at": checked_at,
        "recommendations": ranked,
        "cache_fetched_at": new_fetched_at,
    }


@router.get("/{doc_id}/recommendations")
async def get_online_recommendations(doc_id: str):
    """
    Fetch online paper recommendations for the given document.

    Returns available: false immediately if ENABLE_ONLINE_RECOMMENDATIONS=false.
    Otherwise: live results if online, cached results if offline.
    """
    return await _get_recommendations(doc_id, force_refresh=False)


@router.post("/{doc_id}/recommendations/refresh")
async def refresh_online_recommendations(doc_id: str):
    """
    Force a re-fetch from external APIs, bypassing the cache.

    Rate-limited via cache TTL: if the existing cache is still fresh,
    returns cached results rather than hammering the external API.
    """
    if not settings.ENABLE_ONLINE_RECOMMENDATIONS:
        return dict(_DISABLED_RESPONSE)

    from app.recommendations import cache as reco_cache
    _, fetched_at = reco_cache.get_cached(doc_id)
    if fetched_at and reco_cache.is_cache_fresh(fetched_at):
        # Cache is fresh — return it, don't hit external API
        from app.recommendations import cache as reco_cache2
        cached_results, fetched_at2 = reco_cache2.get_cached(doc_id)
        return {
            "available": True,
            "source_mode": "cached",
            "checked_at": datetime.now(timezone.utc).isoformat(),
            "recommendations": cached_results or [],
            "cache_fetched_at": fetched_at2,
            "note": "Cache is still fresh. Refresh rate limit applies.",
        }

    return await _get_recommendations(doc_id, force_refresh=True)
