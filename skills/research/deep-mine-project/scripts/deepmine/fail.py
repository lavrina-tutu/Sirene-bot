"""Fail-loud helpers and exit codes."""
from __future__ import annotations

import sys


EXIT_OK = 0
EXIT_VALIDATION = 2
EXIT_CONFLUENCE = 3
EXIT_MPP = 4
EXIT_MEETINGS = 5
EXIT_DIGEST = 6


class DeepMineError(Exception):
  """Base error with CLI exit code."""

  exit_code: int = EXIT_VALIDATION

  def __init__(self, message: str) -> None:
    super().__init__(message)
    self.message = message


class ValidationError(DeepMineError):
  exit_code = EXIT_VALIDATION


class ConfluenceDownError(DeepMineError):
  exit_code = EXIT_CONFLUENCE


class MppError(DeepMineError):
  exit_code = EXIT_MPP


class MeetingsIndexError(DeepMineError):
  exit_code = EXIT_MEETINGS


class DigestError(DeepMineError):
  exit_code = EXIT_DIGEST


def confluence_down(reason: str) -> None:
  raise ConfluenceDownError(f"Confluence unavailable: {reason}")


def mpp_failed(reason: str) -> None:
  raise MppError(f"MPP export failed: {reason}")


def meetings_failed(reason: str) -> None:
  raise MeetingsIndexError(f"Meetings index unavailable: {reason}")


def digest_failed(reason: str) -> None:
  raise DigestError(f"Digest validation failed: {reason}")


def exit_from_error(exc: DeepMineError) -> int:
  print(exc.message, file=sys.stderr)
  return exc.exit_code
