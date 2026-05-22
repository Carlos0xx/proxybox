"""subprocess wrapper with sane defaults.

Returns the child's stdout on success, '' on any failure (timeout, non-zero
exit, missing binary). Never raises — every caller is in a hot read path
(``/api/status``, ``/api/bans``, ``/api/logs``) that should degrade
gracefully when the host's user-space tools are unavailable.

Security contract: ``cmd`` MUST be a Sequence[str]. We never accept a raw
string and ``shell=`` is always False. A string command is rejected with
TypeError at runtime to surface accidental introductions early (lint /
test) instead of letting a future command-injection vulnerability slide
in behind an innocent-looking f-string.
"""

from __future__ import annotations

import subprocess
from collections.abc import Sequence


def run(cmd: Sequence[str], timeout: int = 8) -> str:
    """Run ``cmd`` (an argv list), return stdout. Empty string on any failure."""
    if isinstance(cmd, str) or not isinstance(cmd, Sequence):
        # Catch accidental f-string commands at the call site — pipes and
        # shell metachars should be replaced by an explicit Python pipeline.
        raise TypeError("shell.run requires a list/tuple of argv, not a string")
    try:
        result = subprocess.run(
            list(cmd),
            shell=False,  # explicit — no string interpretation
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
        return result.stdout
    except (subprocess.TimeoutExpired, subprocess.SubprocessError, OSError):
        return ""
