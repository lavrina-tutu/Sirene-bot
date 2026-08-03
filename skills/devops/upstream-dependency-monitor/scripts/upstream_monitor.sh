#!/usr/bin/env bash
# upstream_monitor.sh — мониторинг upstream hermes-agent
# no_agent watchdog: stdout пустой = тихо, непустой = доставляется в TG
# State: ~/.hermes/upstream-monitor.json
set -euo pipefail

STATE="$HOME/.hermes/upstream-monitor.json"
REPO="$HOME/hermes-agent"

BEFORE=$(git -C "$REPO" rev-parse HEAD)

# Инициализация state если нет
if [ ! -f "$STATE" ]; then
    python3 -c "
import json
from datetime import datetime
json.dump({'last_sha': '$BEFORE', 'checked_at': datetime.now().isoformat()}, open('$STATE', 'w'))
"
    # Первый запуск — просто инициализируем, не шумим
    exit 0
fi

LAST_SHA=$(python3 -c "import json; print(json.load(open('$STATE'))['last_sha'])")

# Fetch upstream (без merge)
if ! git -C "$REPO" fetch origin --quiet 2>/dev/null; then
    # SSH-проблема или нет сети — warn-only, не false alarm
    echo "⚠️ upstream fetch failed — проверь SSH-ключ или сеть"
    exit 0
fi

UPSTREAM_SHA=$(git -C "$REPO" rev-parse origin/main 2>/dev/null || \
               git -C "$REPO" rev-parse origin/master 2>/dev/null)

if [ "$UPSTREAM_SHA" = "$LAST_SHA" ]; then
    exit 0  # тихо
fi

COUNT=$(git -C "$REPO" rev-list --count "$LAST_SHA..$UPSTREAM_SHA" 2>/dev/null || echo "?")
echo "🔔 Upstream hermes-agent: $COUNT новых коммит(ов)"
echo ""
git -C "$REPO" log --oneline "$LAST_SHA..$UPSTREAM_SHA" 2>/dev/null | head -10
echo ""

BREAKING=$(git -C "$REPO" log --oneline "$LAST_SHA..$UPSTREAM_SHA" 2>/dev/null | \
    grep -iE "break|breaking|config|schema|migration|rename|remove|deprecat|incompatible" | head -5 || true)

if [ -n "$BREAKING" ]; then
    echo "⚠️ Возможные breaking changes:"
    echo "$BREAKING"
    echo ""
    echo "🔍 Рекомендую: запустить weekly QA вручную перед git pull"
    echo ""
fi

# Обновить state (не делаем git pull)
python3 -c "
import json
from datetime import datetime
json.dump({'last_sha': '$UPSTREAM_SHA', 'checked_at': datetime.now().isoformat()}, open('$STATE', 'w'))
"

echo "Для обновления: git -C ~/hermes-agent pull --ff-only"
echo "Обновлён last_sha → ${UPSTREAM_SHA:0:8}"
