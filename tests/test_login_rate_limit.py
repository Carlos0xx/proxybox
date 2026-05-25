"""Tests for app.services.login_rate_limit.

Defensive depth in front of /login/{secret} brute-force. The module is
process-local in-memory state, so each test resets between runs.
"""

from __future__ import annotations

import pytest

from app.services import login_rate_limit as lrl


@pytest.fixture(autouse=True)
def _reset() -> None:
    lrl._reset_all_for_tests()


def test_first_attempts_have_no_delay() -> None:
    for _ in range(lrl.FAIL_THRESHOLD):
        assert lrl.delay_for("1.1.1.1") == 0.0
        lrl.record_fail("1.1.1.1")


def test_delay_kicks_in_after_threshold_and_doubles() -> None:
    ip = "2.2.2.2"
    # Burn through the free attempts.
    for _ in range(lrl.FAIL_THRESHOLD):
        lrl.record_fail(ip)
    # First over-threshold attempt: 2^0 = 1 s.
    assert lrl.delay_for(ip) == 1.0
    lrl.record_fail(ip)
    # 2^1 = 2 s.
    assert lrl.delay_for(ip) == 2.0
    lrl.record_fail(ip)
    # 2^2 = 4 s.
    assert lrl.delay_for(ip) == 4.0


def test_delay_caps_at_max() -> None:
    ip = "3.3.3.3"
    for _ in range(lrl.FAIL_THRESHOLD + 30):
        lrl.record_fail(ip)
    # 2^30 would be ~10^9 seconds. Verify the cap holds.
    assert lrl.delay_for(ip) == lrl.MAX_DELAY_SEC


def test_record_success_resets_counter() -> None:
    ip = "4.4.4.4"
    for _ in range(lrl.FAIL_THRESHOLD + 2):
        lrl.record_fail(ip)
    assert lrl.delay_for(ip) > 0
    lrl.record_success(ip)
    assert lrl.delay_for(ip) == 0.0
    assert lrl.current_fail_count(ip) == 0


def test_window_eviction_after_stale_period(monkeypatch: pytest.MonkeyPatch) -> None:
    """A bucket that has not been touched for > WINDOW_SEC should reset."""
    ip = "5.5.5.5"
    # Fake the monotonic clock so we can fast-forward without sleeping.
    fake_now = [1000.0]
    monkeypatch.setattr(lrl, "_now", lambda: fake_now[0])

    for _ in range(lrl.FAIL_THRESHOLD):
        lrl.record_fail(ip)
    assert lrl.current_fail_count(ip) == lrl.FAIL_THRESHOLD

    # Jump well past the window — next read should see a fresh bucket.
    fake_now[0] += lrl.WINDOW_SEC + 1
    assert lrl.current_fail_count(ip) == 0
    assert lrl.delay_for(ip) == 0.0


def test_per_ip_isolation() -> None:
    """One offender's failures don't penalise a different IP."""
    for _ in range(lrl.FAIL_THRESHOLD + 3):
        lrl.record_fail("10.0.0.1")
    assert lrl.delay_for("10.0.0.1") > 0
    assert lrl.delay_for("10.0.0.2") == 0.0
