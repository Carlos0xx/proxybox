#!/usr/bin/env bash
# scripts/release-audit.sh — pre-release security gate (CONSTRAINTS.md § L4)
#
# Run before tagging a release. Exits non-zero on any finding that should
# block the release. Designed for human review of borderline cases — print
# everything, don't silently auto-fix.
#
# Checks:
#   1. clean working tree
#   2. pii-check.sh --all   (all tracked files vs ~/.proxybox-pii-blocklist.txt)
#   3. gitleaks detect      (full history, all branches)
#   4. git author/committer scan for blocklisted handles / hostnames
#   5. commit-message body grep against blocklist
#   6. version sanity        (pyproject.toml, app/main.py)
#   7. CHANGELOG entry for the candidate tag
#   8. shellcheck for deployment scripts (when shellcheck is installed)

set -uo pipefail

cd "$(dirname "$0")/.." || exit 1

CANDIDATE_TAG="${1:-}"
red()   { printf "\033[31m%s\033[0m\n" "$*"; }
green() { printf "\033[32m%s\033[0m\n" "$*"; }
warn()  { printf "\033[33m%s\033[0m\n" "$*"; }

FINDINGS=0
fail() { red "  ✗ $*"; FINDINGS=$((FINDINGS+1)); }
pass() { green "  ✓ $*"; }

# ───────────────── 1. clean tree ─────────────────
echo "[1/8] clean working tree"
if [ -n "$(git status --porcelain)" ]; then
    fail "uncommitted changes present; commit or stash before release"
    git status --short | sed 's/^/      /'
else
    pass "tree is clean"
fi

# ───────────────── 2. pii-check on all tracked files ─────────────────
echo ""
echo "[2/8] pii-check.sh --all (tracked files vs blocklist)"
if ./scripts/pii-check.sh --all 2>&1 | tail -3; then
    pass "no PII hits across tracked files"
else
    fail "pii-check.sh reported hits"
fi

# ───────────────── 3. gitleaks (full history) ─────────────────
echo ""
echo "[3/8] gitleaks detect (full git history)"
if command -v gitleaks >/dev/null 2>&1; then
    if gitleaks detect --no-banner --redact 2>&1 | tail -10; then
        pass "gitleaks clean"
    else
        fail "gitleaks reported findings (redacted above)"
    fi
else
    warn "  gitleaks not installed (brew install gitleaks). cannot enforce — skipping."
fi

# ───────────────── 4. git author / committer scan ─────────────────
echo ""
echo "[4/8] git authors + committers vs PII blocklist"
BLOCKLIST="${PROXYBOX_PII_BLOCKLIST:-$HOME/.proxybox-pii-blocklist.txt}"
if [ ! -f "$BLOCKLIST" ]; then
    fail "blocklist not found at $BLOCKLIST"
else
    AUTHORS=$(git log --all --format='%an <%ae> | %cn <%ce>' | sort -u)
    HIT=0
    while IFS= read -r pattern; do
        # Skip blank + comment
        [ -z "$pattern" ] && continue
        case "$pattern" in '#'*) continue ;; esac
        if echo "$AUTHORS" | grep -qF "$pattern"; then
            fail "blocklist pattern '$pattern' appears in commit authors/committers"
            HIT=$((HIT+1))
        fi
    done < "$BLOCKLIST"
    if [ "$HIT" = "0" ]; then
        pass "no leaked identities in commit metadata"
        echo "      unique author/committer pairs:"
        echo "$AUTHORS" | sed 's/^/        /'
    fi
fi

# ───────────────── 5. commit message bodies vs blocklist ─────────────────
#
# Some blocklist patterns are appropriate to ENFORCE on file content (so
# they can never sneak into the running code) but not on commit history
# — e.g. a developer-private hostname that's benign in audit-trail
# commit messages, or a string that documents what was REMOVED. List
# those patterns one-per-line in scripts/release-audit-history-ignore
# with a rationale. Each line of that file is also skipped by the pii-
# check sweep (the file's whole purpose is to enumerate patterns, so it
# would self-trigger otherwise). Keeps the blocklist's content-protection
# role intact while reflecting that git messages are a different surface
# than files-on-disk.
echo ""
echo "[5/8] commit message bodies vs PII blocklist"
HISTORY_IGNORE="$(dirname "$0")/release-audit-history-ignore"
if [ -f "$BLOCKLIST" ]; then
    MSGS=$(git log --all --format='%B')
    HIT=0
    while IFS= read -r pattern; do
        [ -z "$pattern" ] && continue
        case "$pattern" in '#'*) continue ;; esac
        # Skip patterns explicitly allowed in git history.
        if [ -f "$HISTORY_IGNORE" ] && grep -qxF "$pattern" "$HISTORY_IGNORE"; then
            continue
        fi
        if echo "$MSGS" | grep -qF "$pattern"; then
            fail "blocklist pattern '$pattern' appears in commit messages"
            HIT=$((HIT+1))
        fi
    done < "$BLOCKLIST"
    [ "$HIT" = "0" ] && pass "no blocklist hits in commit messages"
fi

# ───────────────── 6. version sanity ─────────────────
#
# Source of truth = pyproject.toml. app/main.py used to hardcode a
# duplicate; v0.1.13 moved it to importlib.metadata so the only correct
# state is the literal string disappearing from app/main.py and the
# metadata-resolution call appearing instead. We check both: that
# pyproject is set, AND that app/main.py uses VERSION (sourced via
# _pkg_version) for the FastAPI app version field.
echo ""
echo "[6/8] version sanity (pyproject.toml = canonical)"
PYP_VER=$(grep -oE '^version = "[^"]+"' pyproject.toml | cut -d'"' -f2)
echo "      pyproject.toml: $PYP_VER"
if grep -qE 'version=VERSION' app/main.py && grep -qE '_pkg_version\("proxybox"\)' app/main.py; then
    pass "app/main.py sources its FastAPI version from importlib.metadata"
elif grep -qE 'version="[0-9]+\.[0-9]+\.[0-9]+"' app/main.py; then
    APP_LIT=$(grep -oE 'version="[0-9]+\.[0-9]+\.[0-9]+"' app/main.py | head -1 | cut -d'"' -f2)
    if [ "$APP_LIT" = "$PYP_VER" ]; then
        pass "app/main.py hardcoded literal ($APP_LIT) matches pyproject"
    else
        fail "app/main.py hardcoded literal ($APP_LIT) != pyproject ($PYP_VER)"
    fi
else
    fail "app/main.py has neither hardcoded version literal nor importlib wiring"
fi
if [ -n "$CANDIDATE_TAG" ]; then
    EXPECTED=${CANDIDATE_TAG#v}
    if [ "$PYP_VER" = "$EXPECTED" ]; then
        pass "matches candidate tag $CANDIDATE_TAG"
    else
        fail "tag $CANDIDATE_TAG expects $EXPECTED, but version is $PYP_VER"
    fi
fi

# ───────────────── 7. CHANGELOG ─────────────────
echo ""
echo "[7/8] CHANGELOG.md entry"
if [ ! -f CHANGELOG.md ]; then
    fail "CHANGELOG.md not found"
elif [ -n "$CANDIDATE_TAG" ] && ! grep -qF "$CANDIDATE_TAG" CHANGELOG.md; then
    fail "CHANGELOG.md has no entry for $CANDIDATE_TAG"
else
    pass "CHANGELOG.md present (manual review still recommended)"
fi

# ───────────────── 8. shell scripts ─────────────────
echo ""
echo "[8/8] shellcheck deploy/scripts"
if command -v shellcheck >/dev/null 2>&1; then
    if find deploy scripts -name '*.sh' -print0 | xargs -0 shellcheck -S warning; then
        pass "shellcheck clean for deploy/scripts"
    else
        fail "shellcheck reported deployment script issues"
    fi
else
    warn "  ! shellcheck not installed; CI lint workflow still enforces it"
fi

echo ""
echo "═══════════════════════════════════════════════════"
if [ "$FINDINGS" = "0" ]; then
    green "✓ release-audit: 0 findings, OK to release"
    exit 0
else
    red "✗ release-audit: $FINDINGS finding(s), do NOT release until resolved"
    exit 1
fi
