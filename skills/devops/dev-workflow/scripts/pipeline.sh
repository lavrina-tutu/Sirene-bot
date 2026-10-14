#!/usr/bin/env bash
set -euo pipefail
ROOT="${PIPELINE_ROOT:-}"
if [[ -z "$ROOT" ]]; then
  echo "PIPELINE_ROOT unset" >&2
  exit 1
fi
export PYTHONPATH="$(dirname "$ROOT")"
exec python3 -m pipeline.cli "$@"
