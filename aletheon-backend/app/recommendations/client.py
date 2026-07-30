"""
client.py — HTTP clients for Semantic Scholar and arXiv APIs.

Called ONLY when ENABLE_ONLINE_RECOMMENDATIONS=true AND connectivity check passes.
Never imported by the core pipeline.

Semantic Scholar Graph API:
  https://api.semanticscholar.org/graph/v1/paper/search
  No API key required at low volume.

arXiv API:
  https://export.arxiv.org/api/query
  No API key required.
"""
from __future__ import annotations

import logging
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

_SS_BASE = "https://api.semanticscholar.org/graph/v1/paper/search"
_ARXIV_BASE = "https://export.arxiv.org/api/query"
_REQUEST_TIMEOUT = 10
_USER_AGENT = "Aletheon-Research-Assistant/2.0 (research tool; contact: aletheon@example.com)"


@dataclass
class CandidatePaper:
    title: str
    authors: list[str] = field(default_factory=list)
    year: int | None = None
    abstract: str = ""
    url: str = ""
    source: str = ""    # "semantic_scholar" | "arxiv"


def _get(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": _USER_AGENT})
    with urllib.request.urlopen(req, timeout=_REQUEST_TIMEOUT) as resp:
        return resp.read()


def fetch_semantic_scholar(query: str, limit: int = 15) -> list[CandidatePaper]:
    """
    Search Semantic Scholar Graph API.
    Returns up to `limit` CandidatePaper objects.
    """
    params = urllib.parse.urlencode({
        "query": query,
        "limit": limit,
        "fields": "title,authors,year,abstract,url,externalIds",
    })
    url = f"{_SS_BASE}?{params}"
    try:
        raw = _get(url)
        import json
        data = json.loads(raw)
        papers = []
        for p in data.get("data", []):
            authors = [a.get("name", "") for a in p.get("authors", [])]
            ext = p.get("externalIds") or {}
            paper_url = p.get("url") or (
                f"https://doi.org/{ext['DOI']}" if "DOI" in ext else
                f"https://arxiv.org/abs/{ext['ArXiv']}" if "ArXiv" in ext else ""
            )
            papers.append(CandidatePaper(
                title=p.get("title", ""),
                authors=authors,
                year=p.get("year"),
                abstract=p.get("abstract") or "",
                url=paper_url,
                source="semantic_scholar",
            ))
        return papers
    except Exception as exc:
        logger.warning(f"[SS Client] Fetch failed: {exc}")
        return []


def fetch_arxiv(query: str, max_results: int = 10) -> list[CandidatePaper]:
    """
    Search arXiv API via Atom feed.
    Returns up to `max_results` CandidatePaper objects.
    """
    params = urllib.parse.urlencode({
        "search_query": f"all:{query}",
        "max_results": max_results,
        "sortBy": "relevance",
    })
    url = f"{_ARXIV_BASE}?{params}"
    try:
        raw = _get(url)
        ns = {"atom": "http://www.w3.org/2005/Atom"}
        root = ET.fromstring(raw)
        papers = []
        for entry in root.findall("atom:entry", ns):
            title = (entry.findtext("atom:title", "", ns) or "").strip().replace("\n", " ")
            abstract = (entry.findtext("atom:summary", "", ns) or "").strip().replace("\n", " ")
            paper_url = ""
            for link in entry.findall("atom:link", ns):
                if link.get("rel") == "alternate":
                    paper_url = link.get("href", "")
                    break
            authors = [
                a.findtext("atom:name", "", ns)
                for a in entry.findall("atom:author", ns)
            ]
            published = entry.findtext("atom:published", "", ns) or ""
            year = int(published[:4]) if published and len(published) >= 4 else None
            if title:
                papers.append(CandidatePaper(
                    title=title, authors=authors, year=year,
                    abstract=abstract, url=paper_url, source="arxiv",
                ))
        return papers
    except Exception as exc:
        logger.warning(f"[arXiv Client] Fetch failed: {exc}")
        return []


def fetch_candidates(query: str, ss_limit: int = 15, arxiv_limit: int = 10) -> list[CandidatePaper]:
    """
    Fetch candidates from both Semantic Scholar and arXiv.
    Rate-safe: sequential with a small delay.
    """
    candidates = fetch_semantic_scholar(query, limit=ss_limit)
    time.sleep(0.5)   # be a good citizen
    candidates += fetch_arxiv(query, max_results=arxiv_limit)
    # Deduplicate by title (case-insensitive)
    seen, unique = set(), []
    for p in candidates:
        key = p.title.lower().strip()
        if key and key not in seen:
            seen.add(key)
            unique.append(p)
    return unique
