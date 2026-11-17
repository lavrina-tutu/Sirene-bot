"""Typed query API для архива слепков плана (P3.RAG.1-8, R-023/R-026/R-027).

Публичные функции принимают параметры из R-026 (plan/project_slug,
конкретные версии/snapshot_id, representation) — не свободный SQL от
вызывающей стороны (LLM/workvault-rag). Каждая функция возвращает typed dict
с обязательным полем ``receipt`` (R-026: план/линия, A/B, representation,
mapping, baseline, target, календарь, completeness, hashes, known_at).

Две "версии" плана в этом архиве — разные представления с разным
идентификатором:
  * Confluence-публикация Gantt JSON — ``{"kind": "publication",
    "publication_id": "..."}`` (плотная история v1..v6 ZD, только Gantt-id,
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
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .selectors import PlanQueryError

VersionSelector = dict[str, Any]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


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


def publication_observations(conn, publication_id, *, watermark=None):
    sql = ('SELECT o.*,l.link_revision_id,l.link_kind,l.confidence,l.evidence FROM plan_publication_page_link l '
           'JOIN plan_page_observation o USING(observation_id) WHERE l.publication_id=?')
    args = [publication_id]
    if watermark is not None:
        sql += ' AND l.rowid<=?'
        args.append(watermark)
    rows = _records(conn, sql + ' ORDER BY l.rowid', args)
    for row in rows:
        row['verified_at'] = row['fetched_at']
        row['verification'] = json.loads(row.pop('verification_json') or '{}')
    return rows


def list_versions(conn, plan_id):
    versions = []
    for row in _records(conn, 'SELECT * FROM plan_publication WHERE plan_id=? ORDER BY recorded_at,publication_id', (plan_id,)):
        # Listing remains possible for incomplete legacy records.
        links = _records(conn, 'SELECT * FROM plan_publication_snapshot WHERE publication_id=? ORDER BY rowid', (row['publication_id'],))
        versions.append({**row, 'kind': 'publication', 'representation': 'gantt_json',
            'publication_verified': row['trust'] == 'verified_v1', 'snapshot_links': links,
            'observations': publication_observations(conn, row['publication_id'])})
    for row in _records(conn, 'SELECT * FROM plan_snapshot WHERE plan_id=? ORDER BY recorded_at,snapshot_id', (plan_id,)):
        row.pop('source_json', None)
        row['publication_links'] = _records(conn, 'SELECT l.*,p.trust,p.page_id,p.attachment_id,p.attachment_version '
            'FROM plan_publication_snapshot l JOIN plan_publication p USING(publication_id) WHERE snapshot_id=?', (row['snapshot_id'],))
        versions.append({**row, 'kind': 'snapshot'})
    return {'plan_id': plan_id, 'versions': versions, 'receipt': {'plan_id': plan_id,
        'publication_count': sum(v['kind']=='publication' for v in versions),
        'snapshot_count': sum(v['kind']=='snapshot' for v in versions), 'known_at': _now()}}


def _load_publication(conn, plan_id, publication_id):
    from .selectors import resolve_selector
    import hashlib
    row = resolve_selector(conn, plan_id, {'kind':'publication', 'publication_id':publication_id})
    row.update(body=None, artifact_quality='unavailable', publication_verified=row['trust']=='verified_v1')
    artifact = get_artifact(conn, row['artifact_id']) if row['artifact_id'] else None
    if artifact:
        try:
            raw = Path(artifact['path']).read_bytes()
            if hashlib.sha256(raw).hexdigest() == artifact['raw_sha256'] == row['raw_sha256']:
                row['body'] = json.loads(raw)
                row['artifact_quality'] = 'verified_bytes'
            else:
                row['artifact_quality'] = 'hash_mismatch'
        except (OSError, ValueError):
            pass
    return row


def _clean(row):
    metadata = {'snapshot_id','plan_id','recorded_at','task_version_id','dependency_version_id',
        'resource_version_id','assignment_version_id','calendar_version_id','segment_id','availability_id',
        'interval_id','timephased_id','baseline_value_id','external_dependency_id'}
    result = {k:v for k,v in row.items() if k not in metadata}
    for key in ('source_json','extensions'):
        if isinstance(result.get(key), str):
            try:
                result[key] = json.loads(result[key])
            except ValueError:
                pass
    return result


def _load_snapshot(conn, snapshot_id, plan_id=None):
    from .selectors import resolve_selector
    meta = get_snapshot(conn, snapshot_id)
    if not meta:
        raise PlanQueryError('snapshot_not_found')
    meta = resolve_selector(conn, plan_id or meta['plan_id'], {'kind':'snapshot','snapshot_id':snapshot_id})
    groups = {}
    children = {'task': [('segments','plan_task_segment','task_version_id'),
                         ('baseline_values','plan_embedded_baseline_value','task_version_id')],
                'resource':[('availability','plan_resource_availability','resource_version_id')],
                'assignment':[('timephased','plan_assignment_timephased','assignment_version_id')],
                'calendar':[('intervals','plan_calendar_interval','calendar_version_id')]}
    for kind in ('task','resource','calendar','assignment','dependency'):
        rows = _records(conn, 'SELECT * FROM plan_'+kind+'_version WHERE snapshot_id=? ORDER BY rowid', (snapshot_id,))
        for row in rows:
            for name, table, fk in children.get(kind, []):
                row[name] = [_clean(r) for r in _records(conn, 'SELECT * FROM '+table+' WHERE '+fk+'=? ORDER BY rowid', (row[fk],))]
                row[name].sort(key=_canonical)
        groups[kind] = [_clean(r) for r in rows]
    meta['entities'] = groups
    meta['tasks_by_key'] = {r['task_key']:r for r in groups['task']}
    # No lossy by-UID index: duplicated UIDs remain independent records.
    meta['dependencies'] = groups['dependency']
    meta['external_dependencies'] = [_clean(r) for r in _records(conn,'SELECT * FROM plan_external_dependency WHERE snapshot_id=?', (snapshot_id,))]
    meta['collections'] = _records(conn, 'SELECT * FROM plan_snapshot_collection WHERE snapshot_id=?', (snapshot_id,))
    meta['quality_issues'] = _records(conn, 'SELECT * FROM plan_quality_issue WHERE snapshot_id=?', (snapshot_id,))
    meta['source'] = json.loads(meta['source_json']) if meta['source_json'] else {}
    return meta


def _canonical(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',',':'))


def _quality(snapshot):
    required = {'tasks','dependencies','resources','assignments','calendars','external_dependencies'}
    states = {r['collection_kind']:r['status'] for r in snapshot['collections']}
    def incomplete(value):
        if isinstance(value, dict):
            if 'quality' in value and value['quality'] not in ('complete','known','ok'):
                return True
            return any(incomplete(v) for v in value.values())
        return isinstance(value,list) and any(incomplete(v) for v in value)
    complete = (required <= states.keys() and all(states[k]=='complete' for k in required)
        and bool(snapshot['source']) and not incomplete(snapshot['source']) and not snapshot['quality_issues']
        and all(row.get('quality')=='complete' for row in snapshot['entities']['task'])
        and all(row.get('source_json') is not None for kind in ('calendar','resource','assignment','dependency')
                for row in snapshot['entities'][kind]))
    return {'collections':states, 'completeness':'complete' if complete else 'partial',
        'calendar':'known' if complete and snapshot['entities']['calendar'] else 'unknown'}


def _absolute_delta(a, b, zone_a, zone_b):
    # Date-only and unknown zones have no absolute instant. Keep raw values.
    if not zone_a or not zone_b or zone_a=='unknown' or zone_b=='unknown' or not a or not b or 'T' not in a or 'T' not in b:
        return None
    from zoneinfo import ZoneInfo
    try:
        left, right = (datetime.fromisoformat(v.replace('Z','+00:00')) for v in (a,b))
        if left.tzinfo is None:
            left = left.replace(tzinfo=ZoneInfo(zone_a))
            if left.fold == 0 and left.utcoffset() != left.replace(fold=1).utcoffset():
                return None
        if right.tzinfo is None:
            right = right.replace(tzinfo=ZoneInfo(zone_b))
            if right.fold == 0 and right.utcoffset() != right.replace(fold=1).utcoffset():
                return None
        return (right.astimezone(timezone.utc)-left.astimezone(timezone.utc)).total_seconds()
    except (ValueError, TypeError, KeyError):
        return None


def diff_versions(conn, plan_id, version_a, version_b, *, mapping_revision_id=None):
    from .selectors import resolve_pair
    a,b = resolve_pair(conn, plan_id, version_a, version_b)
    kinds = (version_a['kind'],version_b['kind'])
    if kinds == ('snapshot','snapshot'):
        result = _diff_snapshots(conn,plan_id,a['snapshot_id'],b['snapshot_id'],mapping_revision_id=mapping_revision_id)
    elif kinds == ('publication','publication'):
        result = _diff_publications(conn,plan_id,a['publication_id'],b['publication_id'],
            mapping_revision_id=mapping_revision_id, selections=(a,b))
    else:
        pub = a if kinds[0]=='publication' else b
        snap = b if kinds[0]=='publication' else a
        linked = get_snapshot(conn,pub['snapshot_id']) if pub['snapshot_id'] else None
        archive = _load_publication(conn,plan_id,pub['publication_id'])
        if not linked or linked['representation'] != 'gantt_json' or archive['artifact_quality']!='verified_bytes':
            result = {'result_class':'representation_mismatch','exit_code':4,
                'reason':'confirmed_gantt_snapshot_and_mapping_required','receipt':{'mapping':'unknown','known_at':_now()}}
        else:
            sa,sb = (linked['snapshot_id'],snap['snapshot_id']) if kinds[0]=='publication' else (snap['snapshot_id'],linked['snapshot_id'])
            result = _diff_snapshots(conn,plan_id,sa,sb,mapping_revision_id=mapping_revision_id)
    result.setdefault('exit_code',0)
    result.setdefault('receipt',{}).update(plan_id=plan_id,version_a=a['selector'],version_b=b['selector'])
    return result


def _diff_publications(conn, plan_id, publication_a, publication_b, *, mapping_revision_id=None, selections=None):
    from .selectors import resolve_pair
    resolve_pair(conn,plan_id,{'kind':'publication','publication_id':publication_a},
                 {'kind':'publication','publication_id':publication_b})
    a,b = (_load_publication(conn,plan_id,p) for p in (publication_a,publication_b))
    if selections:
        for loaded,selected in zip((a,b),selections):
            loaded.update({k:selected[k] for k in ('snapshot_id','snapshot_links','snapshot_link_quality','selector')})
    # A source MPP link proves source provenance, not identity of positional Gantt IDs.
    matching = all(p['artifact_quality']=='verified_bytes' and p['snapshot_id']
        and get_snapshot(conn,p['snapshot_id'])['representation']=='gantt_json' for p in (a,b))
    if matching:
        result = _diff_snapshots(conn,plan_id,a['snapshot_id'],b['snapshot_id'],mapping_revision_id=mapping_revision_id)
    else:
        if mapping_revision_id:
            raise PlanQueryError('publication_mapping_scope_unproven')
        result = {'result_class':'observed_diff','changed_tasks':[],'links_added':[],'links_removed':[],
            'unmatched_entities':{},'root':{'finish_delta_calendar_days':None},
            'receipt':{'mapping':'unknown','mapping_revision_id':None,'completeness':'partial','calendar':'unknown','known_at':_now()}}
    result['content_identical'] = bool(a['body'] is not None and b['body'] is not None and a['raw_sha256']==b['raw_sha256'])
    result['publications'] = {'from':{k:v for k,v in a.items() if k!='body'},'to':{k:v for k,v in b.items() if k!='body'}}
    collection_fields = {'eventsData','dependenciesData','resourcesData','calendarsData','assignmentsData'}
    result['representation_fields'] = {side:{k:v for k,v in (p['body'] or {}).items() if k not in collection_fields}
        for side,p in (('from',a),('to',b)) if isinstance(p['body'],dict)}
    if not matching:
        def structure(body):
            body = body if isinstance(body,dict) else {}
            tasks = []
            def walk(nodes):
                for node in nodes:
                    tasks.append({k:v for k,v in node.items() if k!='children'})
                    walk(node.get('children',[]))
            walk(body.get('eventsData',[]))
            return {'task':tasks,'resource':body.get('resourcesData',[]),
                'calendar':body.get('calendarsData',[]),'assignment':body.get('assignmentsData',[]),
                'dependency':body.get('dependenciesData',[])}
        left,right = structure(a['body']),structure(b['body'])
        result['unmatched_entities'] = {kind:{'from':left[kind],'to':right[kind]} for kind in left}
    result['receipt'].update(representation='gantt_json',publication_a=publication_a,publication_b=publication_b,
        hash_a=a['raw_sha256'],hash_b=b['raw_sha256'],trust_a=a['trust'],trust_b=b['trust'],
        publication_verified=a['publication_verified'] and b['publication_verified'],
        link_quality_a=a['snapshot_link_quality'],link_quality_b=b['snapshot_link_quality'],
        comparison_scope='linked_gantt_snapshots' if matching else 'unmatched_publication_structures')
    return result


def _diff_snapshots(conn, plan_id, snap_a, snap_b, *, mapping_revision_id=None):
    from .identity import resolve_identity
    from .selectors import resolve_pair
    resolve_pair(conn,plan_id,{'kind':'snapshot','snapshot_id':snap_a},{'kind':'snapshot','snapshot_id':snap_b})
    a,b = _load_snapshot(conn,snap_a,plan_id),_load_snapshot(conn,snap_b,plan_id)
    proof = resolve_identity(conn,plan_id,snap_a,snap_b,mapping_revision_id)
    if a['representation'] != b['representation'] and proof['mapping'] not in ('confirmed_mapping',):
        return {'result_class':'representation_mismatch','exit_code':4,'receipt':{'mapping':proof['mapping'],'known_at':_now()}}
    maps = {kind:{p['from_key']:p['to_key'] for p in proof['pairs'] if p['entity_kind']==kind}
            for kind in ('task','resource','calendar','assignment')}
    references = {'parent_task_key':'task','task_key':'task','local_task_key':'task',
        'predecessor_task_key':'task','successor_task_key':'task','resource_key':'resource',
        'calendar_key':'calendar','effective_calendar_key':'calendar','base_calendar_key':'calendar','parent_key':'calendar',
        'default_calendar_key':'calendar','project_calendar_key':'calendar'}
    def translated(row, side, *, own=None):
        row = dict(row)
        for key,kind in references.items():
            if key==own or row.get(key) is None:
                continue
            value = row[key]
            if side=='from':
                row[key] = {'mapped':maps[kind][value]} if value in maps[kind] else {'unmatched_from':value}
            else:
                row[key] = {'mapped':value} if value in maps[kind].values() else {'unmatched_to':value}
        return row
    changed, unmatched = {}, {}
    for kind,mapping in maps.items():
        key = kind+'_key'
        left,right = a['entities'][kind],b['entities'][kind]
        indexed_a = {r.get(key):r for r in left if r.get(key)}
        indexed_b = {r.get(key):r for r in right if r.get(key)}
        changed[kind] = []
        for ka,kb in sorted(mapping.items()):
            ta,tb = translated(indexed_a[ka],'from',own=key),translated(indexed_b[kb],'to',own=key)
            fields = (set(ta)|set(tb))-{key}
            changes = {f:{'from':ta.get(f),'to':tb.get(f)} for f in sorted(fields) if ta.get(f)!=tb.get(f)}
            if changes:
                changed[kind].append({'from_key':ka,'to_key':kb,'task_key':kb if kind=='task' else None,
                    'uid':tb.get('uid'),'changes':changes})
        unmatched[kind] = {'from':[r for r in left if r.get(key) not in mapping],
                           'to':[r for r in right if r.get(key) not in mapping.values()]}
    from collections import Counter
    def dep_partition(snapshot, side):
        matched,rest = [],[]
        keys = maps['task'] if side=='from' else set(maps['task'].values())
        for d in snapshot['dependencies']:
            if all(d[k] in keys for k in ('predecessor_task_key','successor_task_key')):
                # Local dependency keys and raw positional source JSON are provenance,
                # not cross-snapshot identity. Every semantic column is retained.
                rec = {k:v for k,v in translated(d,side).items() if k not in ('dependency_key','source_json')}
                # Source endpoint IDs/UIDs are redundant local references, not
                # relation changes after the endpoints have been mapped.
                local_identifiers = {'dependency_key','uid','predecessor_id','successor_id',
                                     'predecessor_uid','successor_uid'}
                def source(value):
                    if isinstance(value,list):
                        return [source(v) for v in value]
                    if not isinstance(value,dict):
                        return value
                    value = {k:source(v) for k,v in value.items() if k not in local_identifiers}
                    for field,kind in references.items():
                        if field in value and value[field] is not None:
                            wrapped = isinstance(value[field],dict) and 'value' in value[field]
                            raw = value[field]['value'] if wrapped else value[field]
                            if isinstance(raw,str):
                                mapped = translated({field:raw},side)[field]
                                value[field] = {**value[field],'value':mapped} if wrapped else mapped
                    return value
                rec['source_json'] = source(d.get('source_json'))
                matched.append(rec)
            else:
                rest.append(d)
        return Counter(_canonical(d) for d in matched),rest
    da,ua = dep_partition(a,'from');db,ub = dep_partition(b,'to')
    unmatched['dependency'] = {'from':ua,'to':ub}
    decode = lambda counter:[json.loads(rec) for rec in sorted(counter) for _ in range(counter[rec])]
    # External records remain visible and do not become proven removals/additions.
    unmatched['external_dependency'] = {'from':a['external_dependencies'],'to':b['external_dependencies']}
    root_pairs = [(a['tasks_by_key'][ka],b['tasks_by_key'][kb]) for ka,kb in maps['task'].items()
        if a['tasks_by_key'][ka].get('outline_level')==1 and b['tasks_by_key'][kb].get('outline_level')==1]
    ra,rb = root_pairs[0] if len(root_pairs)==1 else ({},{})
    za,zb = a['resolved_timezone'] or a['timezone_hint'], b['resolved_timezone'] or b['timezone_hint']
    seconds = _absolute_delta(ra.get('finish_raw'),rb.get('finish_raw'),za,zb)
    qa,qb = _quality(a),_quality(b)
    def project(snapshot, side):
        value = dict(snapshot['source'].get('project',{}))
        for key in ('default_calendar_key','project_calendar_key'):
            if key in value:
                wrapped = isinstance(value[key],dict) and 'value' in value[key]
                raw = value[key]['value'] if wrapped else value[key]
                mapped = translated({key:raw},side)[key]
                value[key] = {**value[key],'value':mapped} if wrapped else mapped
        return value
    project_a,project_b = project(a,'from'),project(b,'to')
    project_changes = {k:{'from':project_a.get(k),'to':project_b.get(k)} for k in sorted(set(project_a)|set(project_b)) if project_a.get(k)!=project_b.get(k)}
    return {'result_class':'observed_diff','changed_tasks':changed['task'],'changed_resources':changed['resource'],
        'changed_calendars':changed['calendar'],'changed_assignments':changed['assignment'],'project_changes':project_changes,
        'root':{'finish_a':ra.get('finish_raw'),'finish_b':rb.get('finish_raw'),'finish_delta_seconds':seconds,
                'finish_delta_calendar_days':None if seconds is None else seconds/86400},
        'links_removed':decode(da-db),'links_added':decode(db-da),
        'task_uids_added':[],'task_uids_removed':[],'unmatched_entities':unmatched,'working_drift':'unavailable',
        'receipt':{'plan_id':plan_id,'snapshot_a':snap_a,'snapshot_b':snap_b,'representation':a['representation'],
            'representations':[a['representation'],b['representation']],
            **{k:proof[k] for k in ('mapping','mapping_revision_id','evidence_id','evidence_sha256')},
            'identity_scope':proof['scope'],'confirmed_pairs':proof['pairs'],'quality_a':qa,'quality_b':qb,
            'calendar':'known' if qa['calendar']==qb['calendar']=='known' else 'unknown',
            'timezone':za if za==zb else None,'time_precision':'raw values retained; absolute deltas in seconds; no date-only/unknown-zone delta',
            'completeness':'complete' if qa['completeness']==qb['completeness']=='complete' and not any(any(v.values()) for v in unmatched.values()) else 'partial',
            'limitations':['working_time_drift_and_causal_attribution_not_calculated'],'known_at':_now()}}


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
    for sid in (from_snapshot_id, to_snapshot_id):
        if sid:
            snapshot(conn,plan_id,sid)
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
    snap = _load_snapshot(conn, snapshot_id, plan_id)
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
            seconds = _absolute_delta(baseline_finish, finish, snap["resolved_timezone"] or snap["timezone_hint"], snap["resolved_timezone"] or snap["timezone_hint"])
            delta_days = None if seconds is None else seconds / 86400
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
            "completeness": "partial" if missing_baseline or any(r.get('delta_calendar_days') is None for r in comparisons) else "complete",
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
    mapping_revision_id: str | None = None,
) -> dict[str, Any]:
    """Observed change groups only. Identity proof never establishes causality.

    build_groups does not schedule or replay the project; no query in this
    path claims validated_attribution. Publication selectors remain exact.
    """
    known_at = _now()
    if version_a.get("kind") != "snapshot" or version_b.get("kind") != "snapshot":
        diff = diff_versions(conn, plan_id, version_a, version_b, mapping_revision_id=mapping_revision_id)
        if diff.get('result_class') == 'representation_mismatch':
            return diff
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
    return _explain_via_mppreader(conn, plan_id, version_a["snapshot_id"], version_b["snapshot_id"], target_task_key, mapping_revision_id)


def _explain_via_mppreader(
    conn: sqlite3.Connection, plan_id: str, snap_a: str, snap_b: str, target_task_key: str | None, mapping_revision_id=None,
) -> dict[str, Any]:
    import subprocess
    import sys

    known_at = _now()
    from .identity import resolve_identity
    proof = resolve_identity(conn,plan_id,snap_a,snap_b,mapping_revision_id)
    diff = _diff_snapshots(conn,plan_id,snap_a,snap_b,mapping_revision_id=mapping_revision_id)
    if diff.get('result_class')=='representation_mismatch':
        return diff
    if proof['mapping']=='unknown' or any(p['from_key'] != p['to_key'] for p in proof['pairs']) or any(
            diff['unmatched_entities']['task'].values()):
        return {'result_class':'insufficient_data','blockers':['confirmed_complete_identity_required'],
                'receipt':diff['receipt']}
    a = _load_snapshot(conn, snap_a)
    b = _load_snapshot(conn, snap_b)

    tasks_a = [
        {"task_key": k, "duration_raw": v.get("duration_raw"), "constraint_type": v.get("constraint_type")}
        for k, v in a["tasks_by_key"].items()
    ]
    tasks_b = [
        {"task_key": k, "duration_raw": v.get("duration_raw"), "constraint_type": v.get("constraint_type")}
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
        "result_class": "observed_diff" if not result["uncovered"] else "insufficient_data",
        "causality": "not_established", "blockers": ["change_groups_are_not_schedule_replay"],
        "groups": result["groups"],
        "categories": result["categories"],
        "uncovered": result["uncovered"],
        "receipt": {
            "plan_id": plan_id, "snapshot_a": snap_a, "snapshot_b": snap_b,
            "mapping": proof["mapping"], "mapping_revision_id": proof["mapping_revision_id"],
            "evidence_id": proof["evidence_id"], "method": "sequential+shapley (groups only, not scheduled)",
            "completeness": "partial",
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


def get_publish_confirmation(conn, operation_id):
    rows = _records(conn, 'SELECT * FROM plan_publish_confirmation WHERE operation_id=?', (operation_id,))
    if not rows:
        return None
    row = rows[0]
    row['receipt'] = json.loads(row.pop('receipt_json'))
    row['schedule'] = json.loads(row.pop('schedule_json'))
    return row


def latest_target_confirmation(conn, namespace, page_id):
    rows = _records(conn, 'SELECT c.operation_id FROM plan_publish_confirmation c '
        'JOIN plan_publication p ON p.publication_id=c.publication_id '
        'WHERE p.source_namespace=? AND p.page_id=? ORDER BY c.rowid DESC LIMIT 1', (namespace, str(page_id)))
    return get_publish_confirmation(conn, rows[0]['operation_id']) if rows else None
