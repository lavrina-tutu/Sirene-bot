#!/bin/bash
# restore-all-skills.sh — восстановление симлинков скиллов после hermes update
# Запускать: после каждого `hermes update` или `hermes -p <profile> update`
# Идемпотентный — безопасно запускать многократно
# ВНИМАНИЕ: профиль tz-dev удалён 13.08.2026, link-tzdev-to-default.sh больше не вызывается

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "=== Skill symlink restoration $(date) ==="
echo ""

# Sync custom skills from hermes-workspace → default
echo "--- Syncing custom skills to default ---"
"$SCRIPT_DIR/sync-to-hermes.sh" default

echo ""
echo "--- Restoring TZ mirror (hermes-workspace → WorkVault) ---"
TZ_SRC="$SCRIPT_DIR/Hermes-Backlog/TZ"
TZ_DST="$HOME/WorkVault/Hermes-Backlog/TZ"
if [ -d "$TZ_SRC" ]; then
  mkdir -p "$TZ_DST"
  cp -a "$TZ_SRC/." "$TZ_DST/"
  echo "  TZ restored: $TZ_DST"
else
  echo "  SKIP: no mirror at $TZ_SRC"
fi

echo ""
echo "--- Restoring data graph entities (hermes-workspace → WorkVault/Registries) ---"
REG_SRC="$SCRIPT_DIR/Hermes-Backlog/Registries-entities"
REG_DST="$HOME/WorkVault/Registries"
if [ -d "$REG_SRC" ]; then
  mkdir -p "$REG_DST"
  for ent in entities.schema.json entities.json; do
    if [ -f "$REG_SRC/$ent" ]; then
      cp -a "$REG_SRC/$ent" "$REG_DST/"
      echo "  restored $REG_DST/$ent"
    fi
  done
else
  echo "  SKIP: no mirror at $REG_SRC"
fi

echo ""
echo "=== Restoration complete ==="
