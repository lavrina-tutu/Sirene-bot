#!/usr/bin/env python3
"""Batch-resolve Confluence ri:userkey → username/displayName (B1)."""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import Any, Protocol
from urllib.parse import quote

from section_patch import DEFAULT_BASE, _api_request, get_page, load_confluence_token

USERKEY_RE = re.compile(r'ri:userkey="([^"]+)"', re.IGNORECASE)

ANYWHERE_CONTACTS = Path.home() / "USERTOOLS" / "AnywhereContacts"
CONTACTS_ENC = Path.home() / "WorkVault" / "Contacts" / "contacts.enc"


class UserClient(Protocol):
  def get_user_by_key(self, userkey: str) -> dict[str, Any]: ...


class ConfluenceUserClient:
  """GET /rest/api/user?key= — no /user/search."""

  def __init__(self, token: str, base_url: str = DEFAULT_BASE) -> None:
    self._token = token
    self._base = base_url.rstrip("/")

  def get_user_by_key(self, userkey: str) -> dict[str, Any]:
    url = f"{self._base}/rest/api/user?key={quote(userkey, safe='')}"
    return _api_request("GET", url, self._token)


def extract_userkeys(storage: str) -> list[str]:
  """Unique userkeys in document order."""
  seen: set[str] = set()
  out: list[str] = []
  for key in USERKEY_RE.findall(storage or ""):
    if key not in seen:
      seen.add(key)
      out.append(key)
  return out


def resolve_user(
  key: str,
  cache: dict[str, dict[str, str]],
  client: UserClient,
) -> dict[str, str]:
  """Resolve one userkey; cache hit avoids HTTP."""
  if key in cache:
    return cache[key]
  data = client.get_user_by_key(key)
  username = str(data.get("username") or "")
  display = str(data.get("displayName") or data.get("displayname") or "")
  if not username and not display:
    raise RuntimeError(f"empty user response for key={key!r}")
  result = {"userkey": key, "username": username, "displayName": display}
  cache[key] = result
  return result


def resolve_all(
  keys: list[str],
  client: UserClient,
  cache: dict[str, dict[str, str]] | None = None,
) -> list[dict[str, str]]:
  c: dict[str, dict[str, str]] = cache if cache is not None else {}
  return [resolve_user(k, c, client) for k in keys]


def _load_store():
  if str(ANYWHERE_CONTACTS) not in sys.path:
    sys.path.insert(0, str(ANYWHERE_CONTACTS))
  from anywhere_contacts import create_store  # type: ignore

  key = os.environ.get("CONTACTS_ENCRYPTION_KEY", "")
  if not key:
    raise RuntimeError("CONTACTS_ENCRYPTION_KEY not set")
  return create_store(CONTACTS_ENC, key)


def write_contacts(resolved: list[dict[str, str]]) -> list[str]:
  """
  Update confluence_login / confluence_userkey on existing contacts only.
  Does not create contacts or plaintext .md files.
  """
  store = _load_store()
  data = store.read()
  contacts = data.get("contacts") or {}
  updated: list[str] = []

  for row in resolved:
    username = (row.get("username") or "").lower()
    userkey = row.get("userkey") or ""
    if not username:
      continue

    login: str | None = None
    if username in contacts:
      login = username
    else:
      for lg, c in contacts.items():
        if (c.get("confluence_login") or "").lower() == username:
          login = lg
          break
        if (c.get("confluence_userkey") or "") == userkey and userkey:
          login = lg
          break

    if login is None:
      continue

    store.update_contact(
      login,
      {
        "confluence_login": row.get("username") or "",
        "confluence_userkey": userkey,
      },
    )
    updated.append(login)

  return updated


def storage_from_page(page_id: str, *, token: str | None = None) -> str:
  page = get_page(page_id, token=token)
  return page["body"]["storage"]["value"]


def main(argv: list[str] | None = None) -> int:
  parser = argparse.ArgumentParser(description="Batch-resolve Confluence userkeys")
  src = parser.add_mutually_exclusive_group(required=True)
  src.add_argument("--storage-file", type=Path, help="Storage XML or page JSON with body.storage")
  src.add_argument("--page-id", help="Fetch storage via GET (live)")
  parser.add_argument("--write-contacts", action="store_true", help="Write to contacts.enc only")
  args = parser.parse_args(argv)

  if args.storage_file:
    raw = args.storage_file.read_text(encoding="utf-8")
    if raw.lstrip().startswith("{"):
      page = json.loads(raw)
      storage = page["body"]["storage"]["value"]
    else:
      storage = raw
  else:
    storage = storage_from_page(args.page_id)

  keys = extract_userkeys(storage)
  token = load_confluence_token()
  client = ConfluenceUserClient(token)
  cache: dict[str, dict[str, str]] = {}
  rows = resolve_all(keys, client, cache)

  if args.write_contacts:
    write_contacts(rows)

  print(json.dumps(rows, ensure_ascii=False, indent=2))
  return 0


if __name__ == "__main__":
  raise SystemExit(main())
