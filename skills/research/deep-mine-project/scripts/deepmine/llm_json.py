"""Hermes LLM helpers: text and JSON via response_format."""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

COMPRESSOR_LLM_SLUG = "deepseek/deepseek-v4-flash-0731"
CONTEXT_MODEL = "x-ai/grok-4.6"
CONTEXT_FALLBACK_MODEL = "deepseek/deepseek-v4-pro"

_PREAMBLE_RE = re.compile(
  r"^(?:Пишу|Digest записан|Вот JSON|Here is|```json\s*)",
  re.IGNORECASE | re.MULTILINE,
)
_JSON_FENCE_RE = re.compile(r"^```(?:json)?\s*\n(.*?)\n```\s*$", re.DOTALL)


class LlmJsonError(RuntimeError):
  """LLM returned invalid or empty JSON."""


def _ensure_hermes_on_path() -> None:
  hermes = Path.home() / "hermes-agent"
  if str(hermes) not in sys.path:
    sys.path.insert(0, str(hermes))


def strip_preamble(text: str) -> str:
  """Remove common LLM preamble before JSON parsing."""
  stripped = text.strip()
  fence = _JSON_FENCE_RE.match(stripped)
  if fence:
    return fence.group(1).strip()
  lines = stripped.splitlines()
  while lines and _PREAMBLE_RE.match(lines[0]):
    lines.pop(0)
  return "\n".join(lines).strip()


def call_text(
  prompt: str,
  *,
  task: str = "compression",
  model: str = COMPRESSOR_LLM_SLUG,
  timeout: float = 300.0,
) -> str:
  _ensure_hermes_on_path()
  from agent.auxiliary_client import call_llm

  response = call_llm(
    task=task,
    model=model,
    messages=[{"role": "user", "content": prompt}],
    timeout=timeout,
    max_tokens=None,
    tools=None,
  )
  content = (response.choices[0].message.content or "").strip()
  if not content:
    raise RuntimeError("LLM returned empty content")
  return content


def call_json(
  prompt: str,
  schema: dict[str, Any],
  *,
  task: str = "compression",
  model: str = COMPRESSOR_LLM_SLUG,
  timeout: float = 300.0,
  extra_body: dict[str, Any] | None = None,
) -> dict[str, Any]:
  """Call Hermes LLM with API-level JSON schema via extra_body.response_format."""
  _ensure_hermes_on_path()
  from agent.auxiliary_client import call_llm

  body = dict(extra_body or {})
  body["response_format"] = {
    "type": "json_schema",
    "json_schema": {
      "name": schema.get("title", "response"),
      "strict": True,
      "schema": schema,
    },
  }
  response = call_llm(
    task=task,
    model=model,
    messages=[{"role": "user", "content": prompt}],
    timeout=timeout,
    max_tokens=None,
    tools=None,
    extra_body=body,
  )
  raw = (response.choices[0].message.content or "").strip()
  if not raw:
    raise LlmJsonError("LLM returned empty JSON content")
  cleaned = strip_preamble(raw)
  try:
    data = json.loads(cleaned)
  except json.JSONDecodeError as exc:
    raise LlmJsonError(f"invalid JSON: {exc}") from exc
  if not isinstance(data, dict):
    raise LlmJsonError("JSON root must be an object")
  return data
