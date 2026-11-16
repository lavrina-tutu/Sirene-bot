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
