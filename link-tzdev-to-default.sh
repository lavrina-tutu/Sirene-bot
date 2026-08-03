#!/bin/bash
# link-tzdev-to-default.sh — создаёт в tz-dev симлинки на кастомные скиллы из default
set -euo pipefail

DEFAULT_SKILLS="$HOME/.hermes/profiles/default/skills"
TZDEV_SKILLS="$HOME/.hermes/profiles/tz-dev/skills"

if [ ! -d "$DEFAULT_SKILLS" ] || [ ! -d "$TZDEV_SKILLS" ]; then
    echo "ERROR: skills directories not found"
    exit 1
fi

echo "=== Linking tz-dev custom skills → default ==="
echo ""

created=0; ok=0; fixed=0; skipped=0

while IFS= read -r symlink; do
    rel="${symlink#$DEFAULT_SKILLS/}"
    skill_dir="$rel"

    tzdev_target="$TZDEV_SKILLS/$skill_dir"
    mkdir -p "$(dirname "$tzdev_target")"

    if [ -L "$tzdev_target" ]; then
        current="$(readlink "$tzdev_target")"
        # Calculate expected relative path
        depth=$(echo "$skill_dir" | tr -cd '/' | wc -c)
        expected=""
        for ((i=0; i<=depth+1; i++)); do expected="../$expected"; done
        expected="${expected}default/skills/$skill_dir"
        if [ "$current" = "$expected" ]; then
            ok=$((ok + 1))
        else
            echo "  [FIX] $skill_dir"
            rm "$tzdev_target"
            ln -s "$expected" "$tzdev_target"
            fixed=$((fixed + 1))
        fi
    elif [ -d "$tzdev_target" ]; then
        skipped=$((skipped + 1))
    else
        echo "  [NEW] $skill_dir"
        depth=$(echo "$skill_dir" | tr -cd '/' | wc -c)
        back=""
        for ((i=0; i<=depth+1; i++)); do back="../$back"; done
        ln -s "${back}default/skills/$skill_dir" "$tzdev_target"
        created=$((created + 1))
    fi
done < <(find "$DEFAULT_SKILLS" -mindepth 2 -maxdepth 3 -type l 2>/dev/null)

echo ""
echo "=== Result ==="
echo "  Created:  $created"
echo "  Fixed:    $fixed"
echo "  OK:       $ok"
echo "  Skipped:  $skipped"
