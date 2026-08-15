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
echo "=== Restoration complete ==="
