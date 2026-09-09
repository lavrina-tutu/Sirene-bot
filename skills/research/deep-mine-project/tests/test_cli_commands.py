"""T0: CLI commands exist."""
import subprocess
import sys
from pathlib import Path


def test_cli_commands_exist():
  script = Path(__file__).resolve().parents[1] / "scripts" / "deep_mine.py"
  proc = subprocess.run(
    [sys.executable, str(script), "--help"],
    capture_output=True,
    text=True,
    cwd=script.parent,
  )
  assert proc.returncode == 0
  for cmd in (
    "init", "collect", "refresh", "digest", "pack", "mine", "analyze", "document",
    "graph", "facts", "charter", "architecture", "context",
  ):
    assert cmd in proc.stdout
  assert "cron" not in proc.stdout
