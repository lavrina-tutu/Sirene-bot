"""Download / upload gantt-chart-<param_id>.json attachment."""
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from conf_client import ConfluenceClient, ConfluenceError
from macro import MacroInfo
from plan_verify import verify_attachment_bytes


@dataclass
class AttachmentInfo:
    attach_id: str
    filename: str
    version: int
    title: str


class UploadVerificationConflict(RuntimeError):
    """GET версии, полученной из ответа upload, не совпал по hash с отправленным (R-009 п.7)."""


def attachment_info(data: dict) -> AttachmentInfo:
    """Require server-supplied identity; filename/version guesses are unsafe."""
    attach_id = data.get("id")
    filename = data.get("title")
    version = (data.get("version") or {}).get("number")
    if not attach_id or not filename or type(version) is not int or version < 1:
        raise UploadVerificationConflict("missing actual attachment ID/title/version")
    return AttachmentInfo(str(attach_id), filename, version, filename)


def find_gantt_attachment(attachments: list[dict], macro: MacroInfo) -> AttachmentInfo | None:
    matches = [att for att in attachments if att.get("title") == macro.attachment_name]
    if len(matches) > 1:
        raise UploadVerificationConflict("ambiguous attachment filename")
    return attachment_info(matches[0]) if matches else None


def verify_current_attachment(client, page_id, uploaded: AttachmentInfo, expected_sha256: str) -> bytes:
    matches = [att for att in client.list_attachments(page_id) if att.get("title") == uploaded.filename]
    if len(matches) != 1:
        raise UploadVerificationConflict("current attachment is missing or ambiguous")
    current = attachment_info(matches[0])
    if current.attach_id != uploaded.attach_id or current.version != uploaded.version:
        raise UploadVerificationConflict("current attachment differs from uploaded ID/version")
    ok, raw = verify_uploaded(client, page_id, uploaded.filename, uploaded.version,
                              expected_sha256, attachment_id=uploaded.attach_id)
    if not ok:
        raise UploadVerificationConflict("current attachment SHA-256 mismatch")
    return raw


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
) -> AttachmentInfo:
    payload = json.dumps(gantt, ensure_ascii=False).encode("utf-8")
    if existing:
        return _post_attachment_data(client, page_id, existing.attach_id, filename, payload)
    return _create_attachment(client, page_id, filename, payload)


def upload_prepared_bytes(client, page_id, filename, raw: bytes, existing, expected_sha256):
    """Send the archived representation verbatim; never reserialize parsed JSON."""
    if not isinstance(raw, bytes) or not verify_attachment_bytes(raw, expected_sha256).ok:
        raise UploadVerificationConflict('prepared bytes SHA-256 mismatch')
    return (_post_attachment_data(client, page_id, existing.attach_id, filename, raw)
            if existing else _create_attachment(client, page_id, filename, raw))


def verify_uploaded(
    client: ConfluenceClient,
    page_id: str | int,
    filename: str,
    version: int,
    expected_sha256: str,
    *,
    attachment_id: str | None = None,
) -> tuple[bool, bytes]:
    """Version-specific GET полученной конкретной версии (не ``latest``),
    сверка hash полученных байт с отправленными (R-009 п.7, P1.W1.5, AC-105).

    Несовпадение возвращается как ``(False, raw)`` — вызывающая сторона
    обязана пометить это конфликтом, не перезаписывая подготовленные байты
    фактическими (не поднимать исключение молча здесь, чтобы caller мог
    записать событие ``attachment_verify=conflict`` перед остановкой).
    """
    if type(version) is not int or version < 1:
        raise UploadVerificationConflict("positive exact attachment version required")
    if attachment_id is None:
        matches = [att for att in client.list_attachments(page_id) if att.get("title") == filename]
        if len(matches) != 1:
            raise UploadVerificationConflict("cannot resolve exact attachment identity")
        attachment_id = attachment_info(matches[0]).attach_id
    raw = client.download_attachment_version(page_id, attachment_id, filename, version)
    return verify_attachment_bytes(raw, expected_sha256).ok, raw


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
) -> AttachmentInfo:
    body, ctype = _multipart_body(filename, content, "application/json")
    url = f"{client.base_url}/rest/api/content/{page_id}/child/attachment/{attach_id}/data"
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
        with urlopen(req, timeout=client.timeout) as resp:
            raw = resp.read()
    except HTTPError as exc:
        raise ConfluenceError(exc.code, exc.read().decode("utf-8", errors="replace")) from exc
    data = json.loads(raw.decode("utf-8"))
    results = data.get("results") or [data]
    if len(results) != 1:
        raise UploadVerificationConflict("ambiguous upload response")
    result = attachment_info(results[0])
    if result.attach_id != str(attach_id) or result.filename != filename:
        raise UploadVerificationConflict("upload response identity mismatch")
    return result


def _create_attachment(client: ConfluenceClient, page_id: str | int, filename: str, content: bytes) -> AttachmentInfo:
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
        with urlopen(req, timeout=client.timeout) as resp:
            raw = resp.read()
    except HTTPError as exc:
        raise ConfluenceError(exc.code, exc.read().decode("utf-8", errors="replace")) from exc
    data = json.loads(raw.decode("utf-8"))
    results = data.get("results") or [data]
    if len(results) != 1:
        raise UploadVerificationConflict("ambiguous upload response")
    result = attachment_info(results[0])
    if result.filename != filename:
        raise UploadVerificationConflict("upload response filename mismatch")
    return result
