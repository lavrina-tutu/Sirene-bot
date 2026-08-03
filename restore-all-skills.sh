#!/bin/bash
# restore-all-skills.sh — восстановление симлинков скиллов после hermes update
# Запускать: после каждого `hermes update` или `hermes -p <profile> update`
# Идемпотентный — безопасно запускать многократно

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "=== Skill symlink restoration $(date) ==="
echo ""

# Step 1: Sync custom skills from hermes-workspace → default
echo "--- [1/2] Syncing custom skills to default ---"
"$SCRIPT_DIR/sync-to-hermes.sh" default

echo ""

# Step 2: Link tz-dev custom skills → default
echo "--- [2/2] Linking tz-dev → default ---"
"$SCRIPT_DIR/link-tzdev-to-default.sh"

echo ""
echo "=== Restoration complete ==="
