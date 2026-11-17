"""Exact selectors shared by every plan reader. No latest/vN fallback."""
from __future__ import annotations

from .identity import IdentityError


class PlanQueryError(IdentityError, RuntimeError):
    def __init__(self, code, exit_code=4):
        super().__init__(code, exit_code)


def records(conn, sql, args=()):
    cur = conn.execute(sql, args)
    return [dict(zip((c[0] for c in cur.description), row)) for row in cur.fetchall()]


def parse_selector(value):
    if not isinstance(value, str) or ':' not in value:
        raise PlanQueryError('exact_selector_required', 2)
    kind, ident = value.split(':', 1)
    if kind not in ('snapshot', 'publication') or not ident.strip():
        raise PlanQueryError('exact_selector_required', 2)
    return {'kind': kind, kind + '_id': ident}


def resolve_selector(conn, plan_id, selector):
    if not isinstance(selector, dict) or selector.get('kind') not in ('snapshot', 'publication'):
        raise PlanQueryError('exact_selector_required', 2)
    kind = selector['kind']
    key = kind + '_id'
    allowed = {'kind', key} | ({'page_id', 'attachment_id', 'attachment_version', 'snapshot_id'} if kind == 'publication' else set())
    if set(selector) - allowed or not isinstance(selector.get(key), str) or not selector[key].strip():
        raise PlanQueryError('exact_publication_id_required' if kind == 'publication' else 'exact_snapshot_id_required', 2)
    rows = records(conn, 'SELECT * FROM plan_' + kind + ' WHERE ' + key + '=?', (selector[key],))
    if not rows:
        raise PlanQueryError(kind + '_not_found')
    row = rows[0]
    if row['plan_id'] != plan_id:
        raise PlanQueryError('selector_project_mismatch')
    if kind == 'publication':
        for field in ('page_id', 'attachment_id', 'attachment_version'):
            if field in selector and selector[field] != row[field]:
                raise PlanQueryError('publication_' + field + '_mismatch')
        if not row['page_id'] or not row['attachment_id'] or not row['filename'] or type(row['attachment_version']) is not int or row['attachment_version'] < 1:
            raise PlanQueryError('publication_target_incomplete', 5)
        if row['lineage_id']:
            line = records(conn, 'SELECT * FROM plan_lineage WHERE lineage_id=?', (row['lineage_id'],))
            if not line or line[0]['plan_id'] != plan_id or (line[0]['page_id'] and line[0]['page_id'] != row['page_id']):
                raise PlanQueryError('publication_lineage_mismatch')
        links = records(conn, 'SELECT l.*,s.plan_id AS snapshot_plan_id,s.representation,s.source_artifact_id FROM plan_publication_snapshot l '
            'JOIN plan_snapshot s USING(snapshot_id) WHERE publication_id=? ORDER BY l.rowid', (row[key],))
        if any(link['snapshot_plan_id'] != plan_id for link in links):
            raise PlanQueryError('selector_project_mismatch')
        if 'snapshot_id' in selector:
            links = [link for link in links if link['snapshot_id'] == selector['snapshot_id']]
            if not links:
                raise PlanQueryError('publication_snapshot_mismatch')
        def usable(link):
            if link['confidence'] != 'confirmed' or not link['evidence']:
                return False
            if link['representation']=='gantt_json':
                artifact = records(conn,'SELECT raw_sha256 FROM plan_artifact WHERE artifact_id=?',(link['source_artifact_id'],))
                return bool(artifact and artifact[0]['raw_sha256']==row['raw_sha256'])
            return True  # Source provenance only; never positional Gantt identity.
        confirmed = sorted({link['snapshot_id'] for link in links if usable(link)})
        row['snapshot_links'] = links
        row['snapshot_id'] = confirmed[0] if len(confirmed) == 1 else None
        row['snapshot_link_quality'] = 'confirmed' if len(confirmed) == 1 else 'ambiguous' if confirmed else 'unknown'
        row['selector'] = {k: selector[k] for k in sorted(selector)}
    else:
        row['selector'] = {'kind': kind, key: row[key]}
    return row


def resolve_pair(conn, plan_id, a, b):
    # Both owners are checked before representation/mapping/content comparison.
    return resolve_selector(conn, plan_id, a), resolve_selector(conn, plan_id, b)
