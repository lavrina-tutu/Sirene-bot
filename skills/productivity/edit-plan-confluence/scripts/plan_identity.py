"""Internal identity CLI adapters. Confirmation never resumes an operation."""
from __future__ import annotations

import getpass
import json
from pathlib import Path

import plan_archive  # existing component path bootstrap
from mofs_index.plan import writer as w, identity as i


def snapshot_selector(value):
    if not isinstance(value,str) or not value.startswith('snapshot:') or not value[9:].strip() or ':' in value[9:]:
        raise i.IdentityError('invalid_snapshot_selector',2)
    return value[9:]


def _unique_object(pairs):
    result = {}
    for key,value in pairs:
        if key in result:
            raise i.IdentityError('invalid_mapping',2)
        result[key]=value
    return result


def load_mapping(path):
    try:
        document=json.loads(Path(path).read_text(encoding='utf-8'),object_pairs_hook=_unique_object)
    except (OSError,ValueError,UnicodeError) as exc:
        raise i.IdentityError('invalid_mapping',2) from exc
    return i.validate_mapping(document)


def identity_action(command, *, project_slug, from_selector=None, to_selector=None, mode=None,
                    evidence=None, reason=None, mapping=None, supersedes=None, mapping_revision=None,
                    db_path=None, workvault=None, cache_dir=None):
    from mofs_index.plan.migrate import ensure_plan_schema
    def connect():
        connection=plan_archive._connect(Path(db_path) if db_path else None)
        ensure_plan_schema(connection)
        return connection
    conn = None
    action='identity_'+command
    try:
        if command == 'confirm':
            # Reject shape errors before any durable mutation.
            a,b=snapshot_selector(from_selector),snapshot_selector(to_selector)
            if mode not in ('continuity','mapping') or bool(mapping) != (mode=='mapping') or not reason or not reason.strip():
                raise i.IdentityError('invalid_identity_arguments',2)
            pairs=load_mapping(mapping) if mapping else ()
            try:
                data=Path(evidence).read_bytes()
            except (OSError,TypeError) as exc:
                raise i.IdentityError('invalid_identity_evidence',2) from exc
            if not data.strip():
                raise i.IdentityError('invalid_identity_evidence',2)
            conn=connect()
            plan=plan_archive.plan_query.resolve_plan(conn,project_slug)
            if 'plan_id' not in plan:
                raise i.IdentityError('selector_project_mismatch')
            # Validate scope and keys before saving evidence. No project is created.
            scope=i.pair_scope(conn,plan['plan_id'],a,b)
            i.continuity_pairs(conn,scope) if mode=='continuity' else i.validate_pairs(conn,scope,pairs)
            artifact,digest=plan_archive.store_artifact(data,'identity_evidence',project_slug=project_slug,
                                                       ext='bin',conn=conn,workvault=workvault)
            rev=w.register_identity_confirmation(conn,w.IdentityConfirmationSpec(
                project_slug,a,b,mode,artifact,digest,reason,getpass.getuser(),'explicit_user_cli',
                pairs=pairs,supersedes=supersedes))
            return {'schema_version':1,'action':action,'status':'confirmed','exit_code':0,
                'project_slug':project_slug,'from_snapshot_id':a,'to_snapshot_id':b,
                'from_source_sha256':rev['scope']['from_source_sha256'],'to_source_sha256':rev['scope']['to_source_sha256'],
                'mapping_revision_id':rev['mapping_revision_id'],'revision_status':rev['status'],'evidence_id':rev['evidence_id'],
                'evidence_sha256':rev['evidence_sha256'],'published':False,'error':None}
        if command != 'show' or not mapping_revision:
            raise i.IdentityError('invalid_identity_arguments',2)
        conn=connect()
        result=plan_archive.plan_query.get_identity_revision(conn,project_slug,mapping_revision)
        return {'schema_version':1,'action':action,'exit_code':0,'project_slug':project_slug,
                'mapping_revision_id':mapping_revision,'result':result,'published':False,'error':None}
    except i.IdentityError as exc:
        return {'schema_version':1,'action':action,'status':'needs_decision' if exc.exit_code==3 else 'failed',
                'exit_code':exc.exit_code,'project_slug':project_slug,'result':None,
                'published':False,'error':{'code':exc.code,'message':exc.code}}
    except Exception:
        return {'schema_version':1,'action':action,'status':'failed','exit_code':5,'result':None,
                'published':False,'error':{'code':'identity_unavailable','message':'Подтверждение недоступно'}}
    finally:
        if conn is not None:
            conn.close()
