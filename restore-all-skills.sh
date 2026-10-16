#!/bin/bash
# restore-all-skills.sh — восстановление симлинков скиллов после hermes update
# Запускать: после каждого `hermes update` или `hermes -p <profile> update`
# Идемпотентный — безопасно запускать многократно
# ВНИМАНИЕ: профиль tz-dev удалён 13.08.2026, link-tzdev-to-default.sh больше не вызывается

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "=== Skill symlink restoration $(date) ==="
echo ""

# Sync custom skills from hermes-workspace → default (skill symlinks only)
echo "--- Syncing custom skills to default ---"
"$SCRIPT_DIR/sync-to-hermes.sh" default

# NOTE: WorkVault is the single source of truth for TZ / data graph entities.
# The ONLY legitimate sync is autosync_github.sh (WorkVault → git mirror).
# Restore does NOT copy anything into WorkVault — that would roll back daytime
# TZ:patch / Z:finalize / ERC edits with an old mirror. See canon in
# hermes-multi-profile-skills skill.

echo ""
echo "=== Skill symlink restoration complete ==="
