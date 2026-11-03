"""Small in-memory limiter: at most N AI calls per user per window."""
import threading
import time
from fastapi import HTTPException
from . import config

_lock = threading.Lock()
_calls: dict[str, list[float]] = {}


def check_ai_rate(user_id: str):
    now = time.time()
    with _lock:
        recent = [t for t in _calls.get(user_id, []) if now - t < config.AI_WINDOW_SECONDS]
        if len(recent) >= config.AI_CALLS_PER_WINDOW:
            raise HTTPException(429, {"message": "You're going a little fast. Please wait a few minutes and try again.",
                                      "ref": "rate-limit"})
        recent.append(now)
        _calls[user_id] = recent
