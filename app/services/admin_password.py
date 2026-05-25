"""Out-of-band storage for the admin password.

The admin password used to live inline in ``/etc/proxybox/config.yaml``.
That is operationally convenient — one ``cat`` recovers the value when an
operator forgets it — but it also means anyone who can read the YAML can
read the password, even when the file is mode 0600. The risk is mostly
non-attacker: screenshots during a debug session, automated backups that
slurp ``/etc/``, copy-pasting a snippet into a chat for support.

Splitting the password into its own file (``/etc/proxybox/admin.password``,
mode 0400, root-owned) keeps the recovery UX (``ssh root@vps cat /etc/...``)
while letting ``cat /etc/proxybox/config.yaml`` stay screenshot-safe.

The helpers below are the only place that writes that file — install.sh,
the Docker bootstrap, and the account POST handler all funnel through here.
Atomic-write via tmp+rename so a crash mid-rotate can never leave the
file half-written.
"""

from __future__ import annotations

import contextlib
import os
from pathlib import Path


def write(path: Path, password: str) -> None:
    """Write ``password`` to ``path`` atomically, mode 0400.

    Removes any trailing whitespace from the password; the loader strips
    the same on read so a stray newline doesn't break login.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    # Open with restrictive umask so the tmp file can never appear briefly
    # at 0644. fdopen for explicit close-on-error semantics.
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o400)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(password.strip())
    except BaseException:
        with contextlib.suppress(FileNotFoundError):
            tmp.unlink()
        raise
    os.replace(tmp, path)
    path.chmod(0o400)


def read(path: Path) -> str:
    """Return the password from ``path``, or '' if file missing / unreadable."""
    try:
        return path.read_text(encoding="utf-8").strip()
    except (FileNotFoundError, PermissionError, OSError):
        return ""
