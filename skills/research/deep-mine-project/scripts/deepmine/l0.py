"""Parse L0 Confluence index.md pages."""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


_FM_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)


@dataclass
class L0Record:
  page_id: str
  title: str
  confluence_url: str
  space: str
  parent: str | None
  children: list[str]
  version: str
  author: str | None
  last_modified: str | None
  synced_at: str | None
  local_path: str
  content_sha256: str
  body: str


def split_frontmatter(text: str) -> tuple[dict[str, Any], str]:
  match = _FM_RE.match(text)
  if not match:
    return {}, text
  fm = yaml.safe_load(match.group(1)) or {}
  body = text[match.end():]
  return fm, body


def sha256_body(body: str) -> str:
  return hashlib.sha256(body.encode("utf-8")).hexdigest()


def _norm_parent(value: Any) -> str | None:
  if value is None or value == "null":
    return None
  return str(value)


def _norm_children(value: Any) -> list[str]:
  if not value:
    return []
  return [str(c) for c in value]


def parse_l0_page(path: Path, *, local_path: str | None = None) -> L0Record:
  text = path.read_text(encoding="utf-8")
  fm, body = split_frontmatter(text)
  page_id = str(fm.get("confluence_id") or "")
  if not page_id:
    raise ValueError(f"missing confluence_id in {path}")
  rel = local_path or ""
  return L0Record(
    page_id=page_id,
    title=str(fm.get("title") or ""),
    confluence_url=str(fm.get("confluence_url") or ""),
    space=str(fm.get("space") or ""),
    parent=_norm_parent(fm.get("parent")),
    children=_norm_children(fm.get("children")),
    version=str(fm.get("version") or ""),
    author=str(fm.get("author")) if fm.get("author") else None,
    last_modified=str(fm.get("last_modified")) if fm.get("last_modified") else None,
    synced_at=str(fm.get("synced_at")) if fm.get("synced_at") else None,
    local_path=rel,
    content_sha256=sha256_body(body),
    body=body,
  )
