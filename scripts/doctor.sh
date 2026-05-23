#!/usr/bin/env bash
# Sanity-checks before commit/push. Exits non-zero on red flag.
set -euo pipefail

WS="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$WS"

fail=0

echo "[doctor] checking forbidden paths in git index..."
forbidden=$(git ls-files | grep -E '(^|/)(\.venv|venv|__pycache__|\.coverage|\.pytest_cache|\.locks|logs)(/|$)' || true)
if [ -n "$forbidden" ]; then
  echo "❌ Forbidden tracked paths:"
  echo "$forbidden"
  fail=1
fi

echo "[doctor] checking for .env files (only .env.example allowed)..."
envfiles=$(git ls-files | grep -E '(^|/)\.env$' || true)
if [ -n "$envfiles" ]; then
  echo "❌ .env files tracked:"
  echo "$envfiles"
  fail=1
fi

echo "[doctor] checking for token-looking strings in config/config.yaml..."
if [ -f config/config.yaml ]; then
  if grep -nE 'sk-ant-[A-Za-z0-9_-]{20,}|ghp_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|sk-proj-[A-Za-z0-9_-]{20,}|xoxb-[A-Za-z0-9-]{20,}|[0-9]{8,12}:[A-Za-z0-9_-]{30,}' config/config.yaml; then
    echo "❌ Possible secret in config/config.yaml"
    fail=1
  fi
fi

echo "[doctor] checking tools/*/.env (must not exist in tree)..."
for envf in tools/*/.env; do
  [ -e "$envf" ] && { echo "❌ unexpected $envf present in working tree"; fail=1; }
done

if [ "$fail" -ne 0 ]; then
  echo "[doctor] FAIL"
  exit 1
fi
echo "[doctor] OK"
