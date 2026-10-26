#!/usr/bin/env bash
# Воротчик для Cursor-задачи при временном сбое Cursor API.
# no_agent крон-скрипт: пингует каждые ~5 мин; когда Cursor оживёт — запускает задачу,
# доставляет результат в origin, ставит флаг-стоп. Тихий, 0 токенов на тик.
# Проверено 11.09.2026 (ревизор r=claude-sonnet-5-medium, API лежал ~80 мин, авто-возобновился).
#
# Настройки под задачу (правь эти строки):
PROMPT="<abs-путь к файлу-промпту задачи>"
MODEL="<model e.g. claude-sonnet-5-medium>"
FLAG="<abs-путь>/done.flag"
OUTFILE="<abs-путь>/out.json"
LOCKFILE="<abs-путь>/ping.lock"

set -u
if [ -f "$FLAG" ]; then exit 0; fi
exec 9>"$LOCKFILE"
if ! flock -n 9; then exit 0; fi
if [ ! -f "$PROMPT" ]; then
  echo "✗ Нет $PROMPT — не могу запустить. Проверь вручную."; exit 0
fi

PING=$(cd ~/WorkVault/Hermes-Backlog/TZ && timeout 90 agent -p "ок" -f --model cursor-grok-4.6-high --output-format json 2>&1)
case "$PING" in
  *'"is_error":false'*|*'"subtype":"success"'*|*'"type":"result"'*) : ;;
  *'Failed to reach the Cursor API'*|*'socket hang up'*|*'Connection lost'*) exit 0 ;;
  *) exit 0 ;;
esac

RESULT=$(cd ~/WorkVault/Hermes-Backlog/TZ && timeout 900 agent -p "$(cat "$PROMPT")" -f --model "$MODEL" --output-format json 2>&1)
echo "$RESULT" > "$OUTFILE"

if echo "$RESULT" | grep -q '"is_error":false'; then
  python3 -c "import sys,json
try:
  d=json.load(open('$OUTFILE')); print(d.get('result') or d.get('output') or d)
except Exception:
  print(open('$OUTFILE').read())"
  touch "$FLAG"
  exit 0
fi
echo "⚠ Cursor-задача не завершилась (см. $OUTFILE). Попробую снова через 5 мин."
exit 0