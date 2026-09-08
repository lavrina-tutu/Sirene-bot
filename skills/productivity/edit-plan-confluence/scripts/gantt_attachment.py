"""Download / upload gantt-chart-<macro-id>.json attachment."""
from __future__ import annotations

import io
import json
import mimetypes
from dataclasses import dataclass
from typing import Any
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from conf_client import ConfluenceClient, ConfluenceError
from macro import MacroInfo, find_macro


@dataclass
class AttachmentInfo:
    attach_id: str
    filename: str
    version: int
    title: str


def find_gantt_attachment(attachments: list[dict], macro: MacroInfo) -> AttachmentInfo | None:
    def _ver(att: dict) -> int:
        v = att.get("version") or {}
        if isinstance(v, dict):
            return int(v.get("number", 1))
        return 1

    for att in attachments:
        if att.get("title") == macro.attachment_name:
            return AttachmentInfo(
                attach_id=str(att["id"]),
                filename=macro.attachment_name,
                version=_ver(att),
                title=att["title"],
            )
    for att in attachments:
        title = att.get("title", "")
        if title.startswith("gantt-chart-") and title.endswith(".json"):
            return AttachmentInfo(
                attach_id=str(att["id"]),
                filename=title,
                version=_ver(att),
                title=title,
            )
    return None


def load_gantt_json(client: ConfluenceClient, page_id: str | int, macro: MacroInfo) -> tuple[dict[str, Any], AttachmentInfo | None]:
    attachments = client.list_attachments(page_id)
    att = find_gantt_attachment(attachments, macro)
    if not att:
        return {}, None
    raw = client.download_attachment(page_id, att.filename, att.version)
    return json.loads(raw.decode("utf-8")), att


def upload_gantt_json(
    client: ConfluenceClient,
    page_id: str | int,
    filename: str,
    gantt: dict[str, Any],
    existing: AttachmentInfo | None,
) -> int:
    payload = json.dumps(gantt, ensure_ascii=False).encode("utf-8")
    if existing:
        return _post_attachment_data(client, page_id, existing.attach_id, filename, payload)
    return _create_attachment(client, page_id, filename, payload)


def _multipart_body(filename: str, content: bytes, content_type: str) -> tuple[bytes, str]:
    boundary = "----EditPlanConfluenceBoundary"
    parts = [
        f"--{boundary}\r\n".encode(),
        f'Content-Disposition: form-data; name="file"; filename="{filename}"\r\n'.encode(),
        f"Content-Type: {content_type}\r\n\r\n".encode(),
        content,
        b"\r\n",
        f"--{boundary}--\r\n".encode(),
    ]
    body = b"".join(parts)
    return body, f"multipart/form-data; boundary={boundary}"


def _post_attachment_data(
    client: ConfluenceClient,
    page_id: str | int,
    attach_id: str,
    filename: str,
    content: bytes,
) -> int:
    body, ctype = _multipart_body(filename, content, "application/json")
    url = (
        f"{client.base_url}/rest/api/content/{page_id}/child/attachment/{attach_id}/data"
        f"?{urlencode({'conflictPolicy': 'override'})}"
    )
    req = Request(
        url,
        data=body,
        headers={
            "Authorization": f"Bearer {client.token}",
            "Content-Type": ctype,
            "X-Atlassian-Token": "no-check",
        },
        method="POST",
    )
    try:
        with urlopen(req, timeout=120) as resp:
            raw = resp.read()
    except HTTPError as exc:
        raise ConfluenceError(exc.code, exc.read().decode("utf-8", errors="replace")) from exc
    data = json.loads(raw.decode("utf-8"))
    results = data.get("results") or [data]
    return int(results[0].get("version", {}).get("number", 0))


def _create_attachment(client: ConfluenceClient, page_id: str | int, filename: str, content: bytes) -> int:
    body, ctype = _multipart_body(filename, content, "application/json")
    url = f"{client.base_url}/rest/api/content/{page_id}/child/attachment"
    req = Request(
        url,
        data=body,
        headers={
            "Authorization": f"Bearer {client.token}",
            "Content-Type": ctype,
            "X-Atlassian-Token": "no-check",
        },
        method="POST",
    )
    try:
        with urlopen(req, timeout=120) as resp:
            raw = resp.read()
    except HTTPError as exc:
        raise ConfluenceError(exc.code, exc.read().decode("utf-8", errors="replace")) from exc
    data = json.loads(raw.decode("utf-8"))
    results = data.get("results") or [data]
    return int(results[0].get("version", {}).get("number", 1))
