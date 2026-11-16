"""Typed query API для архива слепков плана (P3.RAG.1-8, R-023/R-026/R-027).

Публичные функции принимают параметры из R-026 (plan/project_slug,
конкретные версии/snapshot_id, representation) — не свободный SQL от
вызывающей стороны (LLM/workvault-rag). Каждая функция возвращает typed dict
с обязательным полем ``receipt`` (R-026: план/линия, A/B, representation,
mapping, baseline, target, календарь, completeness, hashes, known_at).

Две "версии" плана в этом архиве — разные представления с разным
идентификатором:
  * Confluence-публикация Gantt JSON — ``{"kind": "publication",
    "attachment_version": N}`` (плотная история v1..v6 ZD, только Gantt-id,
    без UID).
  * MPP snapshot — ``{"kind": "snapshot", "snapshot_id": "..."}`` (полный
    граф с UID/ES-EF-LS-LF/календарями, но только те версии, для которых
    исходный MPP реально сохранён, R-036).

Смешение представлений в одном ``diff_versions`` вызове — явный
``representation_mismatch`` блокер (R-029), не тихое совпадение по
числовому id (Gantt id и MPP uid — разные пространства идентичности, S3
RS1-collect.md: "UID доступен в MppReader, потерян в Gantt").
"""
from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

VersionSelector = dict[str, Any]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class PlanQueryError(RuntimeError):
    """Селектор не разрешается в конкретную запись / неоднозначен (R-026)."""


# ─────────────────────────────────────────────────────────────────────────
# resolve_plan / list_versions
# ─────────────────────────────────────────────────────────────────────────


def resolve_plan(conn: sqlite3.Connection, project_slug: str) -> dict[str, Any]:
    """Разрешить ``project_slug`` (напр. ``"zd"``) в ``plan_id`` + метаданные.

    Неоднозначность отсутствует по конструкции (UQ(project_slug) в schema) —
    либо ровно одна запись, либо явная ``insufficient_data``.
    """
    row = conn.execute(
        "SELECT plan_id, project_slug, name, md_path, created_at FROM plan "
        "WHERE project_slug = ?",
        (project_slug,),
    ).fetchone()
    known_at = _now()
    if row is None:
        return {
            "result_class": "insufficient_data",
            "reason": f"план с project_slug={project_slug!r} не найден",
            "receipt": {"project_slug": project_slug, "known_at": known_at},
        }
    plan_id, slug, name, md_path, created_at = row
    return {
        "plan_id": plan_id,
        "project_slug": slug,
        "name": name,
        "md_path": md_path,
        "created_at": created_at,
        "receipt": {"plan_id": plan_id, "project_slug": slug, "known_at": known_at},
    }


def list_versions(conn: sqlite3.Connection, plan_id: str) -> dict[str, Any]:
    """Все известные версии плана — публикации (Gantt JSON) и снимки (MPP),
    в одном хронологическом списке, с явной пометкой representation."""
    publications = conn.execute(
        "SELECT publication_id, attachment_version, raw_sha256, filename, "
        "recorded_at, observed_at, published_at, trust, historical_status FROM plan_publication "
        "WHERE plan_id = ? ORDER BY attachment_version",
        (plan_id,),
    ).fetchall()
    snapshots = conn.execute(
        "SELECT snapshot_id, representation, status_date, observed_at, "
        "recorded_at, source_artifact_id FROM plan_snapshot "
        "WHERE plan_id = ? ORDER BY recorded_at",
        (plan_id,),
    ).fetchall()

    versions: list[dict[str, Any]] = []
    for pub_id, ver, sha, filename, recorded_at, observed_at, published_at, trust, historical_status in publications:
        versions.append({
            "kind": "publication",
            "publication_id": pub_id,
            "trust": trust,
            "historical_status": historical_status,
            "publication_verified": trust == "verified_v1",
            "attachment_version": ver,
            "representation": "gantt_json",
            "raw_sha256": sha,
            "filename": filename,
            "recorded_at": recorded_at,
            "observed_at": observed_at,
            "published_at": published_at,
        })
    for snap_id, repr_, status_date, observed_at, recorded_at, artifact_id in snapshots:
        versions.append({
            "kind": "snapshot",
            "snapshot_id": snap_id,
            "representation": repr_,
            "status_date": status_date,
            "observed_at": observed_at,
            "recorded_at": recorded_at,
            "source_artifact_id": artifact_id,
        })
    return {
        "plan_id": plan_id,
        "versions": versions,
        "receipt": {
            "plan_id": plan_id,
            "publication_count": len(publications),
            "snapshot_count": len(snapshots),
            "known_at": _now(),
        },
    }


# ─────────────────────────────────────────────────────────────────────────
# Внутренние загрузчики по представлению
# ─────────────────────────────────────────────────────────────────────────


def _load_publication(conn: sqlite3.Connection, plan_id: str, attachment_version: int) -> dict[str, Any]:
    row = conn.execute(
        "SELECT p.publication_id, p.raw_sha256, a.path, p.recorded_at, p.trust, p.historical_status "
        "FROM plan_publication p JOIN plan_artifact a ON a.artifact_id = p.artifact_id "
        "WHERE p.plan_id = ? AND p.attachment_version = ?",
        (plan_id, attachment_version),
    ).fetchone()
    if row is None:
        raise PlanQueryError(f"публикация v{attachment_version} не найдена для plan_id={plan_id}")
    publication_id, sha256, path, recorded_at, trust, historical_status = row
    body = json.loads(Path(path).read_text(encoding="utf-8"))
    return {
        "publication_id": publication_id,
        "trust": trust,
        "historical_status": historical_status,
        "publication_verified": trust == "verified_v1",
        "attachment_version": attachment_version,
        "raw_sha256": sha256,
        "recorded_at": recorded_at,
        "body": body,
    }


def _flatten_gantt(events: list[dict[str, Any]]) -> dict[int, dict[str, Any]]:
    out: dict[int, dict[str, Any]] = {}

    def walk(node: dict[str, Any]) -> None:
        out[node["id"]] = node
        for child in node.get("children", ()):
            walk(child)

    for root in events:
        walk(root)
    return out


def _load_snapshot(conn: sqlite3.Connection, snapshot_id: str) -> dict[str, Any]:
    snap_row = conn.execute(
        "SELECT plan_id, representation, timezone_hint, status_date, recorded_at "
        "FROM plan_snapshot WHERE snapshot_id = ?",
        (snapshot_id,),
    ).fetchone()
    if snap_row is None:
        raise PlanQueryError(f"snapshot_id={snapshot_id} не найден")
    plan_id, representation, timezone_hint, status_date, recorded_at = snap_row
    tasks = conn.execute(
        "SELECT task_key, uid, name, start_raw, finish_raw, duration_raw, "
        "early_start, early_finish, late_start, late_finish, percent_complete, "
        "constraint_type, constraint_date, outline_level "
        "FROM plan_task_version WHERE snapshot_id = ?",
        (snapshot_id,),
    ).fetchall()
    tasks_by_uid: dict[str, dict[str, Any]] = {}
    tasks_by_key: dict[str, dict[str, Any]] = {}
    cols = ("task_key", "uid", "name", "start", "finish", "duration", "early_start",
            "early_finish", "late_start", "late_finish", "percent_complete",
            "constraint_type", "constraint_date", "outline_level")
    for row in tasks:
        rec = dict(zip(cols, row))
        tasks_by_key[rec["task_key"]] = rec
        if rec["uid"] is not None:
            tasks_by_uid[rec["uid"]] = rec
    deps = conn.execute(
        "SELECT predecessor_task_key, successor_task_key, link_type, lag_raw "
        "FROM plan_dependency_version WHERE snapshot_id = ?",
        (snapshot_id,),
    ).fetchall()
    return {
        "snapshot_id": snapshot_id,
        "plan_id": plan_id,
        "representation": representation,
        "timezone_hint": timezone_hint,
        "status_date": status_date,
        "recorded_at": recorded_at,
        "tasks_by_key": tasks_by_key,
        "tasks_by_uid": tasks_by_uid,
        "dependencies": [
            {"predecessor_task_key": p, "successor_task_key": s, "link_type": t, "lag_raw": lag}
            for p, s, t, lag in deps
        ],
    }


# ─────────────────────────────────────────────────────────────────────────
# diff_versions (P3.RAG.2, R-023/R-036, AC-124)
# ─────────────────────────────────────────────────────────────────────────


def diff_versions(
    conn: sqlite3.Connection,
    plan_id: str,
    version_a: VersionSelector,
    version_b: VersionSelector,
    *, mapping_revision_id: str | None = None,
) -> dict[str, Any]:
    """Δ между двумя версиями одного представления.

    ``version_a``/``version_b`` — ``{"kind": "publication", "attachment_version": N}``
    или ``{"kind": "snapshot", "snapshot_id": "..."}``. Разные ``kind`` в
    одном вызове дают явный ``representation_mismatch`` (не "подогнанный"
    diff по случайно совпавшим числовым id, R-029).
    """
    known_at = _now()
    if version_a.get("kind") != version_b.get("kind"):
        return {
            "result_class": "representation_mismatch",
            "reason": (
                f"version_a.kind={version_a.get('kind')!r} != "
                f"version_b.kind={version_b.get('kind')!r}: нельзя напрямую "
                "сравнить Gantt-id (publication) и MPP-uid (snapshot) без "
                "подтверждённого mapping"
            ),
            "receipt": {"plan_id": plan_id, "version_a": version_a, "version_b": version_b, "known_at": known_at},
        }
    if version_a["kind"] == "publication":
        return _diff_publications(conn, plan_id, version_a["attachment_version"], version_b["attachment_version"])
    return _diff_snapshots(conn, plan_id, version_a["snapshot_id"], version_b["snapshot_id"], mapping_revision_id=mapping_revision_id)


def _diff_publications(conn: sqlite3.Connection, plan_id: str, ver_a: int, ver_b: int) -> dict[str, Any]:
    known_at = _now()
    a = _load_publication(conn, plan_id, ver_a)
    b = _load_publication(conn, plan_id, ver_b)
    if a["raw_sha256"] == b["raw_sha256"]:
        return {
            "result_class": "observed_diff",
            "content_identical": True,
            "delta": {},
            "publications_a": a["attachment_version"],
            "publications_b": b["attachment_version"],
            "receipt": {
                "plan_id": plan_id, "representation": "gantt_json",
                "version_a": ver_a, "version_b": ver_b,
                "hash_a": a["raw_sha256"], "hash_b": b["raw_sha256"],
                "trust_a": a["trust"], "trust_b": b["trust"],
                "publication_verified": a["publication_verified"] and b["publication_verified"],
                "completeness": "complete", "known_at": known_at,
            },
        }

    fa = _flatten_gantt(a["body"].get("eventsData", ()))
    fb = _flatten_gantt(b["body"].get("eventsData", ()))
    root_a = fa.get(1, {})
    root_b = fb.get(1, {})

    deps_a = {(d.get("from"), d.get("to")): d for d in a["body"].get("dependenciesData", ())}
    deps_b = {(d.get("from"), d.get("to")): d for d in b["body"].get("dependenciesData", ())}
    removed_links = sorted(set(deps_a) - set(deps_b))
    added_links = sorted(set(deps_b) - set(deps_a))

    def _parse(dt: str | None) -> datetime | None:
        if not dt:
            return None
        return datetime.fromisoformat(dt)

    start_a, start_b = _parse(root_a.get("startDate")), _parse(root_b.get("startDate"))
    finish_a, finish_b = _parse(root_a.get("endDate")), _parse(root_b.get("endDate"))
    dur_a, dur_b = root_a.get("duration"), root_b.get("duration")

    finish_delta_days = (finish_b - finish_a).days if (finish_a and finish_b) else None
    start_delta_days = (start_b - start_a).days if (start_a and start_b) else None

    changed_tasks = []
    common_ids = set(fa) & set(fb)
    for gid in sorted(common_ids):
        ta, tb = fa[gid], fb[gid]
        changes = {}
        for field_name in ("name", "startDate", "endDate", "duration", "parentId"):
            if ta.get(field_name) != tb.get(field_name):
                changes[field_name] = {"from": ta.get(field_name), "to": tb.get(field_name)}
        if changes:
            changed_tasks.append({"gantt_id": gid, "changes": changes})
    added_ids = sorted(set(fb) - set(fa))
    removed_ids = sorted(set(fa) - set(fb))

    return {
        "result_class": "observed_diff",
        "content_identical": False,
        "root": {
            "finish_delta_calendar_days": finish_delta_days,
            "start_delta_calendar_days": start_delta_days,
            "duration_a": dur_a,
            "duration_b": dur_b,
            "duration_delta": (dur_b - dur_a) if (dur_a is not None and dur_b is not None) else None,
            "finish_a": root_a.get("endDate"),
            "finish_b": root_b.get("endDate"),
        },
        "links_removed": [{"from": f, "to": t} for f, t in removed_links],
        "links_added": [{"from": f, "to": t} for f, t in added_links],
        "task_ids_added": added_ids,
        "task_ids_removed": removed_ids,
        "changed_tasks": changed_tasks,
        "caveat": (
            "Gantt-id — позиционный идентификатор представления, не подтверждённая "
            "идентичность задачи между версиями (identity mapping не выполнен на "
            "этом уровне представления, R-023/S3). Изменённые/добавленные/удалённые "
            "id — наблюдаемый факт расписания JSON, не доказанное переименование."
        ),
        "receipt": {
            "plan_id": plan_id, "representation": "gantt_json",
            "version_a": ver_a, "version_b": ver_b,
            "hash_a": a["raw_sha256"], "hash_b": b["raw_sha256"],
                "trust_a": a["trust"], "trust_b": b["trust"],
                "publication_verified": a["publication_verified"] and b["publication_verified"],
            "mapping": "positional_gantt_id", "calendar": "unknown_from_json",
            "timezone": "Europe/Moscow" if plan_id else None,
            "completeness": "complete", "known_at": known_at,
        },
    }


def _diff_snapshots(conn: sqlite3.Connection, plan_id: str, snap_a: str, snap_b: str,
                    *, mapping_revision_id=None) -> dict[str, Any]:
    from .identity import resolve_identity, entities
    proof = resolve_identity(conn, plan_id, snap_a, snap_b, mapping_revision_id)
    a, b = _load_snapshot(conn, snap_a), _load_snapshot(conn, snap_b)
    task_pairs = [p for p in proof['pairs'] if p['entity_kind'] == 'task']
    changed = []
    for pair in task_pairs:
        ta, tb = a['tasks_by_key'][pair['from_key']], b['tasks_by_key'][pair['to_key']]
        fields = ('start','finish','duration','name','constraint_type','constraint_date','outline_level')
        changes = {f:{'from':ta.get(f),'to':tb.get(f)} for f in fields if ta.get(f) != tb.get(f)}
        if changes:
            changed.append({'uid':tb['uid'], 'task_key':tb['task_key'], **pair, 'changes':changes})
    unmatched = {}
    for kind in ('task','resource','calendar','assignment'):
        pairs = [p for p in proof['pairs'] if p['entity_kind']==kind]
        left, key = entities(conn,snap_a,kind)
        right, _ = entities(conn,snap_b,kind)
        unmatched[kind] = {'from':[r for r in left if r[key] not in {p['from_key'] for p in pairs}],
                           'to':[r for r in right if r[key] not in {p['to_key'] for p in pairs}]}
    # Only proven endpoints may participate in a link comparison. Full multiset
    # semantics/calendar/assignment deltas are the separate stage-11 contract.
    mapping = {p['from_key']:p['to_key'] for p in task_pairs}
    deps_a = {(mapping[d['predecessor_task_key']],mapping[d['successor_task_key']]) for d in a['dependencies']
              if d['predecessor_task_key'] in mapping and d['successor_task_key'] in mapping}
    deps_b = {(d['predecessor_task_key'],d['successor_task_key']) for d in b['dependencies']
              if d['predecessor_task_key'] in mapping.values() and d['successor_task_key'] in mapping.values()}
    root_pair = next((p for p in task_pairs if a['tasks_by_key'][p['from_key']].get('outline_level')==1
                     and b['tasks_by_key'][p['to_key']].get('outline_level')==1),None)
    ra = a['tasks_by_key'][root_pair['from_key']] if root_pair else {}
    rb = b['tasks_by_key'][root_pair['to_key']] if root_pair else {}
    delta = None
    if a['timezone_hint'] and b['timezone_hint'] and ra.get('finish') and rb.get('finish'):
        try:
            fa, fb = datetime.fromisoformat(ra['finish']), datetime.fromisoformat(rb['finish'])
            if fa.tzinfo and fb.tzinfo:
                delta = (fb-fa).total_seconds()/86400
        except ValueError:
            pass
    return {'result_class':'observed_diff', 'changed_tasks':changed,
        'root':{'finish_a':ra.get('finish'),'finish_b':rb.get('finish'),'finish_delta_calendar_days':delta},
        'links_removed':sorted(deps_a-deps_b), 'links_added':sorted(deps_b-deps_a),
        'task_uids_added':[], 'task_uids_removed':[], 'unmatched_entities':unmatched,
        'working_drift':'unavailable',
        'receipt':{'plan_id':plan_id,'representation':a['representation'],'snapshot_a':snap_a,'snapshot_b':snap_b,
            'mapping':proof['mapping'],'mapping_revision_id':proof['mapping_revision_id'],
            'evidence_id':proof['evidence_id'],'evidence_sha256':proof['evidence_sha256'],
            'identity_scope':proof['scope'],'confirmed_pairs':proof['pairs'],
            'calendar':'unknown','timezone':a['timezone_hint'] if a['timezone_hint']==b['timezone_hint'] else None,
            'completeness':'partial','limitations':['full_semantic_diff_pending_stage_11'], 'known_at':_now()}}


# ─────────────────────────────────────────────────────────────────────────
# task_history (P3.RAG.3, R-023/R-036, AC-125)
# ─────────────────────────────────────────────────────────────────────────


def task_history(conn: sqlite3.Connection, plan_id: str, uid: str, *,
                 from_snapshot_id=None, to_snapshot_id=None, mapping_revision_id=None) -> dict[str, Any]:
    """UID is a local lookup. History joins only directly proven snapshot pairs."""
    from .identity import resolve_identity, snapshot, records, IdentityError
    rows = records(conn, 'SELECT tv.snapshot_id,s.recorded_at,tv.task_key,tv.name,tv.start_raw AS start,'
        'tv.finish_raw AS finish,tv.duration_raw AS duration FROM plan_task_version tv '
        'JOIN plan_snapshot s ON s.snapshot_id=tv.snapshot_id WHERE tv.plan_id=? AND tv.uid=? '
        'ORDER BY s.recorded_at,s.snapshot_id,tv.task_key', (plan_id,str(uid)))
    receipt = {'plan_id':plan_id,'uid':uid,'representation':'mpp','mapping':'unknown',
               'mapping_revision_id':None,'evidence_id':None,'snapshot_count':len({r['snapshot_id'] for r in rows}),
               'completeness':'partial','known_at':_now()}
    caveat = 'Перенос задачи не доказывает перенос финала проекта; неизвестная идентичность не объединяет задачи.'
    if not rows:
        return {'result_class':'insufficient_data','reason':'task_not_found','receipt':receipt}
    if mapping_revision_id and not (from_snapshot_id and to_snapshot_id):
        raise IdentityError('exact_history_pair_required',2)
    if not from_snapshot_id:
        # There is no privileged first/last UID occurrence across independent MPP.
        return {'uid':uid,'history':rows if len(rows)==1 else [],'unmatched_tasks':rows if len(rows)>1 else [],
            'finish_delta_calendar_days':None,'caveat':caveat,'receipt':receipt}
    snapshot(conn,plan_id,from_snapshot_id)
    anchors = [r for r in rows if r['snapshot_id']==from_snapshot_id]
    if len(anchors) != 1:
        raise IdentityError('invalid_or_duplicate_uid')
    anchor = anchors[0]
    history, unmatched, proofs = [anchor], [], []
    targets = [to_snapshot_id] if to_snapshot_id else [r[0] for r in conn.execute(
        'SELECT snapshot_id FROM plan_snapshot WHERE plan_id=? AND snapshot_id<>? ORDER BY recorded_at,snapshot_id',
        (plan_id,from_snapshot_id))]
    for sid in targets:
        proof = resolve_identity(conn,plan_id,from_snapshot_id,sid,mapping_revision_id)
        pair = next((p for p in proof['pairs'] if p['entity_kind']=='task' and p['from_key']==anchor['task_key']),None)
        if not pair:
            unmatched.extend(r for r in rows if r['snapshot_id']==sid)
            continue
        matched = records(conn, 'SELECT tv.snapshot_id,s.recorded_at,tv.task_key,tv.name,tv.start_raw AS start,'
            'tv.finish_raw AS finish,tv.duration_raw AS duration FROM plan_task_version tv JOIN plan_snapshot s '
            'ON s.snapshot_id=tv.snapshot_id WHERE tv.snapshot_id=? AND tv.task_key=?', (sid,pair['to_key']))
        if sid != from_snapshot_id:
            history.extend(matched)
        proofs.append({k:v for k,v in proof.items() if k != 'pairs'})
    if proofs:
        receipt.update(mapping=proofs[0]['mapping'] if len(proofs)==1 else 'confirmed_direct_pairs',
                       mapping_revision_id=proofs[0]['mapping_revision_id'] if len(proofs)==1 else None,
                       evidence_id=proofs[0]['evidence_id'] if len(proofs)==1 else None, identity_proofs=proofs)
    return {'uid':uid,'history':history,'unmatched_tasks':unmatched,'finish_delta_calendar_days':None,
            'caveat':caveat,'receipt':receipt}


# ─────────────────────────────────────────────────────────────────────────
# compare_baseline (R-023/R-019)
# ─────────────────────────────────────────────────────────────────────────


def compare_baseline(conn: sqlite3.Connection, plan_id: str, snapshot_id: str, baseline_slot: int = 0) -> dict[str, Any]:
    """Сравнить текущие даты снимка с его собственным embedded baseline-слотом
    (0..10). Отсутствующий слот у задачи — известный пропуск, не нулевое
    отклонение (R-014)."""
    known_at = _now()
    rows = conn.execute(
        "SELECT tv.task_key, tv.name, tv.finish_raw, bv.baseline_finish "
        "FROM plan_task_version tv LEFT JOIN plan_embedded_baseline_value bv "
        "ON bv.task_version_id = tv.task_version_id AND bv.baseline_slot = ? "
        "WHERE tv.snapshot_id = ?",
        (baseline_slot, snapshot_id),
    ).fetchall()
    if not rows:
        return {
            "result_class": "insufficient_data",
            "reason": f"snapshot_id={snapshot_id} не найден или без задач",
            "receipt": {"plan_id": plan_id, "snapshot_id": snapshot_id, "known_at": known_at},
        }
    comparisons = []
    missing_baseline = 0
    for task_key, name, finish, baseline_finish in rows:
        if baseline_finish is None:
            missing_baseline += 1
            comparisons.append({"task_key": task_key, "name": name, "finish": finish,
                                 "baseline_finish": None, "status": "baseline_missing"})
            continue
        delta_days = None
        try:
            delta_days = (datetime.fromisoformat(finish) - datetime.fromisoformat(baseline_finish)).days
        except (ValueError, TypeError):
            pass
        comparisons.append({
            "task_key": task_key, "name": name, "finish": finish,
            "baseline_finish": baseline_finish, "delta_calendar_days": delta_days,
            "status": "ok",
        })
    return {
        "snapshot_id": snapshot_id,
        "baseline_slot": baseline_slot,
        "comparisons": comparisons,
        "missing_baseline_count": missing_baseline,
        "receipt": {
            "plan_id": plan_id, "snapshot_id": snapshot_id, "baseline_slot": baseline_slot,
            "completeness": "partial" if missing_baseline else "complete",
            "known_at": known_at,
        },
    }


# ─────────────────────────────────────────────────────────────────────────
# explain_finish_change (P3.RAG.8, R-026/R-035, AC-139/AC-144)
# ─────────────────────────────────────────────────────────────────────────


def explain_finish_change(
    conn: sqlite3.Connection,
    plan_id: str,
    version_a: VersionSelector,
    version_b: VersionSelector,
    *,
    target_task_key: str | None = None,
) -> dict[str, Any]:
    """Вопрос «за счёт каких работ финал ушёл».

    На паре двух MPP snapshot-ов (confirmed uid mapping, полный replay
    доступен) — вызывает ``plan_attribution``/``plan_scheduler`` (MppReader,
    через subprocess с JVM, см. ``MppReader/mpp_input.py::_pick_python``) и
    персистирует через ``writer.record_analysis_run`` → ``validated_attribution``.
    На паре Gantt-публикаций (UID недоступен, изначальный MPP не сохранён)
    возвращает честный ``observed_diff`` с явными блокерами — не выдумывает
    атрибуцию (R-035, AC-139: "Исторический вопрос про ZD v4→v5 (+14) даёт
    observed_diff с явными блокерами, не validated_attribution").
    """
    known_at = _now()
    if version_a.get("kind") != "snapshot" or version_b.get("kind") != "snapshot":
        diff = diff_versions(conn, plan_id, version_a, version_b)
        blockers = [
            "представление не MPP snapshot (нет подтверждённого mapping по uid)",
            "полный replay через MicrosoftScheduler недоступен без исходного MPP для этой пары",
        ]
        return {
            "result_class": "observed_diff",
            "delta": diff.get("root", {}),
            "blockers": blockers,
            "message": (
                "Между выбранными публикациями финал изменился "
                f"({diff.get('root', {}).get('finish_delta_calendar_days')!r} календарных суток); "
                "доказательное разложение по работам недоступно для этой пары (см. blockers)."
            ),
            "receipt": {
                "plan_id": plan_id, "version_a": version_a, "version_b": version_b,
                "completeness": "insufficient", "blockers": blockers, "known_at": known_at,
            },
        }

    # Snapshot-пара: вызов MppReader (plan_attribution.build_groups +
    # sequential_attribution/exact_shapley) через subprocess с python3.9/JVM.
    return _explain_via_mppreader(conn, plan_id, version_a["snapshot_id"], version_b["snapshot_id"], target_task_key)


def _explain_via_mppreader(
    conn: sqlite3.Connection, plan_id: str, snap_a: str, snap_b: str, target_task_key: str | None,
) -> dict[str, Any]:
    import subprocess
    import sys

    known_at = _now()
    from .identity import resolve_identity
    proof = resolve_identity(conn,plan_id,snap_a,snap_b)
    diff = _diff_snapshots(conn,plan_id,snap_a,snap_b)
    if proof['mapping']=='unknown' or any(p['from_key'] != p['to_key'] for p in proof['pairs']) or any(
            diff['unmatched_entities']['task'].values()):
        return {'result_class':'insufficient_data','blockers':['confirmed_complete_identity_required'],
                'receipt':diff['receipt']}
    a = _load_snapshot(conn, snap_a)
    b = _load_snapshot(conn, snap_b)

    tasks_a = [
        {"task_key": k, "duration_raw": v.get("duration"), "constraint_type": v.get("constraint_type")}
        for k, v in a["tasks_by_key"].items()
    ]
    tasks_b = [
        {"task_key": k, "duration_raw": v.get("duration"), "constraint_type": v.get("constraint_type")}
        for k, v in b["tasks_by_key"].items()
    ]
    payload = {
        "snapshot_a": {"tasks": tasks_a, "dependencies": a["dependencies"]},
        "snapshot_b": {"tasks": tasks_b, "dependencies": b["dependencies"]},
    }

    mppreader_root = Path.home() / "USERTOOLS" / "MppReader"
    script = mppreader_root / "plan_attribution.py"
    if not script.exists():
        blockers = ["plan_attribution.py не найден в MppReader"]
        return {
            "result_class": "insufficient_data",
            "blockers": blockers,
            "receipt": {"plan_id": plan_id, "snapshot_a": snap_a, "snapshot_b": snap_b,
                        "completeness": "insufficient", "blockers": blockers, "known_at": known_at},
        }

    code = (
        "import sys, json\n"
        f"sys.path.insert(0, {str(mppreader_root)!r})\n"
        "import plan_attribution as pa\n"
        "payload = json.load(sys.stdin)\n"
        "report = pa.build_groups(payload['snapshot_a'], payload['snapshot_b'])\n"
        "print(json.dumps({'groups': [g.group_id for g in report.groups], "
        "'categories': [g.category for g in report.groups], "
        "'uncovered': list(report.uncovered)}))\n"
    )
    try:
        proc = subprocess.run(
            [sys.executable, "-c", code],
            input=json.dumps(payload), capture_output=True, text=True, timeout=30,
        )
    except Exception as exc:  # noqa: BLE001
        blockers = [f"subprocess вызов MppReader не выполнен: {exc}"]
        return {
            "result_class": "replay_failed",
            "blockers": blockers,
            "receipt": {"plan_id": plan_id, "snapshot_a": snap_a, "snapshot_b": snap_b,
                        "completeness": "insufficient", "blockers": blockers, "known_at": known_at},
        }
    if proc.returncode != 0:
        blockers = [f"build_groups завершился с ошибкой: {proc.stderr[-500:]}"]
        return {
            "result_class": "replay_failed",
            "blockers": blockers,
            "receipt": {"plan_id": plan_id, "snapshot_a": snap_a, "snapshot_b": snap_b,
                        "completeness": "insufficient", "blockers": blockers, "known_at": known_at},
        }
    result = json.loads(proc.stdout)
    return {
        "result_class": "validated_attribution" if not result["uncovered"] else "insufficient_data",
        "groups": result["groups"],
        "categories": result["categories"],
        "uncovered": result["uncovered"],
        "receipt": {
            "plan_id": plan_id, "snapshot_a": snap_a, "snapshot_b": snap_b,
            "mapping": proof["mapping"], "mapping_revision_id": proof["mapping_revision_id"],
            "evidence_id": proof["evidence_id"], "method": "sequential+shapley (groups only, not scheduled)",
            "completeness": "complete" if not result["uncovered"] else "partial",
            "known_at": known_at,
        },
    }


# Stage 03 internal adapters consume these read APIs, never free SQL.
def _record(conn: sqlite3.Connection, table: str, key: str, value: str) -> dict[str, Any] | None:
    cursor = conn.execute(f"SELECT * FROM {table} WHERE {key}=?", (value,))
    row = cursor.fetchone()
    return dict(zip((c[0] for c in cursor.description), row)) if row else None


def get_operation(conn: sqlite3.Connection, operation_id: str) -> dict[str, Any] | None:
    return _record(conn,"plan_operation","operation_id",operation_id)


def get_import_item(conn: sqlite3.Connection, item_id: str) -> dict[str, Any] | None:
    return _record(conn,"plan_import_item","item_id",item_id)


def get_operation_item(conn: sqlite3.Connection, operation_id: str) -> dict[str, Any] | None:
    return _record(conn,"plan_import_item","operation_id",operation_id)


def get_import_batch(conn: sqlite3.Connection, batch_id: str) -> dict[str, Any] | None:
    return _record(conn,"plan_import_batch","batch_id",batch_id)


def get_snapshot(conn: sqlite3.Connection, snapshot_id: str) -> dict[str, Any] | None:
    return _record(conn,"plan_snapshot","snapshot_id",snapshot_id)


def find_snapshot_by_dedup_key(conn: sqlite3.Connection, dedup_key: str) -> dict[str, Any] | None:
    return _record(conn,"plan_snapshot","dedup_key",dedup_key)


def get_artifact(conn: sqlite3.Connection, artifact_id: str) -> dict[str, Any] | None:
    return _record(conn,"plan_artifact","artifact_id",artifact_id)


def find_artifact_by_hash(conn: sqlite3.Connection, sha256: str) -> dict[str, Any] | None:
    return _record(conn,"plan_artifact","raw_sha256",sha256)


def get_lineage(conn: sqlite3.Connection, lineage_id: str) -> dict[str, Any] | None:
    return _record(conn,"plan_lineage","lineage_id",lineage_id)


def get_attempt(conn: sqlite3.Connection, attempt_id: str) -> dict[str, Any] | None:
    return _record(conn,"plan_import_attempt","attempt_id",attempt_id)


def get_operation_events(conn: sqlite3.Connection, operation_id: str) -> list[dict[str, Any]]:
    cursor = conn.execute("SELECT e.* FROM plan_attempt_event e JOIN plan_import_attempt a USING(attempt_id) "
                          "WHERE a.operation_id=? ORDER BY e.created_at,e.rowid",(operation_id,))
    names = [c[0] for c in cursor.description]
    return [dict(zip(names,row)) for row in cursor]


def get_committed_import(conn: sqlite3.Connection, item_id: str) -> dict[str, Any] | None:
    item = get_import_item(conn,item_id)
    if not item or not item["snapshot_id"]:
        return None
    event = conn.execute("SELECT snapshot_id FROM plan_attempt_event WHERE event_id=? AND event_kind='snapshot_committed'",
                         ("snapshot_committed:"+item_id,)).fetchone()
    if not event or event[0] != item["snapshot_id"]:
        raise PlanQueryError("committed_import_inconsistent")
    return {"item": item, "snapshot": get_snapshot(conn,item["snapshot_id"])}


def page_bindings(conn: sqlite3.Connection, page_id: str, namespace: str) -> list[dict[str, Any]]:
    cursor = conn.execute("SELECT l.lineage_id,l.plan_id,p.project_slug FROM plan_lineage l JOIN plan p USING(plan_id) "
                          "WHERE l.page_id=? AND l.source_namespace=?",(page_id,namespace))
    return [dict(zip(("lineage_id","plan_id","project_slug"),row)) for row in cursor]


def get_batch_items(conn: sqlite3.Connection, batch_id: str) -> list[dict[str, Any]]:
    """One ordered read; external item IDs are scoped by their owning batch."""
    cursor = conn.execute("SELECT * FROM plan_import_item WHERE batch_id=? ORDER BY ordinal", (batch_id,))
    names = [column[0] for column in cursor.description]
    return [dict(zip(names, row)) for row in cursor]


def get_batch_item_result(conn: sqlite3.Connection, operation_id: str) -> dict[str, Any] | None:
    for event in reversed(get_operation_events(conn, operation_id)):
        if event["event_kind"] == "batch_item_result":
            return json.loads(event["detail"])
    return None


def get_operation_attempts(conn: sqlite3.Connection, operation_id: str) -> list[dict[str, Any]]:
    cursor = conn.execute("SELECT * FROM plan_import_attempt WHERE operation_id=? ORDER BY created_at,rowid", (operation_id,))
    names = [column[0] for column in cursor.description]
    return [dict(zip(names, row)) for row in cursor]


def read_batch_state(conn: sqlite3.Connection, batch_id: str) -> dict[str, Any]:
    """Coherent read-only projection while a separate process changes results."""
    if conn.in_transaction:
        raise PlanQueryError("caller_transaction_forbidden")
    conn.execute("BEGIN")
    try:
        batch = get_import_batch(conn, batch_id)
        if batch is None:
            raise PlanQueryError("batch_not_found")
        items = get_batch_items(conn, batch_id)
        return {"batch": batch, "items": items,
                "results": {item["operation_id"]: get_batch_item_result(conn, item["operation_id"]) for item in items}}
    finally:
        conn.execute("ROLLBACK")


# Stage 06. These projections are shared by the CLI and typed writer guards.
BATCH_REASONS = ('archive_project_confirmation_required', 'archive_lineage_confirmation_required')


def _records(conn, sql, args=()):
    cursor = conn.execute(sql, args)
    names = [column[0] for column in cursor.description]
    return [dict(zip(names, row)) for row in cursor]


def get_source_provenance(conn, source_mpp_sha256):
    return _records(conn, 'SELECT * FROM plan_provenance WHERE source_mpp_sha256=? ORDER BY evidence_id', (source_mpp_sha256,))


def get_batch_proposals(conn, operation_id):
    rows = _records(conn, 'SELECT * FROM plan_batch_proposal WHERE operation_id=? ORDER BY rowid', (operation_id,))
    return [{**row, 'content': json.loads(row['content_json'])} for row in rows]


def get_batch_decisions(conn, operation_id):
    rows = _records(conn, 'SELECT d.* FROM plan_batch_decision d JOIN plan_batch_proposal p USING(proposal_id) '
                    'WHERE p.operation_id=? ORDER BY d.rowid', (operation_id,))
    return [{**row, 'content': json.loads(row['decision_json'])} for row in rows]


def batch_proposal_contents(conn, operation_id):
    """Recompute exact current grounds without changing any record.

    No proposal is inferred from missing mapping/timezone/history or new bytes.
    Confirmed contradictions cannot be waived by an archive-placement approval.
    """
    import hashlib
    from .writer import _json, normalize_timezone
    item = get_operation_item(conn, operation_id)
    operation = get_operation(conn, operation_id)
    if not item or not item['batch_id']:
        raise PlanQueryError('batch_context_immutable')
    batch = get_import_batch(conn, item['batch_id'])
    context = json.loads(operation['context_json'])
    save = context['save']
    project, lineage = save['project_slug'], save['lineage_id']
    plan = conn.execute('SELECT plan_id FROM plan WHERE project_slug=?', (project,)).fetchone()
    line = get_lineage(conn, lineage)
    if not plan or not line or line['plan_id'] != plan[0]:
        raise PlanQueryError('binding_conflict')
    if hashlib.sha256(_json(json.loads(batch['manifest_json'])).encode()).hexdigest() != batch['manifest_sha256']:
        raise PlanQueryError('proposal_context_mismatch')
    evidence = get_source_provenance(conn, item['source_mpp_sha256'])
    conflicts = [row for row in evidence if row['project_slug'] != project or
                 (row['lineage_id'] is not None and row['lineage_id'] != lineage)]
    if any(row['quality'] == 'confirmed' for row in conflicts):
        raise PlanQueryError('binding_conflict')
    fingerprint = hashlib.sha256(_json([context, json.loads(batch['context_json'])]).encode()).hexdigest()
    policy = {'version': 'archive-placement-v1', 'on_error': batch['on_error']}
    base = {'batch_id': item['batch_id'], 'item_id': item['item_id'], 'operation_id': operation_id,
            'manifest_sha256': batch['manifest_sha256'], 'source_mpp_sha256': item['source_mpp_sha256'],
            'context_sha256': fingerprint, 'project_slug': project, 'lineage_id': lineage,
            'normalization_profile': context['profiles']['NORMALIZATION_PROFILE'],
            'resolved_timezone': normalize_timezone(save.get('timezone_hint')), 'source_version_date': item['source_version_date'],
            'policy': policy, 'policy_sha256': hashlib.sha256(_json(policy).encode()).hexdigest(),
            'context_unchanged': True, 'rule_scope': 'once',
            'all_contradicting_evidence': [{'evidence_id': row['evidence_id'], 'sha256': row['evidence_sha256'],
                'quality': row['quality']} for row in conflicts]}
    result = []
    for reason in BATCH_REASONS:
        matching = [row for row in conflicts if (row['project_slug'] != project if reason == BATCH_REASONS[0]
                    else row['project_slug'] == project and row['lineage_id'] != lineage)]
        if matching:
            result.append({**base, 'reason_code': reason,
                'type': 'confirm_archive_project' if reason == BATCH_REASONS[0] else 'confirm_archive_lineage',
                'evidence': matching, 'action': 'Archive in the frozen project and lineage; no UID continuity confirmation',
                'consequences': 'Only archive placement is approved; source and batch context remain unchanged'})
    return result


def batch_decision_state(conn, operation_id):
    import hashlib
    from .writer import _json
    contents = batch_proposal_contents(conn, operation_id)
    current = {hashlib.sha256(_json(content).encode()).hexdigest() for content in contents}
    proposals = [{**row, 'active': row['proposal_sha256'] in current} for row in get_batch_proposals(conn, operation_id)]
    decisions = get_batch_decisions(conn, operation_id)
    accepted = {row['proposal_id'] for row in decisions}
    active = [row for row in proposals if row['active']]
    closed = {row['reason_code'] for row in active if row['proposal_id'] in accepted}
    reasons = [content['reason_code'] for content in contents]
    missing = [reason for reason in reasons if reason not in closed]
    materialized = {row['proposal_sha256'] for row in active} == current
    return {'proposals': proposals, 'decisions': decisions, 'reasons': reasons,
            'unresolved_reasons': missing, 'decision_ready': bool(current) and materialized and not missing}


def get_identity_revision(conn, project_slug, mapping_revision_id):
    from .identity import show_revision
    return show_revision(conn, project_slug, mapping_revision_id)


def get_identity_requirements(conn, operation_id):
    from .identity import operation_requirements
    return operation_requirements(conn, operation_id)


# Stage 09: typed preparation/rule/decision reads shared by CLI and pipeline.
def get_preparation(conn, operation_id, revision=None):
    if revision is None:
        operation = get_operation(conn,operation_id)
        revision = operation['preparation_revision'] if operation else 0
    rows = _records(conn,'SELECT * FROM plan_preparation WHERE operation_id=? AND revision=?',(operation_id,revision))
    if not rows:
        return None
    row = rows[0]
    row['context'] = json.loads(row.pop('context_json'))
    row['request'] = json.loads(row.pop('request_json'))
    return row


def get_preparation_history(conn, operation_id):
    return [get_preparation(conn,operation_id,row['revision']) for row in
        _records(conn,'SELECT revision FROM plan_preparation WHERE operation_id=? ORDER BY revision',(operation_id,))]


def get_project_rules(conn, project_slug):
    rows = _records(conn,'SELECT r.* FROM plan_project_rule r JOIN plan p ON p.plan_id=r.plan_id '
        'WHERE p.project_slug=? ORDER BY r.rule_id,r.rowid',(project_slug,))
    for row in rows:
        row['content'] = json.loads(row.pop('content_json'))
        row['project_slug'] = project_slug
    # Rule revisions are explicit; no lexicographic version ordering.
    return rows


def get_preparation_result(conn, operation_id, revision=None):
    prep = get_preparation(conn,operation_id,revision)
    if not prep:
        return None
    rows = _records(conn,'SELECT * FROM plan_preparation_result WHERE operation_id=? AND preparation_revision=? '
        'ORDER BY rowid DESC LIMIT 1',(operation_id,prep['revision']))
    if not rows:
        return None
    row = rows[0]
    row['admission'] = json.loads(row.pop('admission_json'))
    row['result'] = json.loads(row.pop('result_json'))
    return row


def get_publish_proposals(conn, operation_id, revision=None):
    prep = get_preparation(conn,operation_id,revision)
    if not prep:
        return []
    rows = _records(conn,'SELECT p.*,d.decision_id,d.rule_scope,d.reason decision_reason,d.created_at decision_created_at '
        'FROM plan_publish_proposal p LEFT JOIN plan_publish_decision d ON d.proposal_id=p.proposal_id '
        'WHERE p.operation_id=? AND p.preparation_revision=? ORDER BY p.rowid',(operation_id,prep['revision']))
    for row in rows:
        row['content'] = json.loads(row.pop('content_json'))
    return rows


def publish_external_effect(conn, operation_id):
    for event in get_operation_events(conn,operation_id):
        if event['event_kind']=='publish_network_intent':return True
        if event['event_kind']=='publish_network_result' and json.loads(event['detail']).get('external_effect')!='none':return True
    return False
