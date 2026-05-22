"""Tests for the in-memory WebAuthn challenge store."""

from __future__ import annotations

import pytest
from fastapi import HTTPException

from app.auth import passkey


@pytest.fixture(autouse=True)
def _clear_challenges() -> None:
    passkey._challenges.clear()
    yield
    passkey._challenges.clear()


def test_challenge_store_evicts_oldest_when_full(monkeypatch: pytest.MonkeyPatch) -> None:
    now = [1000]
    monkeypatch.setattr(passkey.time, "time", lambda: now[0])
    monkeypatch.setattr(passkey, "MAX_CHALLENGES", 3)

    handles: list[str] = []
    for i in range(4):
        now[0] += 1
        handles.append(passkey._store_challenge(f"challenge-{i}".encode(), "login"))

    assert len(passkey._challenges) == 3
    with pytest.raises(HTTPException, match="challenge expired or unknown"):
        passkey._pop_challenge(handles[0], "login")
    assert passkey._pop_challenge(handles[-1], "login") == b"challenge-3"


def test_challenge_store_purges_stale_entries(monkeypatch: pytest.MonkeyPatch) -> None:
    now = [2000]
    monkeypatch.setattr(passkey.time, "time", lambda: now[0])
    stale = passkey._store_challenge(b"old", "reg")

    now[0] += passkey.CHALLENGE_TTL + 1
    fresh = passkey._store_challenge(b"new", "reg")

    assert stale not in passkey._challenges
    assert passkey._pop_challenge(fresh, "reg") == b"new"
