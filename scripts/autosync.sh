#!/usr/bin/env bash
# Auto-sync local Hermes state (skills, config, backlog) -> hermes-workspace repo, then push.
# Usage: cron job invokes this.
# Адаптировано для Linux VM (hermes-agents.devel.tutu.ru), 2026-06-02
set -euo pipefail

WS="$HOME/hermes-workspace"
HERMES_HOME="$HOME/.hermes"
VAULT="$HOME/WorkVault/Hermes-Backlog"

cd "$WS"

echo "[autosync] mirroring skills..."
if [ -d "$HERMES_HOME/skills" ]; then
  rm -rf skills
  mkdir -p skills
  cp -r "$HERMES_HOME/skills/." skills/
  find skills -name '__pycache__' -type d -exec rm -rf {} + 2>/dev/null || true
fi

echo "[autosync] mirroring docs from WorkVault..."
mkdir -p docs docs/tz docs/self-checks
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
if [ -f "$HERMES_HOME/config.yaml" ] && [ -f "$WS/scripts/sanitize_config.sh" ]; then
  bash "$WS/scripts/sanitize_config.sh" "$HERMES_HOME/config.yaml" "$WS/config/config.yaml"
fi

echo "[autosync] running doctor..."
if [ -f "$WS/scripts/doctor.sh" ]; then
  bash "$WS/scripts/doctor.sh"
fi

echo "[autosync] commit + push..."
# Переведено на GitHub Галины (lavrina-tutu/Sirene-bot), auth через ~/.git-credentials (токен Галины). alex-byte не трогаем/не удаляем.
git remote set-url origin https://github.com/lavrina-tutu/Sirene-bot.git
git add -A
if git diff --cached --quiet; then
  echo "[autosync] no changes"
  exit 0
fi
git commit -m "auto-sync $(date '+%Y-%m-%d %H:%M')"
git push origin main
echo "[autosync] done"
