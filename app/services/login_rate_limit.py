"""In-process rate limiter for the login form.

We already have three speed bumps in front of password brute-force:

  1. /login/{12-char-suffix}     — bots that don't know the path can't
                                    even probe the form (bare /login is 404)
  2. random 16-char admin pwd   — install.sh generates this, ~95 bits
  3. constant-time compare       — no timing oracle on partial matches

This adds a fourth bump: per-IP failure counter with progressive delay.
After ``FAIL_THRESHOLD`` failed attempts inside ``WINDOW_SEC`` the next
attempt sleeps before responding — 1 s → 2 s → 4 s → 8 s → 16 s →
``MAX_DELAY_SEC``, capped at one minute. A single successful login (or
WINDOW_SEC of no traffic) clears the counter.

Storage is a single-process in-memory dict — ProxyBox is a single
admin process per VPS, so we don't need a shared store like Redis. If
the process restarts the counter resets, which is OK: an attacker who
can crash + restart uvicorn already has root.
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass

# Tunables — values picked to be punishing without becoming a denial-of-
# service vector against a legit operator who fat-fingers a few times.
FAIL_THRESHOLD = 5  # free attempts before delay kicks in
WINDOW_SEC = 15 * 60  # bucket window: 15 minutes of no failures = reset
MAX_DELAY_SEC = 60  # cap progressive delay at 60 s


@dataclass
class _Entry:
    fails: int = 0
    last_fail_ts: float = 0.0


_state: dict[str, _Entry] = {}
_lock = threading.Lock()


def _now() -> float:
    return time.monotonic()


def _entry_for(ip: str) -> _Entry:
    """Read-or-create with stale-bucket eviction. Caller holds _lock."""
    e = _state.get(ip)
    if e is None or (_now() - e.last_fail_ts) > WINDOW_SEC:
        e = _Entry()
        _state[ip] = e
    return e


def delay_for(ip: str) -> float:
    """Return how long the caller should sleep before responding.

    Returns 0 when the IP is below the threshold or its window has aged
    out; otherwise a doubling backoff capped at MAX_DELAY_SEC.

    Does NOT block — callers (FastAPI handlers are async) decide how
    to wait. This keeps the rate-limit math testable.
    """
    with _lock:
        e = _entry_for(ip)
        if e.fails < FAIL_THRESHOLD:
            return 0.0
        excess = e.fails - FAIL_THRESHOLD
        return min(2.0**excess, MAX_DELAY_SEC)


def record_fail(ip: str) -> int:
    """Bump the failure counter for ``ip``. Returns the new count."""
    with _lock:
        e = _entry_for(ip)
        e.fails += 1
        e.last_fail_ts = _now()
        return e.fails


def record_success(ip: str) -> None:
    """Reset the failure counter on a successful login."""
    with _lock:
        _state.pop(ip, None)


# Test / admin helpers — never called from production handlers.


def _reset_all_for_tests() -> None:
    with _lock:
        _state.clear()


def current_fail_count(ip: str) -> int:
    with _lock:
        e = _state.get(ip)
        if e is None:
            return 0
        if (_now() - e.last_fail_ts) > WINDOW_SEC:
            return 0
        return e.fails
