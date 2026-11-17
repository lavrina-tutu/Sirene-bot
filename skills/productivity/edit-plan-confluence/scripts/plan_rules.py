"""Versioned B/C exceptions: exact reference, evidence, mapping and context.

Rules edit the derived dependency list only. Source snapshots and PreparedPlan
are never mutated. A historical consent cannot supply missing identity proof.
"""
from __future__ import annotations

from copy import deepcopy
from collections import Counter

from itogo import field_value
from prepared_plan import fingerprint, ROOT
from plan_diagnostics import graph_findings, finding
from mofs_index.plan import writer as w, query as q, identity as identity

RULES_VERSION='project-exceptions-v1'


def relation_signature(relation, project):
    lag=field_value(relation.get('lag_value')) or {}
    return {'type':relation.get('link_type'),'lag':lag.get('amount'),'units':lag.get('units'),
            'elapsed':lag.get('elapsed'),'calendar_basis':field_value(relation.get('lag_calendar'))
                or field_value(relation.get('project_lag_calendar')) or field_value(project.get('relationship_lag_calendar'))}


def task_context(task):
    # Row IDs are absent. Parent keys are compared through the exact mapping;
    # context is checked on both snapshots after that proof has been selected.
    return {k:field_value(task.get(k)) for k in ('wbs','outline_level','name','summary','milestone','parent_task_key')}


def hierarchy_keys(tasks, keys):
    required=set(keys)
    for key in keys:
        seen=set()
        while key is not None:
            if key in seen or key not in tasks:raise ValueError('rule_hierarchy_invalid')
            seen.add(key);required.add(key)
            key=field_value(tasks[key].get('parent_task_key'))
    return required


def resolve_drop_links(data, links):
    """Legacy FROM:TO addresses are valid only within this exact source hash."""
    tasks=data['tasks']; result=[]
    for source_id,target_id in links or ():
        a=[t for t in tasks if t.get('id')==source_id]
        b=[t for t in tasks if t.get('id')==target_id]
        if len(a)!=1 or len(b)!=1:raise ValueError('drop_dependency_identity_ambiguous')
        deps=[d for d in data['dependencies'] if d.get('predecessor_task_key')==a[0]['task_key']
              and d.get('successor_task_key')==b[0]['task_key']]
        if len(deps)!=1:raise ValueError('drop_dependency_relation_ambiguous')
        result.append({'source_sha256':data['source_identity']['sha256'],'predecessor_key':a[0]['task_key'],
                       'successor_key':b[0]['task_key'],'dependency_key':deps[0]['dependency_key'],
                       'expected_relation':relation_signature(deps[0],data['project'])})
    return result


def apply_rules(conn, operation_id, prepared, conversion, *, mapping_revision=None):
    op=q.get_operation(conn,operation_id); prep=q.get_preparation(conn,operation_id)
    data=prepared.normalized_data; output=deepcopy(conversion)
    results=[]; findings=[]; excluded=[]; ready=[]
    rules=q.get_project_rules(conn,prep['request']['project_slug'])
    bindings=prep['request']['rule_revisions']
    rules=[r for r in rules if any(b=={'rule_id':r['rule_id'],'revision':r['revision'],'content_sha256':r['content_sha256']}
                                    for b in bindings)]
    if len(rules)!=len(bindings):
        raise ValueError('operation_context_conflict')
    import json
    historical=json.loads((ROOT/'references/profiles/project-rules-v1.json').read_text())['historical']
    for entry in historical:
        if (entry['project_slug']==prep['request']['project_slug'] and entry['source_sha256']==data['source_identity']['sha256']
                and not any(r['rule_id']==entry['rule_id'] for r in rules)):
            results.append({'rule_id':entry['rule_id'],'rule_revision':entry['revision'],'mapping_revision_id':None,
                'status':'inactive','reason':'rule_reference_or_evidence_missing','evidence_id':None})
            recovery=entry.get('recovery')
            if recovery:
                import hashlib
                path=(ROOT/recovery['evidence_path']).resolve()
                if ROOT.resolve() not in path.parents or hashlib.sha256(path.read_bytes()).hexdigest()!=recovery['evidence_sha256']:
                    raise ValueError('historical_rule_recovery_evidence_integrity')
                # A legacy snapshot/source is provenance, not an active local
                # rule binding or a new identity confirmation.
                results[-1]['recovery']=deepcopy(recovery)
            findings.append(finding('identity','rule_reference_or_evidence_missing',entry['rule_id'],entry))
    counts=Counter(r['rule_id'] for r in rules)
    for rule in rules:
        rid=rule['rule_id']; content=rule['content']
        result={'rule_id':rid,'rule_revision':rule['revision'],'mapping_revision_id':None,
                'status':'inactive','reason':None,'evidence_id':rule['evidence_id']}
        results.append(result)
        if counts[rid]>1:
            result['reason']='rule_revision_ambiguous'
            findings.append(finding('identity','rule_revision_ambiguous',rid));continue
        if not rule['reference_snapshot_id'] or not rule['evidence_id']:
            result['reason']='rule_reference_or_evidence_missing'
            findings.append(finding('identity',result['reason'],rid));continue
        try:
            from plan_policy import POLICY_VERSION
            if content['policy_revision']!=POLICY_VERSION:raise ValueError('rule_policy_revision_mismatch')
            w.verify_artifact(conn,rule['evidence_id'],rule['evidence_sha256'])
            w.verify_snapshot(conn,rule['reference_snapshot_id'])
            reference=q.get_snapshot(conn,rule['reference_snapshot_id'])
            if reference['plan_id']!=op['plan_id']:raise ValueError('rule_project_mismatch')
            import json
            reference_data=json.loads(reference['source_json'])
            keys=(content['predecessor_key'],content['successor_key'])
            refs={t['task_key']:t for t in reference_data['tasks']}
            if any('parent_task_key' not in content['task_contexts'][k] for k in keys):
                raise ValueError('rule_hierarchy_context_missing')
            relations=[r for r in reference_data['dependencies'] if (r.get('predecessor_task_key'),r.get('successor_task_key'))==keys
                       and relation_signature(r,reference_data['project'])==content['expected_relation']]
            if len(relations)!=1 or fingerprint(content['expected_relation'])!=content['cause']['source_sha256']:
                raise ValueError('rule_reference_relation_mismatch')
            if any(any(task_context(refs[k]).get(field)!=value for field,value in content['task_contexts'][k].items()) for k in keys):
                raise ValueError('rule_reference_context_mismatch')
            required=tuple(identity.EntityRequirement('task',key) for key in sorted(hierarchy_keys(refs,keys)))
            req=w.register_identity_requirement(conn,w.IdentityRequirementSpec(operation_id,prep['revision'],op['plan_id'],
                rule['reference_snapshot_id'],prep['snapshot_id'],rid,rule['revision'],required))
            ready.append((rule,result,req,refs))
            result['pending_cause']=content['cause']['code']
        except (ValueError,w.PlanWriterError,KeyError) as exc:
            result['reason']=getattr(exc,'code',str(exc))
            findings.append(finding('identity','rule_reference_invalid',rid,result['reason']))
    # Register all requirements before selecting: sufficiency is for the whole pair.
    explicit_used=False
    explicit_scope=identity.show_revision(conn,prep['request']['project_slug'],mapping_revision)['scope'] if mapping_revision else None
    requirements={r['requirement_id']:r for r in q.get_identity_requirements(conn,operation_id)}
    for rule,result,req,refs in ready:
        try:
            argument=mapping_revision if explicit_scope==requirements[req]['scope'] else None
            selection=w.select_operation_identity(conn,w.IdentityChoiceSpec(operation_id,req,argument))
            explicit_used=explicit_used or argument is not None
            if selection['exit_code']:
                result['reason']=selection['error']['code'];findings.append(finding('identity',result['reason'],rule['rule_id']));continue
            result['mapping_revision_id']=selection['mapping_revision_id']
            result.pop('pending_cause',None)
            content=rule['content']; mapping={p['from_key']:p['to_key'] for p in selection['pairs'] if p['entity_kind']=='task'}
            old_keys=(content['predecessor_key'],content['successor_key']); keys=tuple(mapping[k] for k in old_keys)
            tasks={t['task_key']:t for t in data['tasks']}
            def context_matches(old_key,expected):
                current=task_context(tasks[mapping[old_key]])
                return all(current.get(field)==(mapping.get(value) if field=='parent_task_key' and value is not None else value)
                           for field,value in expected.items())
            if (any(not context_matches(k,content['task_contexts'][k]) for k in old_keys)
                    or any(not context_matches(k,task_context(refs[k])) for k in hierarchy_keys(refs,old_keys)-set(old_keys))):
                result['reason']='rule_task_context_changed'
                findings.append(finding('identity',result['reason'],rule['rule_id']));continue
            deps=[d for d in data['dependencies'] if (d.get('predecessor_task_key'),d.get('successor_task_key'))==keys
                  and relation_signature(d,data['project'])==content['expected_relation']]
            if len(deps)!=1:
                result['reason']='rule_relation_changed_or_ambiguous'
                findings.append(finding('identity',result['reason'],rule['rule_id']));continue
            dep=deps[0]; code=content['cause']['code']
            # Current converter and derived graph, never historical longest-path.
            current=[d for d in output['diagnostics'] if d.get('entity')==dep['dependency_key'] and d['code']==code]
            if code=='cycle':
                current=[f for f in graph_findings(data,excluded=excluded)
                         if f['code']=='cycle' and all(k in f['source'] for k in keys)]
            if code=='explicit_dependency_exclusion':
                current=[dep] if content['cause'].get('exact_source_required')==data['source_identity']['sha256'] else []
            if not current:
                # A fixed converter can prove a formerly unsupported relation is
                # now represented exactly; absence of a live date witness cannot.
                represented_id=output['mappings']['dependencies'].get(dep['dependency_key'])
                converted=any(d['id']==represented_id for d in output['gantt']['dependenciesData'])
                if code.startswith('dependency_') and converted:
                    result.update(status='not_needed',reason='correct_conversion_removed_cause');continue
                result['reason']='rule_cause_evidence_required'
                findings.append(finding('identity',result['reason'],rule['rule_id']));continue
            depid=output['mappings']['dependencies'].get(dep['dependency_key'])
            output['gantt']['dependenciesData']=[d for d in output['gantt']['dependenciesData'] if d['id']!=depid]
            output['diagnostics']=[d for d in output['diagnostics'] if d.get('entity')!=dep['dependency_key']]
            excluded.append(dep['dependency_key'])
            result.update(status='applied',reason='historical_consent_and_current_cause_verified',
                          dependency_key=dep['dependency_key'],source_relation=deepcopy(dep))
        except identity.IdentityError as exc:
            result['reason']=exc.code
            findings.append(finding('identity',exc.code,rule['rule_id']))
    if mapping_revision is not None and not explicit_used:
        findings.append(finding('identity','mapping_revision_scope_mismatch','operation'))
    # Source graph diagnostic is superseded only by a real graph recomputation.
    output['diagnostics']=[d for d in output['diagnostics'] if not d['code'].startswith('graph_problem:')]
    return output,results,findings,excluded
