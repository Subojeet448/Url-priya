"""
router.py  –  Decide intent: SEARCH or CHAT
"""

SEARCH_KEYWORDS = {
    "price", "news", "latest", "current", "today", "now", "search",
    "update", "rate", "exchange", "trend", "bitcoin", "crypto",
    "stock", "weather", "usdt", "btc", "who won", "score",
    "breaking", "live", "recently", "this week", "2024", "2025",
}


def detect_intent(prompt: str) -> str:
    """Return 'search' or 'chat'."""
    words = prompt.lower().split()
    for w in words:
        if w.rstrip("?,!.") in SEARCH_KEYWORDS:
            return "search"
    return "chat"
