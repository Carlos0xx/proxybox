#!/usr/bin/env python3
"""CI wrapper around `detect-secrets scan`.

Usage:  python3 scripts/detect-secrets-ci.py

Runs detect-secrets across every git-tracked file. If a baseline
(``.secrets.baseline``) is present, only findings NOT in the baseline
fail CI — the baseline is the project's curated list of acknowledged
false positives. Without a baseline, ANY finding fails CI (greenfield
mode for new repos).

Exits 0 on clean, 1 on findings, 2 on tool error.
"""

from __future__ import annotations

import json
import pathlib
import subprocess
import sys

BASELINE = pathlib.Path(".secrets.baseline")


def _fail(msg: str, code: int = 2) -> None:
    print(f"detect-secrets-ci: {msg}", file=sys.stderr)
    sys.exit(code)


def _run_scan() -> dict:
    """Invoke detect-secrets in scan mode against the tracked working tree."""
    try:
        result = subprocess.run(
            [
                "detect-secrets",
                "scan",
                "--all-files",
                # Skip git internals, local agent worktrees, virtualenvs, and
                # cache dirs at any depth. These can carry high-entropy
                # housekeeping strings that are not repository secrets.
                "--exclude-files",
                r"(^|/)(\.git|\.claude|\.ruff_cache|\.pytest_cache|node_modules|\.venv|venv)/",
            ],
            capture_output=True,
            text=True,
            check=True,
            timeout=120,
        )
    except FileNotFoundError:
        _fail("detect-secrets not installed (`pip install detect-secrets`)")
    except subprocess.CalledProcessError as e:
        _fail(f"detect-secrets exited {e.returncode}: {e.stderr or e.stdout}")
    except subprocess.TimeoutExpired:
        _fail("detect-secrets timed out after 120 s")
    return json.loads(result.stdout)


def main() -> int:
    if BASELINE.exists():
        # Hook mode: compare scan output against the baseline. Hook exits
        # non-zero only on findings that aren't already acknowledged.
        files = subprocess.check_output(["git", "ls-files"], text=True).splitlines()
        rc = subprocess.call(["detect-secrets-hook", "--baseline", str(BASELINE), *files])
        return 1 if rc != 0 else 0

    scan = _run_scan()
    findings = scan.get("results", {})
    total = sum(len(v) for v in findings.values())
    if total:
        print(f"detect-secrets found {total} potential secret(s) across {len(findings)} file(s):")
        print(json.dumps(findings, indent=2))
        print(
            "\nIf these are false positives, generate a baseline:\n"
            "  detect-secrets scan --all-files > .secrets.baseline\n"
            "  detect-secrets audit .secrets.baseline\n"
        )
        return 1

    print("detect-secrets: clean (no baseline, no findings)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
