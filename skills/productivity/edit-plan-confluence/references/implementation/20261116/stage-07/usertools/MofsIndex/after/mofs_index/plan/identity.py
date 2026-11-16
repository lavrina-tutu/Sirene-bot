"""Pair-scoped identity policy. No inference from lineage, names or UID alone."""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path

POLICY_REVISION = 'identity-v1'
KINDS = {'task': ('plan_task_version', 'task_key'),
         'resource': ('plan_resource_version', 'resource_key'),
         'calendar': ('plan_calendar_version', 'calendar_key'),
         'assignment': ('plan_assignment_version', 'assignment_key')}


class IdentityError(ValueError):
    def __init__(self, code, exit_code=4):
        self.code, self.exit_code = code, exit_code
        super().__init__(code)


@dataclass(frozen=True)
class MappingPair:
    entity_kind: str
    from_key: str
    to_key: str
    identity_key: str


@dataclass(frozen=True)
class EntityRequirement:
    entity_kind: str
    from_key: str
    to_key: str | None = None


def records(conn, sql, args=()):
    cursor = conn.execute(sql, args)
    return [dict(zip((c[0] for c in cursor.description), row)) for row in cursor.fetchall()]


def snapshot(conn, plan_id, snapshot_id):
    rows = records(conn, 'SELECT * FROM plan_snapshot WHERE snapshot_id=?', (snapshot_id,))
    if not rows:
        raise IdentityError('snapshot_not_found')
    if rows[0]['plan_id'] != plan_id:
        raise IdentityError('selector_project_mismatch')
    return rows[0]


def pair_scope(conn, plan_id, from_snapshot_id, to_snapshot_id):
    a, b = (snapshot(conn, plan_id, sid) for sid in (from_snapshot_id, to_snapshot_id))
    def source(s):
        digest = s['source_mpp_sha256']
        if not digest and s['source_artifact_id']:
            row = conn.execute('SELECT raw_sha256 FROM plan_artifact WHERE artifact_id=?',
                               (s['source_artifact_id'],)).fetchone()
            digest = row[0] if row else None
        return digest
    return {'plan_id': plan_id, 'from_snapshot_id': from_snapshot_id, 'to_snapshot_id': to_snapshot_id,
            'from_representation': a['representation'], 'to_representation': b['representation'],
            'from_source_sha256': source(a), 'to_source_sha256': source(b),
            'from_profile': a['normalization_profile_fingerprint'], 'to_profile': b['normalization_profile_fingerprint'],
            'from_timezone': a['resolved_timezone'], 'to_timezone': b['resolved_timezone']}


def entities(conn, snapshot_id, kind):
    if kind not in KINDS:
        raise IdentityError('invalid_mapping', 2)
    table, key = KINDS[kind]
    rows = records(conn, f'SELECT * FROM {table} WHERE snapshot_id=?', (snapshot_id,))
    return rows, key


def keyed(conn, snapshot_id, kind):
    rows, key = entities(conn, snapshot_id, kind)
    result = {}
    for row in rows:
        value = row[key]
        if not isinstance(value, str) or not value.strip() or value in result:
            raise IdentityError('ambiguous_local_key')
        result[value] = row
    return result


def validate_mapping(document):
    if not isinstance(document, dict) or set(document) != {'schema_version', 'pairs'}:
        raise IdentityError('invalid_mapping', 2)
    if type(document['schema_version']) is not int or document['schema_version'] != 1 or not isinstance(document['pairs'], list) or not document['pairs']:
        raise IdentityError('invalid_mapping', 2)
    result = []
    for pair in document['pairs']:
        if not isinstance(pair, dict) or set(pair) != {'entity_kind','from_key','to_key','identity_key'}:
            raise IdentityError('invalid_mapping', 2)
        if any(not isinstance(value, str) or not value.strip() for value in pair.values()) or pair['entity_kind'] not in KINDS:
            raise IdentityError('invalid_mapping', 2)
        result.append(MappingPair(**pair))
    return tuple(result)


def validate_pairs(conn, scope, pairs):
    seen_from, seen_to, seen_identity = set(), set(), set()
    for pair in pairs:
        if not isinstance(pair, MappingPair) or pair.entity_kind not in KINDS or any(
                not isinstance(v, str) or not v.strip() for v in (pair.from_key, pair.to_key, pair.identity_key)):
            raise IdentityError('invalid_mapping', 2)
        kind = pair.entity_kind
        for snapshot_id, key in ((scope['from_snapshot_id'], pair.from_key), (scope['to_snapshot_id'], pair.to_key)):
            if key not in keyed(conn, snapshot_id, kind):
                raise IdentityError('mapping_key_not_found')
        indexes = ((seen_from, (kind, pair.from_key)), (seen_to, (kind, pair.to_key)),
                   (seen_identity, (kind, pair.identity_key)))
        for seen, key in indexes:
            if key in seen:
                raise IdentityError('mapping_not_one_to_one')
            seen.add(key)
    return tuple(pairs)


def continuity_pairs(conn, scope):
    if scope['from_representation'] != 'mpp' or scope['to_representation'] != 'mpp':
        raise IdentityError('continuity_requires_mpp')
    result = []
    # Continuity proves UID namespaces only. Calendar keys without UID are not inferred.
    for kind in ('task', 'resource', 'assignment'):
        indexes = []
        for sid in (scope['from_snapshot_id'], scope['to_snapshot_id']):
            rows, key = entities(conn, sid, kind)
            by_uid = {}
            for row in rows:
                uid = row.get('uid')
                if not isinstance(uid, str) or not re.fullmatch(r'0|[1-9][0-9]*', uid) or uid in by_uid:
                    raise IdentityError('invalid_or_duplicate_uid')
                if not row[key]:
                    raise IdentityError('ambiguous_local_key')
                by_uid[uid] = row[key]
            indexes.append(by_uid)
        for uid in sorted(set(indexes[0]) & set(indexes[1])):
            result.append(MappingPair(kind, indexes[0][uid], indexes[1][uid], kind + ':uid:' + uid))
    return validate_pairs(conn, scope, result)


def same_source(conn, scope):
    if scope['from_snapshot_id'] == scope['to_snapshot_id']:
        return True
    digest = scope['from_source_sha256']
    return bool(digest and re.fullmatch('[0-9a-f]{64}', digest)
        and digest == scope['to_source_sha256'] and scope['from_profile']
        and scope['from_profile'] == scope['to_profile']
        and scope['from_representation'] == scope['to_representation']
        and scope['from_timezone'] == scope['to_timezone'])


def revision_status(conn, revision_id):
    if conn.execute('SELECT 1 FROM plan_mapping_event WHERE mapping_revision_id=?', (revision_id,)).fetchone():
        return 'revoked'
    if conn.execute('SELECT 1 FROM plan_mapping_revision WHERE supersedes=?', (revision_id,)).fetchone():
        return 'superseded'
    return 'active'


def verify_evidence(conn, evidence_id, digest):
    row = conn.execute('SELECT raw_sha256,path FROM plan_artifact WHERE artifact_id=?', (evidence_id,)).fetchone()
    try:
        data = Path(row[1]).read_bytes() if row else b''
        valid = row and bool(data.strip()) and row[0] == digest and hashlib.sha256(data).hexdigest() == digest
    except OSError:
        valid = False
    if not valid:
        raise IdentityError('identity_evidence_unavailable', 5)


def show_revision(conn, project_slug, revision_id):
    rows = records(conn, 'SELECT r.*,p.project_slug FROM plan_mapping_revision r JOIN plan p ON p.plan_id=r.plan_id '
                   'WHERE mapping_revision_id=?', (revision_id,))
    if not rows or rows[0]['project_slug'] != project_slug:
        raise IdentityError('mapping_revision_scope_mismatch')
    rev = rows[0]
    if not rev['scope_json']:
        raise IdentityError('mapping_revision_unconfirmed')
    verify_evidence(conn, rev['evidence_id'], rev['evidence_sha256'])
    rev['scope'] = json.loads(rev['scope_json'])
    if rev['scope'] != pair_scope(conn, rev['plan_id'], rev['from_snapshot_id'], rev['to_snapshot_id']):
        raise IdentityError('mapping_revision_scope_mismatch')
    rev['status'] = revision_status(conn, revision_id)
    rev['pairs'] = records(conn, 'SELECT entity_kind,from_key,to_key,identity_key FROM plan_identity_mapping '
                           'WHERE mapping_revision_id=? ORDER BY entity_kind,from_key', (revision_id,))
    validate_pairs(conn, rev['scope'], tuple(MappingPair(**p) for p in rev['pairs']))
    return rev


def resolve_identity(conn, plan_id, from_snapshot_id, to_snapshot_id, mapping_revision_id=None):
    scope = pair_scope(conn, plan_id, from_snapshot_id, to_snapshot_id)
    slug = conn.execute('SELECT project_slug FROM plan WHERE plan_id=?', (plan_id,)).fetchone()[0]
    if mapping_revision_id:
        rev = show_revision(conn, slug, mapping_revision_id)
        if rev['scope'] != scope:
            raise IdentityError('mapping_revision_scope_mismatch')
        if rev['status'] != 'active':
            raise IdentityError('mapping_revision_inactive')
    else:
        rows = conn.execute('SELECT mapping_revision_id FROM plan_mapping_revision WHERE plan_id=? '
            'AND from_snapshot_id=? AND to_snapshot_id=? AND scope_json IS NOT NULL',
            (plan_id, from_snapshot_id, to_snapshot_id)).fetchall()
        active = [r[0] for r in rows if revision_status(conn, r[0]) == 'active']
        if len(active) > 1:
            raise IdentityError('mapping_ambiguous', 3)
        rev = show_revision(conn, slug, active[0]) if active else None
    if rev:
        return {'mapping': 'confirmed_uid' if rev['basis'] == 'continuity' else 'confirmed_mapping',
            'mapping_revision_id': rev['mapping_revision_id'], 'evidence_id': rev['evidence_id'],
            'evidence_sha256': rev['evidence_sha256'], 'scope': scope, 'pairs': rev['pairs']}
    if same_source(conn, scope):
        pairs = []
        for kind in KINDS:
            # Missing legacy assignment keys cannot prove correspondence.
            rows_a, key = entities(conn, from_snapshot_id, kind)
            rows_b, _ = entities(conn, to_snapshot_id, kind)
            a = {row[key] for row in rows_a if row[key]}
            b = {row[key] for row in rows_b if row[key]}
            if len(a) != len(rows_a) or len(b) != len(rows_b):
                continue
            pairs += [dict(entity_kind=kind,from_key=k,to_key=k,identity_key=kind+':'+k) for k in sorted(a & b)]
        return {'mapping':'same_source', 'mapping_revision_id':None, 'evidence_id':None,
                'evidence_sha256':None, 'scope':scope, 'pairs':pairs}
    return {'mapping':'unknown', 'mapping_revision_id':None, 'evidence_id':None,
            'evidence_sha256':None, 'scope':scope, 'pairs':[]}


def operation_requirements(conn, operation_id):
    rows = records(conn, 'SELECT * FROM plan_identity_requirement WHERE operation_id=? ORDER BY rowid', (operation_id,))
    for row in rows:
        row['required_entities'] = json.loads(row.pop('required_json'))
        row['scope'] = json.loads(row.pop('scope_json'))
        row.update({k:v for k,v in row['scope'].items() if k != 'plan_id'})
        choice = records(conn, 'SELECT c.* FROM plan_operation_mapping c JOIN plan_identity_requirement r '
            'ON r.requirement_id=c.requirement_id WHERE r.operation_id=? AND r.preparation_revision=? '
            'AND r.from_snapshot_id=? AND r.to_snapshot_id=? LIMIT 1',
            (operation_id,row['preparation_revision'],row['from_snapshot_id'],row['to_snapshot_id']))
        row['mapping_revision_id'] = choice[0]['mapping_revision_id'] if choice else None
        row['evidence_id'] = choice[0]['evidence_id'] if choice else None
        row['evidence_sha256'] = choice[0]['evidence_sha256'] if choice else None
        row['mapping_status'] = revision_status(conn,row['mapping_revision_id']) if choice else 'unselected'
        if choice:
            try:
                verify_evidence(conn,row['evidence_id'],row['evidence_sha256'])
            except IdentityError as exc:
                row['mapping_status'] = exc.code
        row['checks'] = records(conn,'SELECT * FROM plan_identity_check WHERE requirement_id=? ORDER BY rowid', (row['requirement_id'],))
    return rows
