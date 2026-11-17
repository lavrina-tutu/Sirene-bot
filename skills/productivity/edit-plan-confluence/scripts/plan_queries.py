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
        return history(conn, HistoryRequest(**parameters))
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
