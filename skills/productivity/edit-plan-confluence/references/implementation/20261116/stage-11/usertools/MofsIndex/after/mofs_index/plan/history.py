"""Typed, read-only history. Arrivals, unique snapshots and publications stay distinct.

Dates explicitly supplied by the user are calendar dates on the UTC date scale
for source filtering; this does not assert a timezone for task dates. Status dates
and filenames are never substituted for a missing source version date.
"""
from __future__ import annotations

import base64
import hashlib
import json
from dataclasses import dataclass
from datetime import date, datetime, timezone

from . import query as q


class HistoryQueryError(ValueError):
    pass


def timestamp(value):
    if not isinstance(value, str) or 'T' not in value:
        raise HistoryQueryError('timezone_aware_timestamp_required')
    try:
        result = datetime.fromisoformat(value.replace('Z', '+00:00'))
        if result.utcoffset() is None:
            raise ValueError()
    except ValueError as exc:
        raise HistoryQueryError('timezone_aware_timestamp_required') from exc
    return result.astimezone(timezone.utc).isoformat(timespec='microseconds')


def _time(value, *, source=False):
    if value is None:
        return None
    try:
        if source and len(value) == 10:
            value = date.fromisoformat(value).isoformat() + 'T00:00:00+00:00'
        return timestamp(value)
    except (ValueError, TypeError):
        return None  # Historical unknown/naive time is not invented.


@dataclass(frozen=True)
class HistoryRequest:
    project_slug: str
    view: str = 'files'
    order: str = 'ingested'
    lineage_id: str | None = None
    since: str | None = None
    until: str | None = None
    time_field: str | None = None
    limit: int = 100
    cursor: str | None = None


def _encode(value):
    return base64.urlsafe_b64encode(json.dumps(value, sort_keys=True, separators=(',', ':')).encode()).decode()


def _decode(value):
    try:
        if len(value) > 16384:
            raise ValueError()
        data = json.loads(base64.b64decode(value.encode(), altchars=b'-_', validate=True))
        if not isinstance(data, dict) or data.get('version') != 1:
            raise ValueError()
        return data
    except (ValueError, TypeError, UnicodeError) as exc:
        raise HistoryQueryError('invalid_history_cursor') from exc


def _load(conn, slug, view, marks):
    """One arrival per item; one snapshot per snapshot; one publication per ID."""
    publications = q._records(conn, 'SELECT u.rowid AS sequence,u.* FROM plan_publication u JOIN plan p USING(plan_id) '
        'WHERE u.rowid<=? AND p.project_slug=?', (marks['publications'], slug))
    for publication in publications:
        observations = q.publication_observations(conn,publication['publication_id'],watermark=marks['observations'])
        publication['observations'] = [{key:o[key] for key in ('observation_id','page_version','verified_at',
            'verification_status','verification_scope','verification_profile','confidence')} for o in observations]
        publication['verified_at'] = observations[-1]['verified_at'] if observations else None
        publication['representation'] = 'gantt_json'
        publication['publication_verified'] = publication['trust']=='verified_v1'
    links = q._records(conn, 'SELECT l.* FROM plan_publication_snapshot l JOIN plan_publication u USING(publication_id) '
        'JOIN plan p ON p.plan_id=u.plan_id WHERE l.rowid<=? AND p.project_slug=?', (marks['links'], slug))
    commits = q._records(conn, 'SELECT a.item_id,e.created_at FROM plan_attempt_event e '
        "JOIN plan_import_attempt a USING(attempt_id) WHERE e.event_kind='snapshot_committed' AND e.rowid<=?",
        (marks['events'],))
    recorded = {row['item_id']: row['created_at'] for row in commits}
    items = q._records(conn, 'SELECT i.rowid AS sequence,i.*,o.context_json,p.project_slug FROM plan_import_item i '
        'JOIN plan_operation o USING(operation_id) LEFT JOIN plan p ON p.plan_id=i.plan_id '
        'WHERE i.rowid<=? AND (p.project_slug=? OR i.plan_id IS NULL)', (marks['files'], slug))
    for row in items:
        context = json.loads(row.pop('context_json'))
        saved = context.get('save', {})
        row['project_slug'] = row['project_slug'] or saved.get('project_slug')
        row['lineage_id'] = row['lineage_id'] or saved.get('lineage_id')
    # Metadata history never loads full normalized project JSON into memory.
    columns = [row[1] for row in conn.execute('PRAGMA table_info(plan_snapshot)') if row[1] != 'source_json']
    snapshots = q._records(conn, 'SELECT s.rowid AS sequence,' + ','.join('s.'+name for name in columns) + ',p.project_slug FROM plan_snapshot s '
        'JOIN plan p USING(plan_id) WHERE s.rowid<=? AND p.project_slug=?', (marks['snapshots'], slug))
    by_snapshot = {}
    for link in links:
        group = by_snapshot.setdefault(link['snapshot_id'], [])
        for publication in publications:
            if publication['publication_id'] != link['publication_id']:
                continue
            existing = next((p for p in group if p['publication_id'] == publication['publication_id']), None)
            if existing is None:
                existing = {**publication, 'link_evidence': []}
                group.append(existing)
            existing['link_evidence'].append({key: link[key] for key in ('link_id', 'confidence', 'evidence')})
    def enrich(row):
        pubs = by_snapshot.get(row.get('snapshot_id'), [])
        known = [p['published_at'] for p in pubs if _time(p['published_at'])]
        row['publications'] = [{key:p[key] for key in ('publication_id','page_id','attachment_id','attachment_version',
            'published_at','observed_at','recorded_at','verified_at','trust','historical_status','observations','link_evidence')} for p in pubs]
        # A source snapshot's NULL published_at does not deny linked publications.
        row['published_at'] = min(known, key=_time) if known else None
        return row
    snap_map = {row['snapshot_id']: row for row in snapshots}
    if view == 'files':
        rows = []
        for row in items:
            if row['project_slug'] != slug:
                continue
            snap = snap_map.get(row['snapshot_id'], {})
            row['recorded_at'] = recorded.get(row['item_id'])
            row['snapshot_recorded_at'] = snap.get('recorded_at')
            row['status_date'] = snap.get('status_date')
            rows.append(enrich(row))
        return rows, 'item_id'
    if view == 'snapshots':
        rows = []
        for row in snapshots:
            if row['project_slug'] != slug:
                continue
            arrivals = [i for i in items if i['snapshot_id'] == row['snapshot_id']]
            row['received_at'] = min((i['received_at'] for i in arrivals if _time(i['received_at'])), key=_time, default=None)
            dates = sorted({i['source_version_date'] for i in arrivals if i['source_version_date']})
            row['source_version_dates'] = dates
            # Multiple distinct labels do not become one invented version date.
            row['source_version_date'] = dates[0] if len(dates) == 1 else None
            row.pop('source_json', None)
            rows.append(enrich(row))
        return rows, 'snapshot_id'
    plan = q.resolve_plan(conn, slug)
    plan_id = plan.get('plan_id') if plan else None
    rows = []
    for row in publications:
        if row['plan_id'] != plan_id:
            continue
        row['snapshot_links'] = [link for link in links if link['publication_id'] == row['publication_id']]
        row['snapshot_ids'] = sorted({link['snapshot_id'] for link in row['snapshot_links']})
        row['received_at'] = row['observed_at']
        row['source_version_date'] = None  # An import time is not a historical version date.
        rows.append(row)
    return rows, 'publication_id'


def history(conn, request: HistoryRequest):
    if request.view not in ('files', 'snapshots', 'publications') or request.order not in ('ingested', 'source'):
        raise HistoryQueryError('invalid_history_arguments')
    if isinstance(request.limit, bool) or not isinstance(request.limit, int) or not 1 <= request.limit <= 1000:
        raise HistoryQueryError('invalid_history_limit')
    field = request.time_field or {'files': 'received', 'snapshots': 'recorded', 'publications': 'published'}[request.view]
    if field not in ('received', 'recorded', 'source', 'published'):
        raise HistoryQueryError('invalid_history_time_field')
    since = timestamp(request.since) if request.since is not None else None
    until = timestamp(request.until) if request.until is not None else None
    if since and until and since >= until:
        raise HistoryQueryError('invalid_history_period')
    params = {'project_slug': request.project_slug, 'view': request.view, 'order': request.order,
              'lineage_id': request.lineage_id, 'since': since, 'until': until, 'time_field': field}
    fingerprint = hashlib.sha256(json.dumps(params, sort_keys=True).encode()).hexdigest()
    cursor = _decode(request.cursor) if request.cursor else None
    if cursor and cursor.get('query') != fingerprint:
        raise HistoryQueryError('history_cursor_context_mismatch')
    if conn.in_transaction:
        raise HistoryQueryError('caller_transaction_forbidden')
    conn.execute('BEGIN')
    try:
        tables = {'files': 'plan_import_item', 'snapshots': 'plan_snapshot', 'publications': 'plan_publication', 'links': 'plan_publication_snapshot', 'events': 'plan_attempt_event', 'observations':'plan_publication_page_link'}
        marks = {name: conn.execute('SELECT coalesce(max(rowid),0) FROM ' + table).fetchone()[0] for name, table in tables.items()}
        if cursor:
            marks = cursor.get('watermarks')
            if not isinstance(marks, dict) or set(marks) != set(tables) or any(type(v) is not int or v < 0 for v in marks.values()):
                raise HistoryQueryError('invalid_history_cursor')
        rows, identity = _load(conn, request.project_slug, request.view, marks)
        if request.lineage_id:
            rows = [row for row in rows if row['lineage_id'] == request.lineage_id]
        column = {'received': 'received_at', 'recorded': 'recorded_at', 'source': 'source_version_date', 'published': 'published_at'}[field]
        unknown = sum(_time(row.get(column), source=field == 'source') is None for row in rows)
        if since or until:
            rows = [row for row in rows if (value := _time(row.get(column), source=field == 'source')) is not None
                    and (not since or value >= since) and (not until or value < until)]
        unknown_source = sum(row.get('source_version_date') is None for row in rows)
        def key(row):
            value = _time(row.get('source_version_date'), source=True) if request.order == 'source' else _time(
                row.get('received_at') if request.view == 'files' else row.get('recorded_at'))
            return [int(value is None), value or '', row.get('ordinal', 0), row[identity]]
        rows.sort(key=key)
        total = len(rows)
        if cursor:
            last = cursor.get('after')
            if not isinstance(last, list) or len(last) != 4 or type(last[0]) is not int or not isinstance(last[1], str) or type(last[2]) is not int or not isinstance(last[3], str):
                raise HistoryQueryError('invalid_history_cursor')
            rows = [row for row in rows if key(row) > last]
        page = rows[:request.limit]
        next_cursor = _encode({'version': 1, 'query': fingerprint, 'watermarks': marks, 'after': key(page[-1])}) if len(rows) > request.limit else None
        unknown_page = [row for row in page if row.get('source_version_date') is None] if request.order == 'source' else []
        main_page = [row for row in page if row.get('source_version_date') is not None] if request.order == 'source' else page
        return {'schema_version': 1, 'action': 'history', 'exit_code': 0, 'parameters': {**params, 'limit': request.limit},
                'result': {'records': main_page, 'unknown_source_dates': unknown_page, 'unknown_source_date_count': unknown_source,
                           'unknown_time_count': unknown, 'total': total, 'next_cursor': next_cursor},
                'quality': {'time_interval': '[since,until)', 'source_date_scale': 'UTC calendar date; no task timezone inference',
                            'identity': 'not_evaluated', 'publication_trust': 'preserved'}, 'error': None}
    finally:
        conn.execute('ROLLBACK')
