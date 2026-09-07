#!/usr/bin/env python3
"""Confluence GET/PUT wrappers for VestnikTheme."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from urllib.parse import quote

from section_patch import (
  DEFAULT_BASE,
  _api_request,
  build_put_payload,
  load_confluence_token,
  put_page,
)
from vestnik_theme_author import Material, material_from_page
from vestnik_theme_errors import ConflictError, VestnikError

__all__ = [
  "VESTNIK_PAGE_ID",
  "VESTNIK_TITLE",
  "MATERIAL_EXPAND",
  "Material",
  "load_token",
  "get_page",
  "resolve_ref",
  "fetch_material",
  "put_storage",
]

VESTNIK_PAGE_ID = "324382467"
VESTNIK_TITLE = "Вестник Аналитики и Данных"
MATERIAL_EXPAND = "body.storage,version,space,history"


def load_token() -> str:
  return load_confluence_token()


def get_page(
  page_id: str,
  *,
  expand: str = MATERIAL_EXPAND,
  token: str | None = None,
  base_url: str = DEFAULT_BASE,
) -> dict[str, Any]:
  tok = token or load_token()
  url = f"{base_url}/rest/api/content/{page_id}?expand={quote(expand, safe=',')}"
  return _api_request("GET", url, tok)


def resolve_ref(url_or_id: str, *, token: str | None = None, base_url: str = DEFAULT_BASE) -> str:
  """Resolve display URL to pageId via API; numeric id passes through."""
  s = str(url_or_id).strip()
  if s.isdigit():
    return s
  from vestnik_theme_intent import _get_parser

  ref = _get_parser()(s)
  if ref.page_id:
    return ref.page_id
  if not ref.space_key or not ref.title:
    raise VestnikError(stage="parse", message=f"cannot resolve ref: {s!r}")
  tok = token or load_token()
  title_q = quote(ref.title, safe="")
  url = (
    f"{base_url}/rest/api/content?spaceKey={quote(ref.space_key, safe='')}"
    f"&title={title_q}&limit=1"
  )
  data = _api_request("GET", url, tok)
  results = data.get("results") or []
  if not results:
    raise VestnikError(stage="parse", message=f"page not found: {ref.space_key}/{ref.title}")
  return str(results[0]["id"])


def fetch_material(page_id: str, *, token: str | None = None) -> Material:
  page = get_page(page_id, token=token)
  return material_from_page(page, page_id)


def put_storage(
  page_id: str,
  *,
  title: str,
  current_version: int,
  storage: str,
  token: str | None = None,
) -> dict[str, Any]:
  payload = build_put_payload(title, current_version + 1, storage)
  if "space" in payload:
    raise VestnikError(stage="put", message="payload must not contain space")
  try:
    return put_page(page_id, payload, token=token)
  except RuntimeError as exc:
    msg = str(exc)
    if msg.startswith("HTTP 409"):
      raise ConflictError(msg) from exc
    raise
