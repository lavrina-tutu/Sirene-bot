"""GET-only publication observations. Never rewrites publication trust or dates."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

from conf_client import ConfluenceClient


class ReadOnlyConfluenceClient(ConfluenceClient):
    """Transport-level guard, including direct/download requests."""
    @classmethod
    def from_client(cls, client):
        result = cls.__new__(cls)
        for key in ('base_url','token','timeout','retry_limit'):
            setattr(result,key,getattr(client,key))
        return result

    def _request(self, method, path, **kwargs):
        if method != 'GET' or kwargs.get('data') is not None:
            raise ValueError('publication_verify_get_only')
        return super()._request(method, path, **kwargs)

    def _read(self, req):
        if req.get_method() != 'GET' or req.data is not None:
            raise ValueError('publication_verify_get_only')
        return super()._read(req)


def _verify(conn, pub, client, scope):
    from mofs_index.plan import query as q, writer as w
    from macro import find_macro
    from plan_verify import verify_attachment_bytes, verify_storage_observation
    reasons, checks = [], {}
    expected = q._load_publication(conn, pub['plan_id'], pub['publication_id'])
    if expected['artifact_quality'] != 'verified_bytes':
        reasons.append('expected_bytes_unavailable')
    if pub['snapshot_link_quality'] != 'confirmed':
        reasons.append('confirmed_snapshot_link_required')
    observations = [o for o in q.publication_observations(conn,pub['publication_id'])
                    if not o['link_kind'].startswith('publication_verify:') and o['confidence']=='confirmed'
                    and o['plan_id']==pub['plan_id'] and o['page_id']==pub['page_id']]
    saved = observations[-1] if observations else {}
    storage_expected = saved.get('itogo_raw')
    if saved.get('storage_artifact_id'):
        try:
            storage_expected = Path(w.verify_artifact(conn,saved['storage_artifact_id'])).read_text()
        except (OSError, ValueError, w.PlanWriterError):
            storage_expected = None
    if not storage_expected or not saved.get('storage_sha256') or hashlib.sha256(storage_expected.encode()).hexdigest()!=saved['storage_sha256']:
        storage_expected = None
        reasons.append('expected_storage_unavailable')
    version = pub.get('page_version')
    if scope=='historical_version' and not version:
        reasons.append('historical_page_version_unknown')
    page, storage, attachment = {}, None, {}
    mismatch = False
    def read_failure(label, exc):
        reasons.append(label)
        checks[label] = {'error_type':type(exc).__name__, 'http_status':getattr(exc,'status',None)}
    try:
        raw = client.download_attachment_version(pub['page_id'],pub['attachment_id'],pub['filename'],pub['attachment_version'])
        if expected['artifact_quality']=='verified_bytes':
            result = verify_attachment_bytes(raw,pub['raw_sha256'])
            attachment = {'attachment_id':pub['attachment_id'],'attachment_version':pub['attachment_version'],
                'expected_sha256':result.expected_sha256,'actual_sha256':result.actual_sha256}
            checks['exact_attachment'] = result.ok
            mismatch |= not result.ok
    except Exception as exc:
        read_failure('exact_attachment_unavailable',exc)
    try:
        if scope=='historical_version' and version:
            page = client._request('GET','/rest/api/content/'+pub['page_id'],
                query={'version':str(version),'expand':'body.storage,version,space'},headers={'Cache-Control':'no-cache'})
        else:
            page = client.get_page(pub['page_id'])
        if str(page.get('id')) != pub['page_id']:
            raise ValueError('page_id_mismatch')
        storage = page['body']['storage']['value']
        observed_version = page['version']['number']
        if scope=='historical_version' and version and observed_version != version:
            reasons.append('historical_version_not_returned')
            mismatch = True
        if storage_expected:
            macro = find_macro(storage_expected)
            summary = re.findall(r'Итого:\s*с\s*(\d{2}\.\d{2}\.\d{2})\s*по\s*(\d{2}\.\d{2}\.\d{2})\s*-\s*(\d+)\s*рабочих дней',storage_expected)
            if not macro or macro.attachment_name != pub['filename'] or (pub['macro_id'] and macro.macro_id != pub['macro_id']) or len(summary)!=1:
                reasons.append('expected_managed_fields_incomplete')
            else:
                d1,d2,n = summary[0]
                v = verify_storage_observation(storage,expected_storage=storage_expected,expected_macro=macro,
                    expected_itogo=(d1,d2,int(n)),expected_version=version if scope=='historical_version' and version else observed_version,
                    actual_version=observed_version)
                checks.update(v.checks)
                mismatch |= not v.ok
        if scope=='current_state':
            current = [a for a in client.list_attachments(pub['page_id']) if a.get('title')==pub['filename']]
            checks['current_attachment'] = (len(current)==1 and str(current[0]['id'])==pub['attachment_id']
                and current[0].get('version',{}).get('number')==pub['attachment_version'])
            latest = client.get_page(pub['page_id'])
            checks['current_page_stable'] = (str(latest.get('id'))==pub['page_id'] and latest['version']['number']==observed_version
                and latest['body']['storage']['value']==storage)
            mismatch |= not checks['current_attachment'] or not checks['current_page_stable']
    except Exception as exc:
        read_failure('page_storage_unavailable',exc)
    ok = not reasons and not mismatch and bool(attachment) and bool(storage_expected) and checks.get('exact_attachment') is True
    status = 'verified_observation' if ok else 'verification_failed' if mismatch else 'not_verified'
    evidence = {'checks':{k:v for k,v in checks.items() if k!='exact_attachment'},'attachment':attachment,
        'reasons':reasons,'publication_id':pub['publication_id'],'historical_publication_proven':False,
        'schedule':'not_verified'}
    obs_id = w.record_page_observation(conn,w.PageObservationSpec(plan_id=pub['plan_id'],page_id=pub['page_id'],
        page_version=page.get('version',{}).get('number'),itogo_raw=storage,
        quality='complete' if ok else 'unknown',verification_status=status,verification_scope=scope,
        verification_profile='publication-verify-v1',verification=evidence,
        storage_sha256=hashlib.sha256(storage.encode()).hexdigest() if storage is not None else None))
    w.link_publication_page(conn,pub['publication_id'],obs_id,link_kind='publication_verify:'+scope,
        confidence='confirmed' if ok else 'unknown',evidence=json.dumps({'status':status,'scope':scope}))
    observation = next(o for o in q.publication_observations(conn,pub['publication_id']) if o['observation_id']==obs_id)
    return {'schema_version':1,'action':'publication verify','exit_code':0 if ok else 5,
        'status':status if ok else 'not_verified','verification_status':status,'publication_id':pub['publication_id'],
        'observation_id':obs_id,'verified_at':observation['verified_at'],'scope':scope,'checks':checks,'reasons':reasons,
        'trust':pub['trust'],'historical_status':pub['historical_status'],'historical_publication_proven':False,
        'schedule':'not_verified','error':None if ok else {'code':'not_verified','message':'Недостаточные свидетельства или несоответствие'}}


def verify_publication(*, project_slug, publication_id, scope='current_state', db_path=None,
                       workvault=None, cache_dir=None, client=None):
    import plan_archive  # initializes existing MofsIndex import path
    from plan_batch import _connect, _db
    from mofs_index.plan import query as q
    from mofs_index.plan.selectors import resolve_selector, PlanQueryError
    conn = None
    try:
        if scope not in ('current_state','historical_version'):
            raise PlanQueryError('invalid_verification_scope',2)
        conn = _connect(_db(db_path=db_path))
        plan = q.resolve_plan(conn,project_slug)
        if 'plan_id' not in plan:
            raise PlanQueryError('project_not_found')
        pub = resolve_selector(conn,plan['plan_id'],{'kind':'publication','publication_id':publication_id})
        readonly = ReadOnlyConfluenceClient.from_client(client) if client is not None else ReadOnlyConfluenceClient()
        if pub['source_namespace'].startswith('confluence:'):
            from urllib.parse import urlsplit
            if urlsplit(readonly.base_url).netloc != pub['source_namespace'].split(':',1)[1]:
                raise PlanQueryError('publication_namespace_mismatch')
        return _verify(conn,pub,readonly,scope)
    except PlanQueryError as exc:
        return {'schema_version':1,'action':'publication verify','exit_code':exc.exit_code,'status':'not_verified',
            'error':{'code':exc.code,'message':exc.code}}
    except Exception as exc:
        return {'schema_version':1,'action':'publication verify','exit_code':5,'status':'not_verified',
            'error':{'code':'verification_unavailable','message':type(exc).__name__}}
    finally:
        if conn is not None:
            conn.close()
