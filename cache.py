import time

# { prompt_hash: {"response": "...", "expires": timestamp} }
_CACHE: dict = {}
CACHE_TTL = 300  # 5 minutes


def _key(prompt: str) -> str:
    return str(hash(prompt.strip().lower()))


def get(prompt: str):
    k = _key(prompt)
    entry = _CACHE.get(k)
    if entry and time.time() < entry["expires"]:
        return entry["response"]
    return None


def set(prompt: str, response: str):
    k = _key(prompt)
    _CACHE[k] = {"response": response, "expires": time.time() + CACHE_TTL}


def cleanup():
    """Remove expired entries."""
    now = time.time()
    expired = [k for k, v in _CACHE.items() if now >= v["expires"]]
    for k in expired:
        del _CACHE[k]
