#!/usr/bin/env bash
# Roll the hermes-agent clone back to the 'prev' commit stored in pinned-version.txt.
set -euo pipefail

HA="$HOME/Documents/Cursor_projects/hermes-agent"
WS="$HOME/Documents/Cursor_projects/hermes-workspace"

PREV=$(grep '^prev:' "$WS/upstream/pinned-version.txt" | awk '{print $2}')
[ -z "$PREV" ] && { echo "[rollback] no prev: in pinned-version.txt"; exit 1; }

cd "$HA"
echo "[rollback] checking out $PREV"
git checkout "$PREV"

VENV=""
if [ -d "$HA/.venv" ]; then VENV="$HA/.venv"; elif [ -d "$HA/venv" ]; then VENV="$HA/venv"; fi
if [ -n "$VENV" ]; then
  if [ -f "$VENV/Scripts/activate" ]; then source "$VENV/Scripts/activate"; else source "$VENV/bin/activate"; fi
  pip install -e . --force-reinstall
fi

hermes --version || true
echo "[rollback] back on $PREV"
