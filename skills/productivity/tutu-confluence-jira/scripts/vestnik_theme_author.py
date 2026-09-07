#!/usr/bin/env python3
"""FetchMaterial + userkey confirm for VestnikTheme."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from userkey_resolve import UserClient, resolve_user
from vestnik_theme_errors import VestnikError, report_technical

__all__ = ["Material", "material_from_page", "confirm_userkey"]


@dataclass
class Material:
  page_id: str
  title: str
  space_key: str
  created_by_username: str
  created_by_userkey: str
  created_by_display: str


def material_from_page(page: dict[str, Any], page_id: str) -> Material:
  title = str(page.get("title") or "")
  space = page.get("space") or {}
  space_key = str(space.get("key") or "")
  history = page.get("history") or {}
  created_by = history.get("createdBy") or {}
  username = str(created_by.get("username") or "")
  userkey = str(created_by.get("userKey") or created_by.get("userkey") or "")
  display = str(created_by.get("displayName") or created_by.get("displayname") or "")
  if not userkey:
    raise VestnikError(stage="fetch", message=f"no createdBy.userKey for page {page_id}")
  return Material(
    page_id=page_id,
    title=title,
    space_key=space_key,
    created_by_username=username,
    created_by_userkey=userkey,
    created_by_display=display,
  )


def confirm_userkey(
  userkey: str,
  *,
  client: UserClient,
  cache: dict[str, dict[str, str]],
) -> dict[str, str]:
  try:
    result = resolve_user(userkey, cache, client)
  except Exception as exc:
    report_technical("userkey", str(exc))
    raise VestnikError(stage="userkey", message=str(exc)) from exc
  if not result.get("userkey"):
    report_technical("userkey", "empty userkey in API response")
    raise VestnikError(stage="userkey", message="empty userkey in API response")
  return result
