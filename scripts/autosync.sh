#!/usr/bin/env bash
# Auto-sync local Hermes state (skills, config, backlog) -> hermes-workspace repo, then push.
# Usage: cron job invokes this.
set -euo pipefail

WS="$HOME/Documents/Cursor_projects/hermes-workspace"
HERMES_HOME="$HOME/AppData/Local/hermes"
VAULT="$HOME/WorkVault/Hermes-Backlog"

# Resolve token: prefer workspace-level .env, fall back to tools/movefromff/.env
TOKEN=""
if [ -f "$WS/.env" ]; then
  TOKEN=$(grep '^GITHUB_TOKEN=' "$WS/.env" | cut -d= -f2- | tr -d '\r\n' || true)
fi
if [ -z "$TOKEN" ] && [ -f "$WS/tools/movefromff/.env" ]; then
  TOKEN=$(grep '^GITHUB_TOKEN=' "$WS/tools/movefromff/.env" | cut -d= -f2- | tr -d '\r\n' || true)
fi
[ -z "$TOKEN" ] && { echo "[autosync] No GITHUB_TOKEN found"; exit 1; }

cd "$WS"

echo "[autosync] mirroring skills..."
# Use cp -r since rsync may be flaky on Windows MSYS; clean target first to mimic --delete
if [ -d "$HERMES_HOME/skills" ]; then
  rm -rf skills
  mkdir -p skills
  cp -r "$HERMES_HOME/skills/." skills/
  find skills -name '__pycache__' -type d -exec rm -rf {} + 2>/dev/null || true
fi

echo "[autosync] mirroring docs from WorkVault..."
for f in "$VAULT"/backlog.md "$VAULT"/automation-tools-vision.md "$VAULT"/github-consolidation-plan.md; do
  [ -f "$f" ] && cp "$f" docs/
done
for f in "$VAULT"/*_TZ_*.md "$VAULT"/*_Brief_*.md; do
  [ -f "$f" ] && cp "$f" docs/tz/
done
for f in "$VAULT"/self-check-*.md; do
  [ -f "$f" ] && cp "$f" docs/self-checks/
done

echo "[autosync] sanitizing config.yaml..."
if [ -f "$HERMES_HOME/config.yaml" ]; then
  bash "$WS/scripts/sanitize_config.sh" "$HERMES_HOME/config.yaml" "$WS/config/config.yaml"
fi

echo "[autosync] running doctor..."
bash "$WS/scripts/doctor.sh"

echo "[autosync] commit + push..."
git remote set-url origin "https://${TOKEN}@github.com/ialextkachenko-byte/hermes-workspace.git"
git add -A
if git diff --cached --quiet; then
  echo "[autosync] no changes"
  exit 0
fi
git commit -m "auto-sync $(date '+%Y-%m-%d %H:%M')"
git push origin main
echo "[autosync] done"
