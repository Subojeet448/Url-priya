import requests
import logging
from config import PPLX_API_URL, SEARCH_TIMEOUT

logger = logging.getLogger(__name__)


def _clean_results(raw: list) -> list:
    """Keep only title, snippet, link from each result."""
    clean = []
    for item in raw:
        clean.append({
            "title":   item.get("title", ""),
            "snippet": item.get("body") or item.get("snippet") or item.get("description", ""),
            "link":    item.get("href") or item.get("link") or item.get("url", ""),
        })
    return clean


def search_pplx(query: str) -> dict | None:
    """Primary: PPLX API."""
    try:
        resp = requests.get(
            PPLX_API_URL,
            params={"prompt": query},
            timeout=SEARCH_TIMEOUT
        )
        resp.raise_for_status()
        data = resp.json()

        answer  = data.get("answer") or data.get("response") or ""
        sources = data.get("sources") or data.get("results") or []

        return {
            "answer":  answer.strip(),
            "sources": _clean_results(sources[:3]),
        }
    except Exception as e:
        logger.warning(f"PPLX search failed: {e}")
        return None


def search_duckduckgo(query: str) -> dict | None:
    """Fallback: DuckDuckGo (no key needed)."""
    try:
        from duckduckgo_search import DDGS
        raw = DDGS().text(query, max_results=3)
        if not raw:
            return None
        return {
            "answer":  "",
            "sources": _clean_results(raw),
        }
    except Exception as e:
        logger.warning(f"DuckDuckGo search failed: {e}")
        return None


def smart_search(query: str) -> dict | None:
    """PPLX → DuckDuckGo fallback."""
    result = search_pplx(query)
    if result:
        return result
    return search_duckduckgo(query)
