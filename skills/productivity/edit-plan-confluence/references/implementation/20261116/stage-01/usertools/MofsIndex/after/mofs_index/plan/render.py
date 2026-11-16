"""MD-витрина плана, собранная из SQL (P3.MD.1-3, R-024/R-025).

``render_plan_md(plan_id)`` — одна read-транзакция SQL → один MD-файл на
план (``<slug>.ganttchart.md``, Q2 DECISIONS-owner.md) → temp-файл → hash
сверка → atomic rename. ``generation`` в frontmatter растёт на каждый
успешный рендер; ``plan_projection`` хранит последний известный hash, чтобы
обнаружить ручную правку файла в обход рендерера (``conflict``, R-025,
AC-128) — рендер не перезаписывает файл молча, если hash на диске не
совпадает с ожидаемым по записи в БД.
"""
from __future__ import annotations

import hashlib
import os
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from . import query as plan_query
from . import writer as plan_writer

WORKVAULT_ROOT = Path.home() / "WorkVault"


class RenderConflict(RuntimeError):
    """Ручная правка MD обнаружена (hash на диске != ожидаемый, AC-128)."""


@dataclass(frozen=True)
class RenderResult:
    plan_id: str
    md_path: Path
    generation: int
    content_sha256: str
    status: str  # ok|conflict|stale|failed
    conflict_detail: str | None = None


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _last_projection(conn: sqlite3.Connection, plan_id: str, md_path: str) -> tuple[int, str] | None:
    row = conn.execute(
        "SELECT generation, content_sha256 FROM plan_projection "
        "WHERE plan_id = ? AND md_path = ? ORDER BY generation DESC LIMIT 1",
        (plan_id, md_path),
    ).fetchone()
    return tuple(row) if row else None


def _fmt_dt(dt: str | None) -> str:
    return dt if dt else "неизвестно"


def _build_markdown(conn: sqlite3.Connection, plan_id: str, plan_meta: dict[str, Any], generation: int) -> str:
    versions = plan_query.list_versions(conn, plan_id)["versions"]
    publications = [v for v in versions if v["kind"] == "publication"]
    snapshots = [v for v in versions if v["kind"] == "snapshot"]

    lines: list[str] = []
    lines.append("---")
    lines.append(f"plan_id: {plan_id}")
    lines.append(f"project_slug: {plan_meta['project_slug']}")
    lines.append(f"generation: {generation}")
    lines.append(f"rendered_at: {_now()}")
    lines.append(f"publication_count: {len(publications)}")
    lines.append(f"snapshot_count: {len(snapshots)}")
    lines.append("source: SQL (mofs_index/plan/render.py::render_plan_md), не ручная правка")
    lines.append("---")
    lines.append("")
    lines.append(f"# Архив слепков плана — {plan_meta.get('name') or plan_meta['project_slug']}")
    lines.append("")

    if publications:
        latest = publications[-1]
        lines.append("## Последняя регистрация публикации")
        lines.append("")
        lines.append(f"- Версия: {latest['attachment_version']}")
        lines.append(f"- Доверие: {latest['trust']}; подтверждение полным конвейером: {latest['publication_verified']}")
        lines.append("- Регистрация и текущее read-back-наблюдение не доказывают историческую публикацию.")
        lines.append(f"- Hash: `{latest['raw_sha256']}`")
        lines.append(f"- Записано: {_fmt_dt(latest['recorded_at'])}")
        lines.append("")

    lines.append("## Публикации (Gantt JSON)")
    lines.append("")
    lines.append("| Версия | Hash | Записано | Доверие |")
    lines.append("|---|---|---|---|")
    for p in publications:
        lines.append(f"| {p['attachment_version']} | `{(p['raw_sha256'] or '')[:12]}…` | {_fmt_dt(p['recorded_at'])} | {p['trust']} |")
    lines.append("")

    if snapshots:
        lines.append("## Снимки MPP (полный граф, UID/ES-EF-LS-LF)")
        lines.append("")
        lines.append("| snapshot_id | observed_at | source_artifact_id |")
        lines.append("|---|---|---|")
        for s in snapshots:
            lines.append(
                f"| `{s['snapshot_id']}` | {_fmt_dt(s['observed_at'])} | "
                f"`{s['source_artifact_id']}` |"
            )
        lines.append("")

    lines.append("## Сравнения между соседними публикациями")
    lines.append("")
    for a, b in zip(publications, publications[1:]):
        d = plan_query.diff_versions(
            conn, plan_id,
            {"kind": "publication", "attachment_version": a["attachment_version"]},
            {"kind": "publication", "attachment_version": b["attachment_version"]},
        )
        lines.append(f"### v{a['attachment_version']} → v{b['attachment_version']}")
        lines.append("")
        if d.get("content_identical"):
            lines.append("Байты идентичны (diff=0).")
        else:
            root = d.get("root", {})
            lines.append(
                f"- Финал: {root.get('finish_a')} → {root.get('finish_b')} "
                f"({root.get('finish_delta_calendar_days'):+} календарных суток)"
                if root.get("finish_delta_calendar_days") is not None else "- Финал: без изменений"
            )
            if root.get("duration_delta") is not None:
                lines.append(f"- Длительность: {root.get('duration_a')} → {root.get('duration_b')} ({root.get('duration_delta'):+})")
            if d.get("links_removed"):
                lines.append(f"- Удалены связи: {d['links_removed']}")
            if d.get("links_added"):
                lines.append(f"- Добавлены связи: {d['links_added']}")
            lines.append(f"- {d.get('caveat', '')}")
        lines.append("")

    if len(snapshots) >= 2:
        lines.append("## Сравнение MPP-снимков (UID-уровень)")
        lines.append("")
        sd = plan_query.diff_versions(
            conn, plan_id,
            {"kind": "snapshot", "snapshot_id": snapshots[0]["snapshot_id"]},
            {"kind": "snapshot", "snapshot_id": snapshots[-1]["snapshot_id"]},
        )
        lines.append(f"- Финал: {sd['root'].get('finish_a')} → {sd['root'].get('finish_b')} "
                     f"({sd['root'].get('finish_delta_calendar_days')} календарных суток)")
        if sd.get("changed_tasks"):
            lines.append("")
            lines.append("| UID | Задача | Было | Стало |")
            lines.append("|---|---|---|---|")
            for ct in sd["changed_tasks"]:
                fin = ct["changes"].get("finish")
                if fin:
                    lines.append(f"| {ct['uid']} | {ct.get('task_key')} | {fin['from']} | {fin['to']} |")
        lines.append("")

    lines.append("---")
    lines.append("")
    lines.append(
        "Файл сгенерирован автоматически рендерером `mofs_index/plan/render.py`. "
        "Ручная правка будет обнаружена как `conflict` при следующем рендере и не "
        "будет тихо перезаписана."
    )
    lines.append("")
    return "\n".join(lines)


def render_plan_md(conn: sqlite3.Connection, plan_id: str, *, md_path: str | None = None) -> RenderResult:
    """Собрать MD одной read-транзакцией SQL, записать через temp → hash → atomic rename.

    ``md_path`` по умолчанию берётся из ``plan.md_path`` (Q2: ``Entities/<slug>/Pages/<slug>.ganttchart.md``).
    """
    plan_row = conn.execute(
        "SELECT project_slug, name, md_path FROM plan WHERE plan_id = ?", (plan_id,)
    ).fetchone()
    if plan_row is None:
        raise ValueError(f"plan_id={plan_id} не найден")
    project_slug, name, default_md_path = plan_row
    rel_path = md_path or default_md_path
    if not rel_path:
        raise ValueError(f"plan_id={plan_id} не имеет md_path (Q2: <slug>.ganttchart.md)")

    abs_path = WORKVAULT_ROOT / rel_path if not Path(rel_path).is_absolute() else Path(rel_path)

    previous = _last_projection(conn, plan_id, rel_path)
    next_generation = (previous[0] + 1) if previous else 1

    # AC-128: если файл на диске существует и не совпадает с последним
    # известным hash рендерера — ручная правка в обход протокола, конфликт,
    # не тихая перезапись.
    if previous is not None and abs_path.exists():
        on_disk_sha = hashlib.sha256(abs_path.read_bytes()).hexdigest()
        if on_disk_sha != previous[1]:
            detail = (
                f"файл {abs_path} изменён вручную в обход рендерера "
                f"(ожидался hash {previous[1][:12]}…, на диске {on_disk_sha[:12]}…)"
            )
            plan_writer_record_projection(conn, plan_id, str(rel_path), previous[0], previous[1], None, "conflict", detail)
            return RenderResult(plan_id=plan_id, md_path=abs_path, generation=previous[0],
                                 content_sha256=on_disk_sha, status="conflict", conflict_detail=detail)

    content = _build_markdown(conn, plan_id, {"project_slug": project_slug, "name": name}, next_generation)
    content_sha256 = hashlib.sha256(content.encode("utf-8")).hexdigest()

    abs_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = abs_path.with_suffix(abs_path.suffix + f".tmp-{os.getpid()}")
    tmp_path.write_text(content, encoding="utf-8")
    written_sha256 = hashlib.sha256(tmp_path.read_bytes()).hexdigest()
    if written_sha256 != content_sha256:
        tmp_path.unlink(missing_ok=True)
        raise RuntimeError("hash temp-файла не совпал с ожидаемым — рендер прерван до rename")
    os.replace(tmp_path, abs_path)  # atomic rename в пределах одной ФС

    plan_writer_record_projection(conn, plan_id, str(rel_path), next_generation, content_sha256, None, "ok", None)
    return RenderResult(plan_id=plan_id, md_path=abs_path, generation=next_generation,
                         content_sha256=content_sha256, status="ok")


def plan_writer_record_projection(
    conn: sqlite3.Connection, plan_id: str, md_path: str, generation: int,
    content_sha256: str, last_snapshot_id: str | None, status: str, conflict_detail: str | None,
) -> str:
    import uuid
    projection_id = f"projection_{uuid.uuid4().hex}"
    conn.execute("BEGIN")
    try:
        # UNIQUE(plan_id, md_path): plan_projection хранит ПОСЛЕДНЕЕ известное
        # состояние рендера (не append-only историю) — generation в теле
        # строки отражает номер попытки, upsert на конфликте ключа.
        conn.execute(
            "INSERT INTO plan_projection(projection_id, plan_id, md_path, generation, "
            "content_sha256, last_snapshot_id, status, conflict_detail, rendered_at) "
            "VALUES (?,?,?,?,?,?,?,?,?) "
            "ON CONFLICT(plan_id, md_path) DO UPDATE SET "
            "generation=excluded.generation, content_sha256=excluded.content_sha256, "
            "last_snapshot_id=excluded.last_snapshot_id, status=excluded.status, "
            "conflict_detail=excluded.conflict_detail, rendered_at=excluded.rendered_at",
            (projection_id, plan_id, md_path, generation, content_sha256,
             last_snapshot_id, status, conflict_detail, _now()),
        )
        conn.execute("COMMIT")
    except Exception:
        conn.execute("ROLLBACK")
        raise
    if status == "ok":
        _index_fts(conn, plan_id, md_path, generation, content_sha256)
    return projection_id


def _index_fts(conn: sqlite3.Connection, plan_id: str, md_path: str, generation: int, content_sha256: str) -> None:
    """P3.RAG.5: запись FTS при рендере (не на каждый ingest)."""
    conn.execute("DELETE FROM plan_fts WHERE plan_id = ?", (plan_id,))
    body = Path(WORKVAULT_ROOT / md_path).read_text(encoding="utf-8") if (WORKVAULT_ROOT / md_path).exists() else ""
    conn.execute(
        "INSERT INTO plan_fts(plan_id, publication_id, snapshot_id, representation, anchor, generation, body) "
        "VALUES (?, NULL, NULL, 'md', ?, ?, ?)",
        (plan_id, md_path, generation, body),
    )
    conn.commit()
