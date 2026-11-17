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
    lines.append("Витрина — производная проекция. Точные ID и свидетельства проверяются typed API; порядок регистрации не гарантирует актуальность страницы.")
    lines.append("")

    if publications:
        latest = publications[-1]
        lines.append("## Последняя регистрация публикации")
        lines.append("")
        lines.append(f"- ID: `{latest['publication_id']}`; страница `{latest['page_id']}`; attachment `{latest['attachment_id']}`; версия {latest['attachment_version']}")
        lines.append(f"- Доверие: {latest['trust']}; подтверждение полным конвейером: {latest['publication_verified']}")
        lines.append("- Регистрация и текущее read-back-наблюдение не доказывают историческую публикацию.")
        lines.append(f"- Hash: `{latest['raw_sha256']}`")
        lines.append(f"- Записано: {_fmt_dt(latest['recorded_at'])}")
        lines.append("")

    lines.append("## Публикации (Gantt JSON)")
    lines.append("")
    lines.append("| publication_id | Страница / attachment / версия | Representation | Hash | Записано | Доверие |")
    lines.append("|---|---|---|---|---|---|---|---|")
    for p in publications:
        lines.append(f"| `{p['publication_id']}` | {p['page_id']} / {p['attachment_id']} / {p['attachment_version']} | gantt_json | `{(p['raw_sha256'] or '')[:12]}` | {_fmt_dt(p['recorded_at'])} | {p['trust']} |")
        for obs in p['observations']:
            lines.append(f"- Наблюдение `{obs['observation_id']}`: {obs['verified_at']}, {obs['verification_scope']}, {obs['verification_status']}; историческая дата не восстановлена.")
        for link in p['snapshot_links']:
            lines.append(f"- Snapshot `{link['snapshot_id']}`: link quality `{link['confidence']}`, evidence `{link['evidence']}`.")
    lines.append("")

    if snapshots:
        lines.append("## Снимки и качество сохранённых представлений")
        lines.append("")
        lines.append("| snapshot_id | representation / качество | observed_at | source_artifact_id |")
        lines.append("|---|---|---|---|")
        for s in snapshots:
            lines.append(
                f"| `{s['snapshot_id']}` | {s['representation']} / качество через typed compare | {_fmt_dt(s['observed_at'])} | "
                f"`{s['source_artifact_id']}` |"
            )
        lines.append("")

    lines.append("## Сравнения точных записей")
    lines.append("")
    pairs = list(zip(publications,publications[1:]))
    if len(snapshots)>=2:
        pairs.append((snapshots[0],snapshots[-1]))
    for a,b in pairs:
        sa = {'kind':a['kind'],a['kind']+'_id':a[a['kind']+'_id']}
        sb = {'kind':b['kind'],b['kind']+'_id':b[b['kind']+'_id']}
        lines.append(f"- `{sa}` → `{sb}`")
        try:
            d = plan_query.diff_versions(conn,plan_id,sa,sb)
            receipt = d['receipt']
            lines.append(f"  Mapping: `{receipt.get('mapping')}`; revision: `{receipt.get('mapping_revision_id')}`; evidence: `{receipt.get('evidence_id')}`; completeness: `{receipt.get('completeness')}`; calendar: `{receipt.get('calendar')}`.")
            if d.get('content_identical'):
                lines.append("  Байты идентичны; идентичность задач и историческое доверие проверяются отдельно.")
            lines.append(f"  Изменения: задачи={len(d.get('changed_tasks',[]))}, связи -{len(d.get('links_removed',[]))}/+{len(d.get('links_added',[]))}, календари={len(d.get('changed_calendars',[]))}, назначения={len(d.get('changed_assignments',[]))}.")
            lines.append("  Несопоставленные сущности: " + str({k:{side:len(rows) for side,rows in v.items()} for k,v in d.get('unmatched_entities',{}).items()}))
        except (plan_query.PlanQueryError, ValueError) as exc:
            lines.append(f"  Сравнение недоступно: `{getattr(exc,'code',type(exc).__name__)}`.")
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
