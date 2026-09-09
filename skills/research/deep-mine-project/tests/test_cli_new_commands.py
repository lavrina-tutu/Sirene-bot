"""CLI new commands: graph, facts, charter, architecture, context."""
import subprocess
import sys
from pathlib import Path


def test_cli_new_commands_exist():
  script = Path(__file__).resolve().parents[1] / "scripts" / "deep_mine.py"
  proc = subprocess.run(
    [sys.executable, str(script), "--help"],
    capture_output=True,
    text=True,
    cwd=script.parent,
  )
  assert proc.returncode == 0
  for cmd in ("graph", "facts", "charter", "architecture", "context"):
    assert cmd in proc.stdout
