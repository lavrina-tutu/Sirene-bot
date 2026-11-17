"""Internal CLI adapter. Import-history continues to belong to plan_history."""
from __future__ import annotations


def query_history(*, db_path=None, workvault=None, cache_dir=None, **parameters):
    # Resolve existing component import path, without importing a network client.
    import plan_archive  # noqa: F401
    from mofs_index.plan.history import history, HistoryRequest, HistoryQueryError
    from plan_batch import _connect, _db
    conn = None
    try:
        conn = _connect(_db(db_path=db_path))
        result = history(conn, HistoryRequest(**parameters))
        if result['exit_code'] == 0:
            for row in result['result']['records'] + result['result'].get('unknown_source_dates', []):
                if 'item_id' in row:
                    row['source_mtime_ns'] = source_mtime(conn, row)
            result['result']['current_plan'] = current_plan(conn, parameters['project_slug'], parameters.get('lineage_id'))
        return result
    except HistoryQueryError as exc:
        return {'schema_version': 1, 'action': 'history', 'exit_code': 2, 'result': None,
                'error': {'code': str(exc), 'message': str(exc)}}
    except Exception:
        return {'schema_version': 1, 'action': 'history', 'exit_code': 5, 'result': None,
                'error': {'code': 'history_unavailable', 'message': 'История недоступна'}}
    finally:
        if conn is not None:
            conn.close()


def query_compare(*, project_slug, from_selector, to_selector, mapping_revision=None,
                  db_path=None, workvault=None, cache_dir=None):
    import plan_archive  # noqa: F401
    from mofs_index.plan import query as q
    from mofs_index.plan.selectors import parse_selector, PlanQueryError
    from mofs_index.plan.identity import IdentityError
    from plan_batch import _connect, _db
    conn = None
    try:
        a, b = parse_selector(from_selector), parse_selector(to_selector)
        conn = _connect(_db(db_path=db_path))
        plan = q.resolve_plan(conn, project_slug)
        if 'plan_id' not in plan:
            raise PlanQueryError('project_not_found')
        result = q.diff_versions(conn, plan['plan_id'], a, b, mapping_revision_id=mapping_revision)
        if result.get('result_class') == 'observed_diff':
            result['task_history'] = task_history(conn, result)
        return {'schema_version':1, 'action':'compare', 'exit_code':result.get('exit_code',0),
                'result':result, 'error':None}
    except (PlanQueryError, IdentityError) as exc:
        return {'schema_version':1, 'action':'compare', 'exit_code':exc.exit_code, 'result':None,
                'error':{'code':exc.code, 'message':exc.code}}
    except Exception:
        return {'schema_version':1, 'action':'compare', 'exit_code':5, 'result':None,
                'error':{'code':'compare_unavailable','message':'Сравнение недоступно'}}
    finally:
        if conn is not None:
            conn.close()


def source_mtime(conn, item):
    import json
    from mofs_index.plan import query as q
    for event in reversed(q.get_operation_events(conn, item['operation_id'])):
        if event['event_kind'] == 'source_file_metadata':
            meta = json.loads(event['detail'])
            if meta.get('item_id') == item['item_id'] and meta.get('source_mpp_sha256') == item['source_mpp_sha256']:
                value = meta.get('source_mtime_ns')
                return value if type(value) is int else None
    return None


def current_plan(conn, slug, lineage_id=None):
    """All archived arrivals, independent of history page/filter/ingestion order."""
    from mofs_index.plan.history import history, HistoryRequest
    rows, cursor = [], None
    while True:
        page = history(conn, HistoryRequest(slug, view='files', lineage_id=lineage_id, limit=1000, cursor=cursor))['result']
        for row in page['records']:
            if row.get('snapshot_id'):
                rows.append({**{k:row[k] for k in ('item_id','snapshot_id','original_name','source_mpp_sha256')},
                    'source_mtime_ns':source_mtime(conn,row)})
        cursor = page['next_cursor']
        if not cursor:
            break
    known = [row for row in rows if row['source_mtime_ns'] is not None]
    maximum = max((row['source_mtime_ns'] for row in known), default=None)
    candidates = [row for row in known if row['source_mtime_ns'] == maximum]
    snapshots = {row['snapshot_id'] for row in candidates}
    status = 'selected' if len(snapshots) == 1 else 'ambiguous' if snapshots else 'unknown'
    return {'basis':'source_file_mtime_ns','status':status,'source_mtime_ns':maximum,
        'snapshot_id':next(iter(snapshots)) if len(snapshots) == 1 else None,
        'candidates':candidates,'unknown_mtime_count':len(rows)-len(known)}


def task_history(conn, diff):
    """Source-local record difference, separate from cross-file identity proof."""
    import json
    from mofs_index.plan import query as q
    receipt = diff.get('receipt', {})
    ids = (receipt.get('snapshot_a'), receipt.get('snapshot_b'))
    if not all(ids):
        return {'status':'unavailable','reason':'exact_source_snapshot_pair_required'}
    snapshots = [q.get_snapshot(conn, ident) for ident in ids]
    if any(row['representation'] != 'mpp' for row in snapshots):
        return {'status':'unavailable','reason':'mpp_snapshot_pair_required'}
    sources = [json.loads(row['source_json'] or '{}') for row in snapshots]
    if not all(isinstance(src.get('tasks'), list) for src in sources):
        return {'status':'unavailable','reason':'normalized_source_records_required'}
    tasks = [{t['task_key']:t for t in src['tasks'] if 'error' not in t} for src in sources]
    pairs = receipt.get('confirmed_pairs', [])
    mapping = {p['from_key']:p['to_key'] for p in pairs if p['entity_kind'] == 'task'}
    # Common local keys are compared as records, never promoted to identity proof.
    removed = tasks[0].keys() - tasks[1].keys() - mapping.keys()
    added = tasks[1].keys() - tasks[0].keys() - set(mapping.values())
    def describe(index, keys):
        src = sources[index]
        deps = [*src.get('dependencies', []), *src.get('external_dependencies', [])]
        return [{'task_key':key,'task':tasks[index][key],
            'links':[d for d in deps if key in (d.get('predecessor_task_key'),d.get('successor_task_key'),d.get('local_task_key'))]}
            for key in sorted(keys)]
    return {'status':'compared','basis':'source_local_key_diff','snapshot_from':ids[0],'snapshot_to':ids[1],
        'added':describe(1,added),'removed':describe(0,removed),
        'identity':receipt.get('mapping','unknown'),
        'limitation':'Local key changes are record additions/removals; task continuity requires separate identity evidence.'}
