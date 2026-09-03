#!/usr/bin/env python3
"""Section-patch Confluence storage: GET → replace section inner → PUT (B0)."""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import uuid
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

DEFAULT_BASE = "https://dom.tutu.ru"
ENV_FILE = Path.home() / "USERTOOLS" / "ConfluenceSync" / ".env"

_HEADING_TAG = re.compile(
  r"(<h([1-6])[^>]*>)(.*?)(</h\2>)",
  re.IGNORECASE | re.DOTALL,
)


def load_confluence_token(env_file: Path = ENV_FILE) -> str:
  token = os.environ.get("CONFLUENCE_TOKEN", "")
  if token:
    return token
  if not env_file.is_file():
    raise RuntimeError(f"Confluence .env not found: {env_file}")
  for line in env_file.read_text(encoding="utf-8").splitlines():
    line = line.strip()
    if line.startswith("CONFLUENCE_TOKEN="):
      return line.split("=", 1)[1].strip().strip('"').strip("'")
  raise RuntimeError("CONFLUENCE_TOKEN not in .env")


def _api_request(
  method: str,
  url: str,
  token: str,
  *,
  data: bytes | None = None,
) -> dict[str, Any]:
  req = Request(
    url,
    data=data,
    method=method,
    headers={
      "Authorization": f"Bearer {token}",
      "Content-Type": "application/json",
      "Accept": "application/json",
    },
  )
  try:
    with urlopen(req, timeout=60) as resp:
      raw = resp.read().decode("utf-8")
      return json.loads(raw) if raw.strip() else {}
  except HTTPError as exc:
    body = exc.read().decode("utf-8", errors="replace")
    raise RuntimeError(f"HTTP {exc.code}: {body}") from exc
  except URLError as exc:
    raise RuntimeError(f"network error: {exc}") from exc


def get_page(
  page_id: str,
  *,
  token: str | None = None,
  base_url: str = DEFAULT_BASE,
  out_file: Path | None = None,
) -> dict[str, Any]:
  """GET page with body.storage and version; optionally save JSON to file."""
  tok = token or load_confluence_token()
  url = f"{base_url}/rest/api/content/{page_id}?expand=body.storage,version"
  data = _api_request("GET", url, tok)
  if out_file is not None:
    out_file.parent.mkdir(parents=True, exist_ok=True)
    out_file.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
  return data


def build_put_payload(
  title: str,
  version: int,
  storage_value: str,
) -> dict[str, Any]:
  """PUT payload without ``space`` (existing page update)."""
  return {
    "id": None,
    "type": "page",
    "title": title,
    "version": {"number": version},
    "body": {
      "storage": {
        "value": storage_value,
        "representation": "storage",
      },
    },
  }


def put_page(
  page_id: str,
  payload: dict[str, Any],
  *,
  token: str | None = None,
  base_url: str = DEFAULT_BASE,
) -> dict[str, Any]:
  tok = token or load_confluence_token()
  payload = dict(payload)
  payload["id"] = str(page_id)
  url = f"{base_url}/rest/api/content/{page_id}"
  body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
  return _api_request("PUT", url, tok, data=body)


def _strip_tags(html: str) -> str:
  text = re.sub(r"<[^>]+>", "", html)
  return re.sub(r"\s+", " ", text).strip()


def find_section_span(storage: str, heading: str) -> tuple[int, int, int]:
  """
  Find replaceable inner span for a section.

  Returns ``(inner_start, inner_end, heading_level)``.
  Span excludes the heading tag and the first explanatory paragraph/block
  immediately after it (until first ``<p>`` block ends).
  Inner span ends before the next heading of the same or higher level.
  """
  matches = list(_HEADING_TAG.finditer(storage))
  target_idx = None
  target_level = None
  for i, m in enumerate(matches):
    title = _strip_tags(m.group(3))
    if heading in title or title == heading:
      target_idx = i
      target_level = int(m.group(2))
      break
  if target_idx is None:
    raise ValueError(f"section heading not found: {heading!r}")

  heading_end = matches[target_idx].end()
  # Skip first explanatory block (one <p>...</p> or until next tag block)
  p_match = re.match(r"\s*(<p[^>]*>.*?</p>)", storage[heading_end:], re.IGNORECASE | re.DOTALL)
  inner_start = heading_end + (p_match.end() if p_match else 0)

  inner_end = len(storage)
  for m in matches[target_idx + 1:]:
    level = int(m.group(2))
    if level <= target_level:
      inner_end = m.start()
      break
  return inner_start, inner_end, target_level


def replace_section_inner(storage: str, heading: str, new_inner: str) -> str:
  """Replace only section inner; heading and explanation stay outside span."""
  start, end, _ = find_section_span(storage, heading)
  return storage[:start] + new_inner + storage[end:]


def patch_section(
  page_id: str,
  heading: str,
  new_inner: str,
  *,
  token: str | None = None,
  base_url: str = DEFAULT_BASE,
  get_cache: Path | None = None,
) -> dict[str, Any]:
  """GET → replace section inner → PUT. Storage never read from stdin."""
  cache = get_cache or Path(f"/tmp/confluence_page_{page_id}_{uuid.uuid4().hex[:8]}.json")
  page = get_page(page_id, token=token, base_url=base_url, out_file=cache)
  title = page["title"]
  version = int(page["version"]["number"])
  storage = page["body"]["storage"]["value"]
  patched = replace_section_inner(storage, heading, new_inner)
  payload = build_put_payload(title, version + 1, patched)
  return put_page(page_id, payload, token=token, base_url=base_url)


def main(argv: list[str] | None = None) -> int:
  parser = argparse.ArgumentParser(description="Patch one Confluence section (not full body PUT from LLM)")
  sub = parser.add_subparsers(dest="command", required=True)

  p_get = sub.add_parser("get", help="GET page to JSON file")
  p_get.add_argument("page_id")
  p_get.add_argument("--out", required=True, type=Path)

  p_patch = sub.add_parser("patch", help="GET → replace section → PUT")
  p_patch.add_argument("page_id")
  p_patch.add_argument("--heading", required=True)
  p_patch.add_argument("--inner-file", required=True, type=Path, help="New inner HTML (field markdown converted by script, not LLM storage)")

  args = parser.parse_args(argv)
  if args.command == "get":
    get_page(args.page_id, out_file=args.out)
    print(args.out)
    return 0
  if args.command == "patch":
    inner = args.inner_file.read_text(encoding="utf-8")
    result = patch_section(args.page_id, args.heading, inner)
    print(json.dumps({"id": result.get("id"), "version": result.get("version")}, ensure_ascii=False))
    return 0
  return 2


if __name__ == "__main__":
  raise SystemExit(main())
