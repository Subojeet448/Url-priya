import os

# ── API Keys ──────────────────────────────────────────────
OPENROUTER_KEYS = [
    os.getenv("OPENROUTER_KEY_1", ""),
    os.getenv("OPENROUTER_KEY_2", ""),
    os.getenv("OPENROUTER_KEY_3", ""),
]
OPENROUTER_KEYS = [k for k in OPENROUTER_KEYS if k]  # remove empty

PPLX_API_URL = "https://pplx-api.vercel.app/api/ask"

# ── Models ────────────────────────────────────────────────
PRIMARY_MODELS = [
    "gpt-4o-mini",
    "qwen/qwen-2.5-72b-instruct:free",
    "deepseek/deepseek-chat-v3-0324:free",
]

# ── Timeouts & Limits ────────────────────────────────────
OPENROUTER_URL   = "https://openrouter.ai/api/v1/chat/completions"
AI_TIMEOUT       = 30        # seconds
SEARCH_TIMEOUT   = 10        # seconds
KEY_COOLDOWN     = 300       # 5 min in seconds
MODEL_COOLDOWN   = 120       # 2 min in seconds
RATE_LIMIT_COUNT = 5         # requests
RATE_LIMIT_WINDOW = 10       # seconds

# ── Server ───────────────────────────────────────────────
PORT  = int(os.getenv("PORT", 5000))
DEBUG = os.getenv("DEBUG", "False") == "True"
