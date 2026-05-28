#!/usr/bin/env bash
# Sanitize Hermes config.yaml: strip secret-looking values before mirroring into the repo.
# Usage: sanitize_config.py <src> <dst>
# (Bash wrapper around a tiny Python script.)
set -euo pipefail

SRC="${1:?usage: sanitize_config.sh <src> <dst>}"
DST="${2:?usage: sanitize_config.sh <src> <dst>}"

# Choose a working Python interpreter. Some venvs in this env have a broken
# uv trampoline (missing python.exe), so prefer the Windows `py` launcher.
PYBIN=""
if command -v py >/dev/null 2>&1; then
  PYBIN="py -3"
elif command -v python3 >/dev/null 2>&1; then
  PYBIN="python3"
else
  PYBIN="python"
fi

$PYBIN - "$SRC" "$DST" <<'PY'
import re, sys, pathlib

src = pathlib.Path(sys.argv[1])
dst = pathlib.Path(sys.argv[2])
text = src.read_text(encoding="utf-8")

# Token-like patterns we redact (replace value with '***REDACTED***'):
patterns = [
    re.compile(r'(sk-ant-[A-Za-z0-9_-]{20,})'),
    re.compile(r'(ghp_[A-Za-z0-9]{20,})'),
    re.compile(r'(github_pat_[A-Za-z0-9_]{20,})'),
    re.compile(r'(sk-proj-[A-Za-z0-9_-]{20,})'),
    re.compile(r'(xoxb-[A-Za-z0-9-]{20,})'),
    re.compile(r'(\b[0-9]{8,12}:[A-Za-z0-9_-]{30,}\b)'),  # telegram bot
]
for p in patterns:
    text = p.sub("***REDACTED***", text)

# Also redact obvious "<key>: <long-hex-or-base64>" near words token/secret/api_key/password
text = re.sub(
    r'(?i)((?:api[_-]?key|token|secret|password)\s*[:=]\s*["\']?)([A-Za-z0-9._\-]{24,})(["\']?)',
    r'\1***REDACTED***\3',
    text,
)

dst.parent.mkdir(parents=True, exist_ok=True)
dst.write_text(text, encoding="utf-8")
print(f"sanitized {src} -> {dst}")
PY
