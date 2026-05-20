#!/usr/bin/env bash
# scripts/pii-check.sh — 扫 staged 文件,看是否命中 PII 黑名单
#
# 用法:
#   手动:  ./scripts/pii-check.sh           # 检查 staged 文件
#          ./scripts/pii-check.sh --all     # 检查整个 repo
#   pre-commit: 由 .githooks/pre-commit 自动调用
#
# 黑名单文件:  ~/.proxybox-pii-blocklist.txt  (本地家目录,绝不进 repo)
# 文件格式:    一行一个字串,#开头是注释,空行忽略
# 匹配方式:    plain string + fixed-string grep (-F),非 regex
#
# 退出码: 0 = 无命中, 1 = 命中(block commit)
#
# 兼容性: 用 bash 3.2 (Mac 默认) 也能跑,不依赖 mapfile / readarray

set -euo pipefail

BLOCKLIST="${PROXYBOX_PII_BLOCKLIST:-$HOME/.proxybox-pii-blocklist.txt}"
MODE="${1:-staged}"

if [[ ! -f "$BLOCKLIST" ]]; then
    echo "❌ PII blocklist not found at: $BLOCKLIST"
    echo "   See CONSTRAINTS.md § 2 for what to put in it."
    exit 1
fi

# 取出有效条目 (非注释 / 非空行) — bash 3 兼容,用 while + array append
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

# 选要扫的文件
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
    echo "   Override (强烈不推荐):  git commit --no-verify"
    exit 1
fi

echo "✅ pii-check: no hits across ${#files[@]} file(s) for ${#patterns[@]} pattern(s)"
exit 0
