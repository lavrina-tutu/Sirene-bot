#!/usr/bin/env bash
# Public entry for TelegramGroupTopics restore (apply|check|dry-run).
set -euo pipefail

usage() {
  echo "usage: restore_telegram_topics.sh apply|check|dry-run" >&2
  exit 2
}

if [[ $# -ne 1 ]]; then
  usage
fi

case "$1" in
  apply|check|dry-run) ;;
  *) usage ;;
esac

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
HERMES_AGENT_ROOT="${HERMES_AGENT_ROOT:-$HOME/hermes-agent}"

if [[ -x "${HERMES_AGENT_ROOT}/.venv/bin/python3" ]]; then
  PYTHON="${HERMES_AGENT_ROOT}/.venv/bin/python3"
elif [[ -x "${HOME}/hermes-agent/.venv/bin/python3" ]]; then
  PYTHON="${HOME}/hermes-agent/.venv/bin/python3"
else
  PYTHON="python3"
fi

exec "$PYTHON" "${SCRIPT_DIR}/restore_telegram_topics.py" "$1"
