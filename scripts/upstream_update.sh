#!/usr/bin/env bash
# Update upstream NousResearch/hermes-agent clone, snapshotting pin + pip freeze.
set -euo pipefail

HA="$HOME/Documents/Cursor_projects/hermes-agent"
WS="$HOME/Documents/Cursor_projects/hermes-workspace"

cd "$HA"

CURRENT=$(git rev-parse HEAD)
echo "[upstream_update] current HEAD: $CURRENT"
echo "previous: $CURRENT on $(date +%F)" >> "$WS/upstream/rollback-history.txt"

# Backup pip freeze
VENV=""
if [ -d "$HA/.venv" ]; then VENV="$HA/.venv"; elif [ -d "$HA/venv" ]; then VENV="$HA/venv"; fi
if [ -n "$VENV" ]; then
  "$VENV/Scripts/pip" freeze > "$WS/upstream/pip-freeze-before-$(date +%F).txt" 2>/dev/null \
    || "$VENV/bin/pip" freeze > "$WS/upstream/pip-freeze-before-$(date +%F).txt" 2>/dev/null \
    || true
fi

# Fetch + show diff
git fetch origin --tags
echo "[upstream_update] incoming commits:"
git --no-pager log --oneline "${CURRENT}..origin/main" | head -50 || true

git pull --ff-only origin main

NEW=$(git rev-parse HEAD)
TAG=$(git describe --tags --abbrev=0 2>/dev/null || echo "")

cat > "$WS/upstream/pinned-version.txt" <<EOF
commit:  $NEW
tag:     $TAG
date:    $(date +%F)
prev:    $CURRENT
notes:   обновлено через upstream_update.sh
EOF

# Reinstall
if [ -n "$VENV" ]; then
  if [ -f "$VENV/Scripts/activate" ]; then source "$VENV/Scripts/activate"; else source "$VENV/bin/activate"; fi
  pip install -e . --upgrade
fi

echo "[upstream_update] smoke test..."
hermes --version || true

echo "[upstream_update] OK. Pinned: $NEW (prev=$CURRENT). Rollback: bash scripts/upstream_rollback.sh"
