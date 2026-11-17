"""Migration and backup acceptance through existing MofsIndex APIs only."""
import hashlib
import re
from pathlib import Path

import pytest
from mofs_index.db import connect, initialize
from mofs_index.plan import writer as w, query as q
from mofs_index.plan import migrate
from mofs_index.plan.backup import backup_to, verify_backup

pytestmark = [pytest.mark.acceptance, pytest.mark.unit]


@pytest.mark.parametrize('schema_version', [0, 6])
def test_new_and_old_schema_history(schema_version, tmp_path, monkeypatch, stage13_record):
    path = tmp_path/'migration-source'/'state/index.sqlite'
    path.parent.mkdir(parents=True)
    conn = connect(path, durable=True)
    initialize(conn)
    all_migrations = migrate.MIGRATIONS
    before = None
    try:
        if schema_version:
            monkeypatch.setattr(migrate, 'MIGRATIONS', all_migrations[:schema_version])
            assert len(migrate.ensure_plan_schema(conn)) == schema_version
            plan = w.ensure_plan(conn, 'stage13-legacy')
            lineage = w.ensure_lineage(conn, plan, 'legacy-file-line', page_id='test-legacy')
            raw = tmp_path/'old-source.mpp'; raw.write_bytes(b'Explicit legacy test bytes, not a reader fixture')
            artifact = w.record_artifact(conn, hashlib.sha256(raw.read_bytes()).hexdigest(), 'mpp', str(raw))
            snapshot = w.ingest_snapshot(conn, w.SnapshotSpec(plan, 'mpp', lineage_id=lineage,
                source_artifact_id=artifact, tasks=(w.TaskVersionSpec('old-task', uid='1', name='Legacy'),)))
            w.select_snapshot_baseline(conn, lineage, snapshot, is_explicit=True, basis='test owner')
            w.select_plan_baseline(conn, plan, snapshot, 0, is_explicit=True, basis='test owner')
            attempt = w.begin_attempt(conn, w.AttemptSpec(plan, lineage_id=lineage))
            w.record_event(conn, attempt, 'storage_put', 'confirmed', detail='Legacy registration, no read-back proof')
            pub = w.record_publication(conn, w.PublicationSpec(plan, 'test', 'legacy-att', 2,
                lineage_id=lineage, artifact_id=artifact, page_id='test-legacy', historical_status='registered'))
            # iterdump is a read-only test observation. Setup/migration/writes
            # use typed APIs; no handcrafted legacy INSERT/DDL is introduced.
            before = list(conn.iterdump())
            monkeypatch.setattr(migrate, 'MIGRATIONS', all_migrations)
        backup = tmp_path/'migration-copy.sqlite'
        assert backup_to(backup, path).ok and verify_backup(backup).ok
        copy = connect(backup, durable=True)
        try:
            applied = migrate.ensure_plan_schema(copy)
            assert len(applied) == len(all_migrations)-schema_version
            assert migrate.ensure_plan_schema(copy) == []
            assert verify_backup(backup).ok
            if schema_version:
                assert q.get_snapshot(copy, snapshot)['snapshot_id'] == snapshot
                assert Path(w.verify_artifact(copy, artifact)).read_bytes() == raw.read_bytes()
                versions = q.list_versions(copy, plan)['versions']
                publication = next(row for row in versions if row.get('publication_id') == pub)
                assert publication['trust'] == 'legacy_unverified'
                assert publication['historical_status'] == 'registered'
                after = list(copy.iterdump())
                for table in ('plan_baseline_selection', 'plan_snapshot_selection', 'plan_attempt_event', 'plan_artifact'):
                    prefix = 'INSERT INTO "'+table+'"'
                    old_rows = [r for r in before if r.startswith(prefix)]
                    new_rows = [r for r in after if r.startswith(prefix)]
                    assert len(old_rows) == len(new_rows)
                    for old, new in zip(old_rows, new_rows):
                        # Later migrations append nullable metadata columns.
                        assert new.startswith(old[:-2])
                        assert re.fullmatch(r'(?:,NULL)*\);', new[len(old)-2:])
                assert list(conn.iterdump()) == before
            stage13_record('migration-'+str(schema_version), {'source': str(path), 'copy': str(backup),
                'old_schema_version': schema_version, 'applied_migrations': applied,
                'checksums': migrate.applied_migrations(copy), 'integrity_check': 'ok', 'foreign_key_check': [],
                'original_unchanged': before is None or list(conn.iterdump()) == before,
                'history_preserved': schema_version > 0, 'network': 'forbidden'})
        finally:
            copy.close()
    finally:
        conn.close()
