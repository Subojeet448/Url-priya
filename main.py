"""
main.py  –  AI Engine (Clean v1)
Flask | OpenRouter | PPLX + DuckDuckGo | Cache | Rate Limit
"""

import os, sys
sys.path.insert(0, os.path.dirname(__file__))

import time
import json
import logging
import threading
from collections import defaultdict
from datetime import datetime
from flask import Flask, request, jsonify

from config import PORT, DEBUG, RATE_LIMIT_COUNT, RATE_LIMIT_WINDOW
import cache as Cache
from router import detect_intent
from modules.search import smart_search
from modules.ai import ai_with_failover, key_statuses, model_statuses

# ── Logging ──────────────────────────────────────────────
os.makedirs("logs", exist_ok=True)
os.makedirs("temp", exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("logs/app.log"),
    ],
)
logger = logging.getLogger(__name__)

# ── Flask ────────────────────────────────────────────────
app = Flask(__name__)
app.config["JSON_SORT_KEYS"] = False

# ── Metrics ──────────────────────────────────────────────
_metrics = {
    "total": 0, "ok": 0, "fail": 0, "searches": 0,
    "start": datetime.now(),
}
_m_lock = threading.Lock()

def _update(ok=True, search=False):
    with _m_lock:
        _metrics["total"] += 1
        _metrics["ok" if ok else "fail"] += 1
        if search:
            _metrics["searches"] += 1

# ── Rate limiter ─────────────────────────────────────────
_rate: dict = defaultdict(list)  # ip -> [timestamps]
_r_lock = threading.Lock()

def _is_rate_limited(ip: str) -> bool:
    now = time.time()
    with _r_lock:
        hits = [t for t in _rate[ip] if now - t < RATE_LIMIT_WINDOW]
        _rate[ip] = hits
        if len(hits) >= RATE_LIMIT_COUNT:
            return True
        _rate[ip].append(now)
    return False

# ── Temp cleaner (runs every 10 min) ─────────────────────
def _clean_temp():
    import glob
    while True:
        time.sleep(600)
        for f in glob.glob("temp/*"):
            try:
                os.remove(f)
            except Exception:
                pass
        Cache.cleanup()

threading.Thread(target=_clean_temp, daemon=True).start()


# ── Routes ───────────────────────────────────────────────

@app.route("/", methods=["GET"])
def home():
    return jsonify({
        "service": "AI Engine v1",
        "endpoints": {
            "POST /chat":  "{prompt}",
            "GET  /health": "health check",
            "GET  /status": "models & keys",
        },
        "status": "running",
    })


@app.route("/chat", methods=["POST"])
def chat():
    ip = request.remote_addr or "unknown"

    # Rate limit
    if _is_rate_limited(ip):
        return jsonify({"error": "Too many requests. Try after a few seconds.", "status": "rate_limited"}), 429

    data = request.get_json(force=True, silent=True) or {}
    prompt = (data.get("prompt") or data.get("message") or "").strip()

    if not prompt:
        return jsonify({"error": "prompt is required", "status": "error"}), 400

    t0 = time.time()

    # Cache hit
    cached = Cache.get(prompt)
    if cached:
        logger.info(f"Cache hit for: {prompt[:60]}")
        return jsonify({
            "response": cached,
            "cached": True,
            "status": "success",
        })

    # Route intent
    intent = detect_intent(prompt)
    search_context = ""
    search_used = False

    if intent == "search":
        result = smart_search(prompt)
        if result:
            search_used = True
            # Build clean context for AI
            parts = []
            if result.get("answer"):
                parts.append(f"Answer: {result['answer']}")
            for s in result.get("sources", []):
                if s.get("snippet"):
                    parts.append(f"- {s['title']}: {s['snippet']}")
            search_context = "\n".join(parts)

    # AI call
    try:
        reply = ai_with_failover(prompt, search_context)
    except Exception as e:
        logger.error(f"AI failed: {e}")
        _update(ok=False, search=search_used)
        return jsonify({"error": "AI unavailable. Please try again.", "status": "error"}), 500

    # Save to cache
    Cache.set(prompt, reply)
    _update(ok=True, search=search_used)

    elapsed = round(time.time() - t0, 2)
    logger.info(f"[{ip}] intent={intent} search={search_used} time={elapsed}s")

    return jsonify({
        "response": reply,
        "search_used": search_used,
        "processing_time": f"{elapsed}s",
        "cached": False,
        "status": "success",
    })


@app.route("/health", methods=["GET"])
def health():
    with _m_lock:
        total = _metrics["total"]
        ok    = _metrics["ok"]
        uptime = int((datetime.now() - _metrics["start"]).total_seconds())
        rate = f"{round(ok/total*100, 1)}%" if total else "N/A"

    return jsonify({
        "status": "healthy",
        "uptime_seconds": uptime,
        "total_requests": total,
        "success_rate": rate,
        "searches_done": _metrics["searches"],
    })


@app.route("/status", methods=["GET"])
def status():
    return jsonify({
        "api_keys": key_statuses(),
        "models":   model_statuses(),
        "timestamp": datetime.now().isoformat(),
    })


@app.errorhandler(404)
def not_found(_):
    return jsonify({"error": "Not found", "status": "error"}), 404

@app.errorhandler(500)
def server_error(_):
    return jsonify({"error": "Server error", "status": "error"}), 500


# ── Start ────────────────────────────────────────────────
if __name__ == "__main__":
    print(f"\n🤖 AI Engine running → http://localhost:{PORT}\n")
    app.run(host="0.0.0.0", port=PORT, debug=DEBUG, threaded=True)
