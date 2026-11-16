"""Internal archive-placement decisions. MofsIndex owns every persisted fact."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import json

import plan_archive  # resolves the existing MofsIndex component path
from mofs_index.plan import writer as w, query as q
from plan_lock import batch_lock, PlanLockBusy


@dataclass(frozen=True)
class Proposal:
    proposal_id: str
    proposal_sha256: str
    reason_code: str
    content: dict


def check_batch_item(conn, operation, *, retry_decisions=False):
    """Before reader/archive: proved conflicts fail, only explicit grounds pause."""
    try:
        state = w.refresh_batch_proposals(conn, operation.operation_id, operation.attempt_id)
    except q.PlanQueryError as exc:
        if str(exc) != 'binding_conflict':
            raise
        return {'status': 'failed', 'exit_code': 4, 'warnings': [],
                'error': {'code': 'binding_conflict', 'message': 'Доказанный конфликт архивного размещения',
                          'retryable': False, 'next_action': 'Создать новый пакет с корректным контекстом'}}
    if not state['reasons']:
        return None
    if retry_decisions and state['decision_ready']:
        w.consume_batch_decisions(conn, operation.operation_id, operation.attempt_id)
        return None
    reason = (state['unresolved_reasons'] or state['reasons'])[0]
    return {'status': 'needs_decision', 'exit_code': 3, 'warnings': [],
            'error': {'code': reason, 'message': 'Требуется адресное подтверждение архивного размещения',
                      'retryable': False, 'next_action': 'operation show --operation-id ' + operation.operation_id}}


def action_error(action, code, exit_code=4, **ids):
    return {'schema_version': 1, 'action': action, 'status': 'failed', 'exit_code': exit_code,
            **ids, 'published': False, 'error': {'code': code, 'message': code, 'retryable': False,
                'next_action': 'Создать новый batch ID для изменения контекста' if code == 'batch_context_immutable'
                               else 'operation show --operation-id ' + str(ids.get('operation_id', ''))}}


def register_decision(operation_id, proposal_id=None, *, reason=None, rule_scope='once', timezone_hint=None,
                      mapping_revision=None, db_path=None, workvault=None, cache_dir=None):
    from plan_batch import _connect, _db, _check_paths
    database = _db(db_path=db_path)
    conn = None
    try:
        conn = _connect(database)
        item = q.get_operation_item(conn, operation_id)
        if not item or not item['batch_id']:
            return action_error('register_batch_decision', 'operation_not_found', operation_id=operation_id)
        batch_id = item['batch_id']
        # The preliminary lookup is read-only; all validation repeats under flock.
        with batch_lock(database, batch_id):
            item = q.get_operation_item(conn, operation_id)
            batch = q.get_import_batch(conn, batch_id)
            _check_paths(json.loads(batch['context_json'])['execution'], workvault=workvault, cache_dir=cache_dir)
            if not proposal_id or timezone_hint or mapping_revision or rule_scope != 'once':
                return action_error('register_batch_decision', 'batch_context_immutable',
                                    operation_id=operation_id, batch_id=batch_id, item_id=item['item_id'])
            if not reason or not reason.strip():
                return action_error('register_batch_decision', 'invalid_decision_reason', 2, operation_id=operation_id)
            from plan_reconcile import frozen_batch_input
            frozen_batch_input(item)
            return w.register_batch_decision(conn, w.BatchDecisionSpec(operation_id, proposal_id, reason, rule_scope=rule_scope))
    except Exception as exc:
        code = getattr(exc, 'code', str(exc).split(':')[0] if isinstance(exc, (w.PlanWriterError, q.PlanQueryError)) else 'archive_unavailable')
        conflict = code in ('proposal_context_mismatch', 'decision_conflict', 'batch_context_immutable',
                            'inputs_not_frozen', 'batch_busy', 'batch_context_conflict', 'binding_conflict')
        return action_error('register_batch_decision', code, 4 if conflict or isinstance(exc, PlanLockBusy) else 5,
                            operation_id=operation_id, proposal_id=proposal_id)
    finally:
        if conn is not None:
            conn.close()
