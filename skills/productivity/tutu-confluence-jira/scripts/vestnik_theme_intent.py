#!/usr/bin/env python3
"""ParseIntent for VestnikTheme."""
from __future__ import annotations

import re
import sys
from dataclasses import dataclass
from pathlib import Path

from vestnik_theme_errors import VestnikError

__all__ = ["Intent", "MONTH_NAMES", "parse_intent", "extract_tab_month", "neighbor_month"]

URL_UTILS = Path.home() / "USERTOOLS" / "ConfluenceSync" / "confluencesync" / "url_utils.py"

MONTH_NAMES: dict[str, str] = {
  "январь": "январь", "января": "январь", "январе": "январь",
  "февраль": "февраль", "февраля": "февраль", "феврале": "февраль",
  "март": "март", "марта": "март", "марте": "март",
  "апрель": "апрель", "апреля": "апрель", "апреле": "апрель",
  "май": "май", "мая": "май", "мае": "май",
  "июнь": "июнь", "июня": "июнь", "июне": "июнь",
  "июль": "июль", "июля": "июль", "июле": "июль",
  "август": "август", "августа": "август", "августе": "август",
  "сентябрь": "сентябрь", "сентября": "сентябрь", "сентябре": "сентябрь",
  "октябрь": "октябрь", "октября": "октябрь", "октябре": "октябрь",
  "ноябрь": "ноябрь", "ноября": "ноябрь", "ноябре": "ноябрь",
  "декабрь": "декабрь", "декабря": "декабрь", "декабре": "декабрь",
}

_MONTH_RE = re.compile(
  r"\b(" + "|".join(sorted(MONTH_NAMES.keys(), key=len, reverse=True)) + r")\b",
  re.IGNORECASE,
)
_TOKEN_SPLIT = re.compile(r"[\s,;]+")


def _load_parse_confluence_url():
  parent = str(URL_UTILS.parent)
  if parent not in sys.path:
    sys.path.insert(0, parent)
  import url_utils as _url_utils  # noqa: WPS433 — file import, not confluencesync package

  return _url_utils.parse_confluence_url


_parse_confluence_url = None


def _get_parser():
  global _parse_confluence_url
  if _parse_confluence_url is None:
    _parse_confluence_url = _load_parse_confluence_url()
  return _parse_confluence_url


@dataclass
class Intent:
  page_ids: list[str]
  raw_refs: list[str]
  month: str | None
  apply: bool
  theme: str | None = None


def _extract_month(text: str | None) -> str | None:
  if not text:
    return None
  if re.search(r"[а-яё]+-[а-яё]+", text, re.IGNORECASE):
    return None
  m = _MONTH_RE.search(text)
  if not m:
    return None
  return MONTH_NAMES.get(m.group(1).lower())


def _tokenize(*, page_ids: list[str], command_text: str | None) -> list[str]:
  tokens: list[str] = []
  # comma/space-split every CLI page-id (support `--page-id "1,2,3"`)
  for pid in page_ids:
    for part in _TOKEN_SPLIT.split(str(pid).strip()):
      part = part.strip()
      if part:
        tokens.append(part)
  if command_text:
    for part in _TOKEN_SPLIT.split(command_text.strip()):
      part = part.strip()
      if part:
        tokens.append(part)
  return tokens


# Cyrillic single word (theme candidate), NOT a number/URL/pageId.
_CYRILLIC_WORD_RE = re.compile(r"^[А-Яа-яЁё]+$")
# Command/stop words to drop from the free-text theme.
_STOP_WORDS = {
  "добавь", "добавьте", "добавить", "тему", "тема", "в", "на", "и",
  "вестник", "вестника", "вестнике", "страничке", "страницу", "размести",
  "разместить", "для", "с", "пожалуйста",
}


def extract_tab_month(tab_name: str | None) -> str | None:
  """Last month of a tab period like «Август-Сентябрь 2026» -> «сентябрь»."""
  if not tab_name:
    return None
  found: list[str] = []
  for tok in _TOKEN_SPLIT.split(tab_name) + re.split(r"-|–|—|\s", tab_name):
    low = tok.strip().lower()
    if low in MONTH_NAMES:
      found.append(MONTH_NAMES[low])
  if not found:
    return None
  return found[-1]  # последний месяц интервала


def neighbor_month(table_html: str) -> str | None:
  """Most common month in the first column of the neighbour rows."""
  if not table_html:
    return None
  counts: dict[str, int] = {}
  for m in _MONTH_RE.findall(table_html):
    name = MONTH_NAMES.get(m.lower())
    if name:
      counts[name] = counts.get(name, 0) + 1
  if not counts:
    return None
  # most frequent; next-очередь — последний по позиции (стабильнее)
  return max(counts, key=counts.get)


def _extract_theme(command_text: str | None, used: set[str]) -> str | None:
  if not command_text:
    return None
  parts: list[str] = []
  for tok in _TOKEN_SPLIT.split(command_text.strip()):
    tok = tok.strip()
    if not tok or tok in used:
      continue
    low = tok.lower()
    if low in _STOP_WORDS:
      continue
    if low in MONTH_NAMES:
      continue
    if _CYRILLIC_WORD_RE.match(tok):
      parts.append(tok)
  theme = " ".join(parts).strip()
  return theme or None


def parse_intent(
  *,
  page_ids: list[str],
  command_text: str | None,
  apply: bool,
) -> Intent:
  """Parse CLI + command text into resolved page ids and optional month."""
  parse_url = _get_parser()
  resolved: list[str] = []
  raw_refs: list[str] = []
  seen: set[str] = set()

  for token in _tokenize(page_ids=page_ids, command_text=command_text):
    # Cyrillic single word is a theme candidate, never a pageId.
    if _CYRILLIC_WORD_RE.match(token):
      continue
    try:
      ref = parse_url(token)
    except ValueError:
      continue
    if ref.page_id:
      if ref.page_id not in seen:
        seen.add(ref.page_id)
        resolved.append(ref.page_id)
    elif ref.space_key and ref.title:
      key = f"{ref.space_key}:{ref.title}"
      if key not in seen:
        seen.add(key)
        raw_refs.append(ref.raw or token)
    elif ref.raw:
      raw_refs.append(ref.raw)

  if not resolved and not raw_refs:
    raise VestnikError(stage="parse", message="no page ids or refs in input")

  month = _extract_month(command_text)
  theme = _extract_theme(command_text, used=set(resolved) | set(raw_refs))
  return Intent(page_ids=resolved, raw_refs=raw_refs, month=month, apply=apply, theme=theme)
