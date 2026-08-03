#!/bin/bash
# sync-to-hermes.sh — создаёт симлинки кастомных скиллов из hermes-workspace в профиль Hermes
# Использование: sync-to-hermes.sh [profile]
#   profile: default (по умолчанию) | tz-dev | etc.

set -euo pipefail

WORKSPACE_SKILLS="$HOME/hermes-workspace/skills"
PROFILE="${1:-default}"
TARGET_SKILLS="$HOME/.hermes/profiles/$PROFILE/skills"

if [ ! -d "$TARGET_SKILLS" ]; then
    echo "ERROR: target skills directory not found: $TARGET_SKILLS"
    exit 1
fi

echo "=== Syncing custom skills from hermes-workspace → $PROFILE ==="
echo ""

created=0
skipped=0
fixed=0
ok=0

# Collect all skill dirs first to avoid subshell counter issue
while IFS= read -r skill_md; do
    rel_path="${skill_md#$WORKSPACE_SKILLS/}"
    skill_dir="$(dirname "$rel_path")"
    category="$(dirname "$skill_dir")"
    skill_name="$(basename "$skill_dir")"

    # Skip root-level skills (no category)
    [ "$category" = "." ] && continue

    target_dir="$TARGET_SKILLS/$skill_dir"
    workspace_dir="$WORKSPACE_SKILLS/$skill_dir"

    # Ensure category directory exists
    mkdir -p "$TARGET_SKILLS/$category"

    if [ -L "$target_dir" ]; then
        current_target="$(readlink "$target_dir")"
        if [ "$current_target" = "$workspace_dir" ]; then
            ok=$((ok + 1))
        else
            echo "  [FIX] $skill_dir: $current_target → $workspace_dir"
            rm "$target_dir"
            ln -s "$workspace_dir" "$target_dir"
            fixed=$((fixed + 1))
        fi
    elif [ -d "$target_dir" ]; then
        # Real directory = bundled skill, skip silently
        skipped=$((skipped + 1))
    else
        echo "  [NEW] $skill_dir"
        ln -s "$workspace_dir" "$target_dir"
        created=$((created + 1))
    fi
done < <(find "$WORKSPACE_SKILLS" -name 'SKILL.md' -not -path '*/.git/*')

echo ""
echo "=== Result ==="
echo "  Created (new links):    $created"
echo "  Fixed (wrong targets):  $fixed"
echo "  Already OK:             $ok"
echo "  Skipped (bundled):      $skipped"
echo "  Target: $TARGET_SKILLS"
