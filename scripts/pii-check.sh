#!/usr/bin/env bash
# scripts/pii-check.sh — scan staged files for local PII blocklist hits
#
# Usage:
#   manual:      ./scripts/pii-check.sh        # check staged files
#                ./scripts/pii-check.sh --all  # check the full repo
#   pre-commit: called automatically by .githooks/pre-commit
#
# Blocklist: ~/.proxybox-pii-blocklist.txt, kept in the local home
# directory and never committed.
# Format: one plain string per line; comments start with #; blanks ignored.
# Matching: plain string + fixed-string grep (-F), not regex.
#
# Exit codes: 0 = clean, 1 = hit found and commit blocked.
#
# Compatibility: works on bash 3.2, no mapfile/readarray dependency.

set -euo pipefail

BLOCKLIST="${PROXYBOX_PII_BLOCKLIST:-$HOME/.proxybox-pii-blocklist.txt}"
MODE="${1:-staged}"

if [[ ! -f "$BLOCKLIST" ]]; then
    echo "❌ PII blocklist not found at: $BLOCKLIST"
    echo "   See CONSTRAINTS.md § 2 for what to put in it."
    exit 1
fi

# Extract active entries (non-comment / non-empty), bash 3 compatible.
patterns=()
while IFS= read -r line; do
    # strip trailing whitespace
    line="${line%"${line##*[![:space:]]}"}"
    # skip empty + comment
    [[ -z "$line" || "$line" =~ ^[[:space:]]*# ]] && continue
    patterns+=("$line")
done < "$BLOCKLIST"

if [[ ${#patterns[@]} -eq 0 ]]; then
    echo "⚠️  blocklist is empty — refusing to run (CONSTRAINTS.md § 2 requires non-empty list)"
    exit 1
fi

# Select files to scan.
files=()
if [[ "$MODE" == "--all" ]]; then
    while IFS= read -r f; do
        files+=("$f")
    done < <(git ls-files)
else
    while IFS= read -r f; do
        files+=("$f")
    done < <(git diff --cached --name-only --diff-filter=ACM)
fi

if [[ ${#files[@]} -eq 0 ]]; then
    echo "(no files to check)"
    exit 0
fi

# Self-referential files: some files MUST list blocklist patterns to do
# their job. E.g. scripts/release-audit-history-ignore enumerates which
# patterns are allowed in git commit history. Filter those filenames out
# of any pii-check hit list — they're metadata about the blocklist, not
# a leak surface. Without this, every release-audit run hits its own
# exception list (chicken-and-egg).
self_referential_files='scripts/release-audit-history-ignore'

hits=0
for pat in "${patterns[@]}"; do
    # -F = fixed strings (no regex), -I = ignore binary, -l = filename only
    matches=$(grep -FIl -- "$pat" "${files[@]}" 2>/dev/null || true)
    # Drop any matches that are self-referential files.
    if [[ -n "$matches" ]]; then
        matches=$(echo "$matches" | grep -vE "^($self_referential_files)$" || true)
    fi
    if [[ -n "$matches" ]]; then
        echo "❌ PII hit:  '$pat'"
        echo "   in files:"
        echo "$matches" | sed 's/^/     /'
        hits=$((hits + 1))
    fi
done

if [[ $hits -gt 0 ]]; then
    echo
    echo "🛑 $hits PII pattern(s) hit. commit blocked."
    echo "   Fix:  edit the files to remove PII, then re-stage + retry."
    echo "   Override (strongly discouraged):  git commit --no-verify"
    exit 1
fi

echo "✅ pii-check: no hits across ${#files[@]} file(s) for ${#patterns[@]} pattern(s)"
exit 0
