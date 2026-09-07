#!/usr/bin/env python3
"""VestnikTheme error types and ErrorBus reporting."""
from __future__ import annotations

import subprocess
from pathlib import Path

__all__ = [
  "VestnikError",
  "HitlStop",
  "ConflictError",
  "report_technical",
]

ERROR_BUS = Path.home() / ".hermes" / "scripts" / "report_error.sh"


class VestnikError(Exception):
  """Technical failure; may trigger ErrorBus."""

  def __init__(self, stage: str, message: str, *, exit_code: int = 1) -> None:
    self.stage = stage
    self.message = message
    self.exit_code = exit_code
    super().__init__(message)


class ConflictError(VestnikError):
  """HTTP 409 on PUT."""

  def __init__(self, message: str) -> None:
    super().__init__(stage="put", message=message, exit_code=1)


class HitlStop(Exception):
  """Human-in-the-loop stop; no ErrorBus."""

  def __init__(self, kind: str, message: str) -> None:
    self.kind = kind
    self.message = message
    self.exit_code = 2
    super().__init__(message)


def report_technical(stage: str, message: str, *, detail: str | None = None) -> None:
  """Call ErrorBus (fail-soft); caller must still raise/return non-zero."""
  cmd = [
    str(ERROR_BUS),
    "--tool", "VestnikTheme",
    "--source-kind", "skill",
    "--stage", stage,
    "--message", message,
  ]
  if detail:
    cmd.extend(["--detail", detail])
  try:
    subprocess.run(cmd, check=False, capture_output=True, text=True)
  except OSError:
    pass
