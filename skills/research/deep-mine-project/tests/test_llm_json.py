"""llm_json: call_text, call_json, strip_preamble."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from deepmine.llm_json import LlmJsonError, call_json, call_text, strip_preamble


def test_strip_preamble_json_fence():
  raw = '```json\n{"ok": true}\n```'
  assert strip_preamble(raw) == '{"ok": true}'


def test_strip_preamble_removes_prefix():
  raw = 'Пишу ответ\n{"a": 1}'
  assert strip_preamble(raw) == '{"a": 1}'


def test_call_text_uses_call_llm():
  response = MagicMock()
  response.choices = [MagicMock()]
  response.choices[0].message.content = "hello"
  with patch("agent.auxiliary_client.call_llm", return_value=response) as mock:
    assert call_text("prompt") == "hello"
  mock.assert_called_once()


def test_call_json_parses_response():
  response = MagicMock()
  response.choices = [MagicMock()]
  response.choices[0].message.content = '{"people": []}'
  schema = {"type": "object", "properties": {"people": {"type": "array"}}, "required": ["people"]}
  with patch("agent.auxiliary_client.call_llm", return_value=response):
    data = call_json("prompt", schema)
  assert data == {"people": []}


def test_call_json_invalid_raises():
  response = MagicMock()
  response.choices = [MagicMock()]
  response.choices[0].message.content = "not json"
  schema = {"type": "object", "properties": {}, "required": []}
  with patch("agent.auxiliary_client.call_llm", return_value=response):
    with pytest.raises(LlmJsonError):
      call_json("prompt", schema)
