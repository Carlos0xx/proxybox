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

set -uo pipefail

cd "$(dirname "$0")/.."

CANDIDATE_TAG="${1:-}"
red()   { printf "\033[31m%s\033[0m\n" "$*"; }
green() { printf "\033[32m%s\033[0m\n" "$*"; }
warn()  { printf "\033[33m%s\033[0m\n" "$*"; }

FINDINGS=0
fail() { red "  ✗ $*"; FINDINGS=$((FINDINGS+1)); }
pass() { green "  ✓ $*"; }

# ───────────────── 1. clean tree ─────────────────
echo "[1/7] clean working tree"
if [ -n "$(git status --porcelain)" ]; then
    fail "uncommitted changes present; commit or stash before release"
    git status --short | sed 's/^/      /'
else
    pass "tree is clean"
fi

# ───────────────── 2. pii-check on all tracked files ─────────────────
echo ""
echo "[2/7] pii-check.sh --all (tracked files vs blocklist)"
if ./scripts/pii-check.sh --all 2>&1 | tail -3; then
    pass "no PII hits across tracked files"
else
    fail "pii-check.sh reported hits"
fi

# ───────────────── 3. gitleaks (full history) ─────────────────
echo ""
echo "[3/7] gitleaks detect (full git history)"
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
echo "[4/7] git authors + committers vs PII blocklist"
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
echo ""
echo "[5/7] commit message bodies vs PII blocklist"
if [ -f "$BLOCKLIST" ]; then
    MSGS=$(git log --all --format='%B')
    HIT=0
    while IFS= read -r pattern; do
        [ -z "$pattern" ] && continue
        case "$pattern" in '#'*) continue ;; esac
        if echo "$MSGS" | grep -qF "$pattern"; then
            fail "blocklist pattern '$pattern' appears in commit messages"
            HIT=$((HIT+1))
        fi
    done < "$BLOCKLIST"
    [ "$HIT" = "0" ] && pass "no blocklist hits in commit messages"
fi

# ───────────────── 6. version sanity ─────────────────
echo ""
echo "[6/7] version sanity (pyproject.toml + app/main.py)"
PYP_VER=$(grep -oE '^version = "[^"]+"' pyproject.toml | cut -d'"' -f2)
APP_VER=$(grep -oE 'version="[^"]+"' app/main.py | cut -d'"' -f2 | head -1)
echo "      pyproject.toml: $PYP_VER"
echo "      app/main.py:    $APP_VER"
if [ "$PYP_VER" = "$APP_VER" ]; then
    pass "versions match"
else
    fail "pyproject.toml and app/main.py disagree on version"
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
echo "[7/7] CHANGELOG.md entry"
if [ ! -f CHANGELOG.md ]; then
    fail "CHANGELOG.md not found"
elif [ -n "$CANDIDATE_TAG" ] && ! grep -qF "$CANDIDATE_TAG" CHANGELOG.md; then
    fail "CHANGELOG.md has no entry for $CANDIDATE_TAG"
else
    pass "CHANGELOG.md present (manual review still recommended)"
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
