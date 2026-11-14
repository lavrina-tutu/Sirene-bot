"""Импорт истории ZD (P1.W1.10/11) — только GET, пагинация, карта пропусков.

R-011: явная операция импорта читает метаданные/байты конкретных версий;
403/404/timeout/пустой список различаются и протоколируются (AC-112).
Контрольный диапазон v1..v6 даёт шесть событий / четыре уникальных JSON
hash — сверка с таблицей R-036 §10 ТЗ.
"""
from __future__ import annotations

import hashlib
import socket
import sqlite3
import sys
from dataclasses import dataclass, field
from pathlib import Path
from urllib.error import HTTPError, URLError

MOFS_INDEX_ROOT = Path.home() / "USERTOOLS" / "MofsIndex"
if str(MOFS_INDEX_ROOT) not in sys.path:
    sys.path.insert(0, str(MOFS_INDEX_ROOT))

from mofs_index.plan import writer as plan_writer  # noqa: E402

from conf_client import ConfluenceClient, ConfluenceError  # noqa: E402
from plan_archive import CONFLUENCE_NAMESPACE, _connect, resolve_plan_binding, store_artifact  # noqa: E402


@dataclass
class VersionOutcome:
    version: int
    status: str  # ok|not_found|forbidden|timeout|unknown
    sha256: str | None = None
    size: int | None = None
    publication_id: str | None = None
    reason: str | None = None


@dataclass
class HistoryReport:
    page_id: str
    attachment_id: str
    outcomes: list[VersionOutcome] = field(default_factory=list)
    attempt_id: str = ""

    @property
    def event_count(self) -> int:
        return sum(1 for o in self.outcomes if o.status == "ok")

    @property
    def unique_hashes(self) -> set[str]:
        return {o.sha256 for o in self.outcomes if o.sha256}


def _classify_error(exc: Exception) -> tuple[str, str]:
    if isinstance(exc, ConfluenceError):
        if exc.status == 403:
            return "forbidden", "HTTP 403"
        if exc.status == 404:
            return "not_found", "HTTP 404"
        return "unknown", f"HTTP {exc.status}"
    if isinstance(exc, (socket.timeout, TimeoutError)):
        return "timeout", "timeout"
    if isinstance(exc, URLError):
        return "timeout", f"URLError: {exc}"
    return "unknown", str(exc)


def import_history(
    client: ConfluenceClient,
    page_id: str,
    attachment_id: str,
    version_range: range,
    *,
    project_slug: str = "zd",
    filename: str | None = None,
    db_path: Path | None = None,
    conn: sqlite3.Connection | None = None,
    resume_attempt_id: str | None = None,
) -> HistoryReport:
    """GET-only импорт истории ``attachment_id`` на ``page_id`` для версий
    ``version_range``. Повтор не увеличивает числа (идемпотентность по UQ
    ``plan_publication``). Не публикует, не POST/PUT.

    P1.W1.10-доб. (идемпотентность archive-history): ``resume_attempt_id`` —
    внешний resume-ключ, строка ``attempt_id`` из предыдущего вызова (см.
    ``HistoryReport.attempt_id``). При повторном вызове с тем же
    ``resume_attempt_id`` переиспользуется существующая строка
    ``plan_import_attempt`` (``begin_attempt`` идемпотентен по PK) — новая
    попытка не плодится. Без явного resume-ключа каждый вызов создаёт новую
    попытку (прежнее поведение сохранено)."""
    report = HistoryReport(page_id=page_id, attachment_id=attachment_id)
    own_conn = conn is None
    c = conn or _connect(db_path)
    try:
        binding = resolve_plan_binding(page_id, project_slug, conn=c)
        plan_id = binding["plan_id"]
        lineage_id = binding["lineage_id"]

        if filename is None:
            attachments = client.list_attachments(page_id)
            match = next((a for a in attachments if str(a.get("id")) == str(attachment_id)), None)
            filename = match["title"] if match else f"gantt-chart-{attachment_id}.json"

        attempt_id = plan_writer.begin_attempt(
            c,
            plan_writer.AttemptSpec(
                plan_id=plan_id,
                lineage_id=lineage_id,
                source_namespace=CONFLUENCE_NAMESPACE,
                range_from=str(version_range.start),
                range_to=str(version_range.stop - 1),
                attempt_id=resume_attempt_id,
            ),
        )
        report.attempt_id = attempt_id

        for version in version_range:
            try:
                raw = client.download_attachment(page_id, filename, version)
            except Exception as exc:  # noqa: BLE001 — классифицируем все сетевые отказы
                status, reason = _classify_error(exc)
                outcome = VersionOutcome(version=version, status=status, reason=reason)
                report.outcomes.append(outcome)
                plan_writer.record_event(
                    c, attempt_id, "archive", "unknown" if status == "unknown" else "failed",
                    detail=f"version={version} status={status} reason={reason}",
                )
                # P2 хвост (AC-111): персистентная отметка "MPP vN missing" —
                # не только событие попытки (эфемерно в контексте одного
                # attempt), но отдельная строка plan_quality_issue, видимая
                # независимо от того, какой attempt её завёл.
                plan_writer.record_quality_issue(
                    c, plan_id, "missing_source_version", "warning",
                    lineage_id=lineage_id,
                    detail=f"page_id={page_id} attachment_id={attachment_id} "
                           f"version={version} status={status} reason={reason}",
                )
                continue

            if not raw:
                outcome = VersionOutcome(version=version, status="not_found", reason="пустой ответ")
                report.outcomes.append(outcome)
                plan_writer.record_event(
                    c, attempt_id, "archive", "unknown",
                    detail=f"version={version} status=empty",
                )
                plan_writer.record_quality_issue(
                    c, plan_id, "missing_source_version", "warning",
                    lineage_id=lineage_id,
                    detail=f"page_id={page_id} attachment_id={attachment_id} "
                           f"version={version} status=not_found reason=пустой ответ",
                )
                continue

            sha256 = hashlib.sha256(raw).hexdigest()
            artifact_id, _ = store_artifact(
                raw, "downloaded_json", project_slug=project_slug, conn=c,
            )
            publication_id = plan_writer.record_publication(
                c,
                plan_writer.PublicationSpec(
                    plan_id=plan_id,
                    lineage_id=lineage_id,
                    artifact_id=artifact_id,
                    source_namespace=CONFLUENCE_NAMESPACE,
                    attachment_id=str(attachment_id),
                    attachment_version=version,
                    page_id=page_id,
                    filename=filename,
                    raw_sha256=sha256,
                ),
            )
            plan_writer.record_event(
                c, attempt_id, "archive", "confirmed",
                detail=f"version={version} sha256={sha256}",
            )
            report.outcomes.append(VersionOutcome(
                version=version, status="ok", sha256=sha256, size=len(raw),
                publication_id=publication_id,
            ))

        plan_writer.set_attempt_status(c, attempt_id, "confirmed")
    finally:
        if own_conn:
            c.close()
    return report


def find_mpp_by_hash(known_hashes: dict[str, str], search_roots: list[Path]) -> dict[str, Path | None]:
    """Искать по известным sha256 среди ``search_roots``; если файл исчез —
    фиксировать отсутствие, не выдумывать исходник (R-036)."""
    found: dict[str, Path | None] = {label: None for label in known_hashes}
    for root in search_roots:
        if not root.is_dir():
            continue
        for p in root.iterdir():
            if not p.is_file():
                continue
            try:
                h = hashlib.sha256(p.read_bytes()).hexdigest()
            except OSError:
                continue
            for label, expected in known_hashes.items():
                if h == expected and found[label] is None:
                    found[label] = p
    return found
