import time
import logging
import requests
from datetime import datetime, timedelta
from threading import Lock
from collections import defaultdict

from config import (
    OPENROUTER_KEYS, PRIMARY_MODELS,
    OPENROUTER_URL, AI_TIMEOUT,
    KEY_COOLDOWN, MODEL_COOLDOWN
)
from prompt import SYSTEM_PROMPT

logger = logging.getLogger(__name__)

_lock = Lock()
_key_rest: dict   = defaultdict(lambda: None)   # key_index -> datetime | None
_model_rest: dict = defaultdict(lambda: None)   # model_name -> datetime | None


# ── Cooldown helpers ─────────────────────────────────────

def _is_resting(rest_until) -> bool:
    return rest_until is not None and datetime.now() < rest_until


def _rest_key(idx: int):
    with _lock:
        _key_rest[idx] = datetime.now() + timedelta(seconds=KEY_COOLDOWN)
    logger.warning(f"API key {idx} on cooldown for {KEY_COOLDOWN}s")


def _rest_model(model: str):
    with _lock:
        _model_rest[model] = datetime.now() + timedelta(seconds=MODEL_COOLDOWN)
    logger.warning(f"Model {model} on cooldown for {MODEL_COOLDOWN}s")


def _active_key():
    """Return (key, index) of first available key."""
    for i, key in enumerate(OPENROUTER_KEYS):
        if not _is_resting(_key_rest[i]):
            return key, i
    return OPENROUTER_KEYS[0], 0   # all resting – try anyway


def key_statuses() -> list:
    now = datetime.now()
    result = []
    for i in range(len(OPENROUTER_KEYS)):
        rest = _key_rest[i]
        result.append({
            "index":  i,
            "status": "resting" if _is_resting(rest) else "active",
            "rest_until": rest.isoformat() if rest else None,
        })
    return result


def model_statuses() -> list:
    now = datetime.now()
    result = []
    for m in PRIMARY_MODELS:
        rest = _model_rest[m]
        result.append({
            "model":  m,
            "status": "resting" if _is_resting(rest) else "active",
            "rest_until": rest.isoformat() if rest else None,
        })
    return result


# ── Core call ────────────────────────────────────────────

def _call(messages: list, model: str, api_key: str) -> str:
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://ai-engine.local",
    }
    payload = {
        "model": model,
        "messages": messages,
        "temperature": 0.7,
        "max_tokens": 800,
    }
    resp = requests.post(OPENROUTER_URL, json=payload, headers=headers, timeout=AI_TIMEOUT)
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"].strip()


# ── Failover entry point ─────────────────────────────────

def ai_with_failover(user_prompt: str, search_context: str = "") -> str:
    """Try each model × each key. Return first success."""

    # Build messages
    content = user_prompt
    if search_context:
        content = (
            f"{user_prompt}\n\n"
            f"[Search Results]\n{search_context}\n\n"
            "Use the above search results to give an accurate answer."
        )

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user",   "content": content},
    ]

    last_error = None

    for model in PRIMARY_MODELS:
        if _is_resting(_model_rest[model]):
            logger.info(f"Skipping {model} (cooldown)")
            continue

        for attempt in range(len(OPENROUTER_KEYS)):
            api_key, key_idx = _active_key()

            try:
                logger.info(f"Trying model={model} key={key_idx}")
                reply = _call(messages, model, api_key)

                # Mark both as healthy
                with _lock:
                    _key_rest[key_idx]  = None
                    _model_rest[model]  = None

                return reply

            except Exception as e:
                last_error = str(e)
                _rest_key(key_idx)
                time.sleep(0.3)

        _rest_model(model)

    raise RuntimeError(f"All models/keys failed. Last: {last_error}")
