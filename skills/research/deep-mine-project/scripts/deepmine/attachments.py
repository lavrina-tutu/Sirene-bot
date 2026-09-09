"""Step B: whitelist attachment download via ConfluenceSync client."""
from __future__ import annotations

import hashlib
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .fail import confluence_down
from .models import Manifest
from .paths import CONFLUENCE_SYNC_CWD
from .project_config import ProjectConfig


WHITELIST_EXT = {".mpp", ".mpx", ".xml", ".json"}
OLE2_SIG = b"\xd0\xcf\x11\xe0"
ZIP_SIG = b"PK\x03\x04"


@dataclass
class AttachmentMeta:
  page_id: str
  filename: str
  download_url: str
  filesize: int | None


def _client():
  if str(CONFLUENCE_SYNC_CWD) not in sys.path:
    sys.path.insert(0, str(CONFLUENCE_SYNC_CWD))
  from confluencesync.config import get_settings  # type: ignore
  from confluencesync.confluence_client import ConfluenceClient  # type: ignore

  settings = get_settings()
  return ConfluenceClient(settings.confluence_url, settings.confluence_token)


def is_whitelisted(filename: str, expected_names: set[str]) -> bool:
  lower = filename.lower()
  if lower in {n.lower() for n in expected_names}:
    return True
  return Path(filename).suffix.lower() in WHITELIST_EXT


def is_ole2_or_zip(path: Path) -> str:
  if path.suffix.lower() == ".json":
    return "json"
  head = path.read_bytes()[:4]
  if head.startswith(OLE2_SIG):
    return "ole2"
  if head.startswith(ZIP_SIG):
    return "zip"
  return "unknown"


def expected_attachment_names(cfg: ProjectConfig) -> set[str]:
  names: set[str] = set()
  expected = cfg.plan.get("expected_name") or ""
  if expected:
    names.add(str(expected))
  instance = cfg.gantt_instance
  if instance:
    names.add(f"gantt-chart-{instance}.json")
  return names


def list_whitelist(page_id: str, client: Any, expected_names: set[str]) -> list[AttachmentMeta]:
  metas: list[AttachmentMeta] = []
  for att in client.get_attachments(page_id):
    title = att.get("title") or ""
    if not is_whitelisted(title, expected_names):
      continue
    size = (att.get("extensions") or {}).get("fileSize")
    metas.append(
      AttachmentMeta(
        page_id=page_id,
        filename=title,
        download_url=client.attachment_download_url(page_id, title),
        filesize=int(size) if size is not None else None,
      )
    )
  return metas


def download_attachment(meta: AttachmentMeta, client: Any, dest_dir: Path) -> Path:
  dest_dir.mkdir(parents=True, exist_ok=True)
  dest = dest_dir / meta.filename
  resp = client.session.get(meta.download_url, stream=True, timeout=120)
  if resp.status_code in (401, 403):
    confluence_down(f"HTTP {resp.status_code} downloading {meta.filename}")
  resp.raise_for_status()
  with dest.open("wb") as fh:
    for chunk in resp.iter_content(chunk_size=65536):
      if chunk:
        fh.write(chunk)
  return dest


def sync_attachments(cfg: ProjectConfig, manifest: Manifest, overlay: Path) -> dict[str, Any]:
  client = _client()
  if not client.ping():
    confluence_down("ping failed")
  expected = expected_attachment_names(cfg)
  page_ids = cfg.attachment_page_ids
  now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
  records: list[dict[str, Any]] = []
  for page_id in page_ids:
    for meta in list_whitelist(page_id, client, expected):
      local = download_attachment(meta, client, overlay / "attachments")
      data = local.read_bytes()
      records.append(
        {
          "filename": meta.filename,
          "page_id": meta.page_id,
          "download_url": meta.download_url,
          "local_path": str(local.relative_to(overlay)),
          "sha256": hashlib.sha256(data).hexdigest(),
          "filesize": len(data),
          "format_hint": is_ole2_or_zip(local),
          "synced_at": now,
        }
      )
  manifest.attachments = records
  return {"downloaded": len(records), "attachments": records}
