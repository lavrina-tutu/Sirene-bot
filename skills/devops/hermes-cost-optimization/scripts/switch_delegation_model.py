"""
Auto-switch delegation model based on VPN/endpoint availability.
Checks a corporate/local LLM endpoint — if reachable, uses it; otherwise falls back to Haiku.

Usage: run directly or via Hermes cron job (no_agent=true, every 5m).
Configure the constants below for your environment.
"""
import socket
import subprocess
import sys
import json
from pathlib import Path

# ── Configure these ────────────────────────────────────────────────
EXO_HOST = "10.8.4.100"
EXO_PORT = 52415
TIMEOUT = 3  # seconds

EXO_MODEL = "mlx-community/Qwen3.6-35B-A3B-8bit"
EXO_BASE_URL = f"http://{EXO_HOST}:{EXO_PORT}/v1"
EXO_API_KEY = "mlx-community/Qwen1.6-35B-A3B-8bit"
EXO_PROVIDER = "custom"

FALLBACK_MODEL = "claude-haiku-4-5"
FALLBACK_PROVIDER = "anthropic"
# ───────────────────────────────────────────────────────────────────

STATE_FILE = Path.home() / "AppData/Local/hermes/delegation_model_state.json"


def is_exo_available():
    try:
        sock = socket.create_connection((EXO_HOST, EXO_PORT), timeout=TIMEOUT)
        sock.close()
        return True
    except (socket.timeout, ConnectionRefusedError, OSError):
        return False


def get_current_state():
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text())
        except Exception:
            pass
    return {"active": None}


def save_state(active):
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps({"active": active}))


def run(cmd):
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    return result.returncode == 0


def switch_to_exo():
    ok = all([
        run(f'hermes config set delegation.model "{EXO_MODEL}"'),
        run(f'hermes config set delegation.base_url "{EXO_BASE_URL}"'),
        run(f'hermes config set delegation.api_key "{EXO_API_KEY}"'),
        run(f'hermes config set delegation.provider "{EXO_PROVIDER}"'),
    ])
    if ok:
        save_state("exo")
        print(f"Switched delegation → exo cluster ({EXO_MODEL})")
    else:
        print("Failed to switch to exo cluster")
    return ok


def switch_to_haiku():
    ok = all([
        run(f'hermes config set delegation.model "{FALLBACK_MODEL}"'),
        run(f'hermes config set delegation.provider "{FALLBACK_PROVIDER}"'),
        run('hermes config set delegation.base_url ""'),
        run('hermes config set delegation.api_key ""'),
    ])
    if ok:
        save_state("haiku")
        print(f"Switched delegation → {FALLBACK_MODEL} (Anthropic)")
    else:
        print("Failed to switch to Haiku")
    return ok


def main():
    available = is_exo_available()
    current = get_current_state()["active"]

    if available:
        if current != "exo":
            switch_to_exo()
        # else: already on exo, silent (no output = no delivery from cron)
    else:
        if current != "haiku":
            switch_to_haiku()
        # else: already on haiku, silent


if __name__ == "__main__":
    main()
