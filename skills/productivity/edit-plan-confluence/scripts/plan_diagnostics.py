"""Prepared-only evidence: completeness, graph, source/represented task dates.

No MPP reader or scheduler replay is imported. Local dates and live observations
are distinct sources and neither a matching root nor longest-path proves them.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from fnmatch import fnmatchcase
from zoneinfo import ZoneInfo

from prepared_plan import ROOT, fingerprint
from itogo import field_value


def policy_profile():
    return json.loads((ROOT/'references/profiles/publication-policy-v1.json').read_text())


def finding(category, code, entity, source=None, represented=None, *, model=None, observed=None):
    return dict(category=category,code=code,entity=entity,source=source,represented=represented,model=model,observed=observed)


def completeness(data, profile):
    findings=[]
    def nonimpact(path):
        return any(fnmatchcase(path,p) for p in profile['nonimpact_fields'])
    def walk(value,path):
        if isinstance(value,dict):
            quality=value.get('quality')
            absent=(quality=='missing' and value.get('reason') in profile['known_absence_reasons'])
            if quality in ('partial','missing','unsupported') and not absent:
                findings.append(finding('nonimpact_incomplete' if nonimpact(path) else 'incomplete',
                    'field_'+quality,path,value))
            if value.get('status') in ('partial','missing','unsupported'):
                findings.append(finding('nonimpact_incomplete' if nonimpact(path) else 'incomplete',
                    'nested_collection_'+value['status'],path,value))
            for k,v in value.items():
                walk(v,path+'.'+k if path else k)
        elif isinstance(value,list):
            for index,v in enumerate(value): walk(v,path+'.'+str(index))
    for name,status in data['collections'].items():
        if status['status']!='complete':
            findings.append(finding('nonimpact_incomplete' if nonimpact('collections.'+name) else 'incomplete',
                                    'collection_'+status['status'],name,status))
    for name in ('project','tasks','dependencies','resources','assignments','calendars','external_dependencies'):
        walk(data[name],name)
    for group,properties in profile['known_record_fields'].items():
        rows=[data[group]] if group=='project' else data[group]
        for index,row in enumerate(rows):
            for key in row.keys()-set(properties):
                path=group+'.'+str(index)+'.'+key
                if not nonimpact(path):findings.append(finding('incomplete','unknown_source_field',path,row[key]))
    return findings


def capability_findings(data, plugin_profile):
    issues=[]
    for task in data['tasks']:
        if task.get('id')==0:continue
        for field in ('actual_start','actual_finish','actual_duration','actual_work','stop','resume'):
            raw=task.get(field);value=field_value(raw)
            quantity=raw.get('quantity',{}) if isinstance(raw,dict) else {}
            empty=value in (None,False,0,'0','0.0','0.0h','0.0d') or quantity.get('amount') in ('0','0.0')
            if not empty and not plugin_profile.supports('task:'+field):
                issues.append(finding('unsupported_semantics','task_actuals_unrepresented:'+field,task['task_key'],raw))
    for resource in data['resources']:
        if resource.get('availability') and not plugin_profile.supports('resource:availability'):
            issues.append(finding('unsupported_semantics','resource_availability_unrepresented',resource['resource_key'],resource['availability']))
    for assignment in data['assignments']:
        for field in ('start','finish','segments'):
            value=field_value(assignment.get(field))
            if value not in (None,[]) and not plugin_profile.supports('assignment:'+field):
                issues.append(finding('unsupported_semantics','assignment_semantics_unrepresented:'+field,assignment['assignment_key'],value))
    return issues


def graph_findings(data, *, excluded=()):
    """Recompute from the derived relation set, retaining source issues separately."""
    tasks={t['task_key'] for t in data['tasks'] if 'error' not in t}
    adjacency={k:[] for k in tasks}; findings=[]
    for d in [*data['dependencies'],*data['external_dependencies']]:
        if d.get('dependency_key') in excluded: continue
        a,b=d.get('predecessor_task_key'),d.get('successor_task_key')
        if d.get('external') or d in data['external_dependencies']:
            findings.append(finding('graph','external_dependency_unresolved',d.get('dependency_key'),d));continue
        if a not in tasks or b not in tasks:
            findings.append(finding('graph','dangling_dependency',d.get('dependency_key'),d));continue
        if a==b:
            findings.append(finding('graph','self_reference',d.get('dependency_key'),d));continue
        adjacency[a].append(b)
    visiting=set();done=set()
    def visit(key,chain):
        if key in visiting:
            findings.append(finding('graph','cycle',key,chain+[key]));return
        if key in done:return
        visiting.add(key)
        for other in adjacency[key]:visit(other,chain+[key])
        visiting.remove(key);done.add(key)
    for key in sorted(tasks):visit(key,[])
    # Getter-level defects not reconstructible from relation rows cannot vanish.
    for key in ('dangling_endpoints','external_records'):
        if data['diagnose_graph'].get(key):findings.append(finding('graph',key,'source_graph',data['diagnose_graph'][key]))
    return findings


def flatten(events):
    result={}
    for node in events:
        result[node['id']]=node
        result.update(flatten(node.get('children',[])))
    return result


def compare_dates(data, conversion, *, observation=None, profile=None):
    profile=profile or policy_profile(); timezone_name=data['resolved_timezone']
    nodes=flatten(conversion['gantt']['eventsData']); findings=[]; checks=[]
    observed=(observation or {}).get('tasks',{})
    for task in data['tasks']:
        key=task.get('task_key')
        if task.get('id')==0:continue
        node=nodes.get(conversion['mappings']['tasks'].get(key),{})
        for source_field,target_field in (('start','startDate'),('finish','endDate')):
            src=field_value(task.get(source_field)); represented=node.get(target_field)
            obs=observed.get(key,{}).get(source_field)
            check={'entity':key,'milestone':task.get('milestone') is True,'field':source_field,
                   'source':src,'represented':represented,'model':None,'observed':obs,
                   'absolute_comparison':False,'delta_seconds':None,'observation_delta_seconds':None}
            try:
                if src is None or represented is None:raise ValueError('missing_date')
                a,b=datetime.fromisoformat(src.replace('Z','+00:00')),datetime.fromisoformat(represented.replace('Z','+00:00'))
                def absolute(d):
                    if d.tzinfo is not None:return d.astimezone(timezone.utc)
                    z=ZoneInfo(timezone_name)
                    aware=d.replace(tzinfo=z)
                    if aware.utcoffset()!=d.replace(tzinfo=z,fold=1).utcoffset():raise ValueError('ambiguous_local_date')
                    if aware.astimezone(timezone.utc).astimezone(z).replace(tzinfo=None)!=d:raise ValueError('nonexistent_local_date')
                    return aware.astimezone(timezone.utc)
                # Without a source zone no absolute equality is claimed, even if
                # a caller put a matching root or model result in its evidence.
                if timezone_name is not None:
                    aa,bb=absolute(a),absolute(b)
                    check.update(absolute_comparison=True,delta_seconds=(bb-aa).total_seconds())
                    if obs is not None:check['observation_delta_seconds']=(absolute(datetime.fromisoformat(obs.replace('Z','+00:00')))-aa).total_seconds()
                    deltas=[check['delta_seconds'],check['observation_delta_seconds']]
                    if any(v is not None and abs(v)>profile['date_tolerance_seconds'] for v in deltas):
                        findings.append(finding('date_mismatch','task_date_mismatch',key+':'+source_field,src,represented,observed=obs))
            except (ValueError,TypeError,KeyError):
                findings.append(finding('incomplete','date_missing_or_ambiguous',key+':'+source_field,src,represented,observed=obs))
            checks.append(check)
    return findings,checks


def diagnose(prepared, conversion, *, plugin_profile, excluded=(), observation=None):
    data=prepared.normalized_data; profile=policy_profile()
    findings=completeness(data,profile)+graph_findings(data,excluded=excluded)
    if plugin_profile is not None:findings+=capability_findings(data,plugin_profile)
    if data['resolved_timezone'] is None:
        findings.append(finding('timezone','timezone_required','source_dates',None))
    if plugin_profile is None or not plugin_profile.document['plugin'].get('version'):
        findings.append(finding('plugin_unknown','plugin_profile_required','plugin'))
    for diagnostic in conversion['diagnostics']:
        if diagnostic.get('entity') in excluded: continue
        code=diagnostic['code']
        if code=='summary_timezone_unresolved':continue # dedicated timezone row/3
        if code=='source_collection_incomplete':continue # classified by completeness
        category='graph' if code.startswith('graph_problem:') else 'unsupported_semantics'
        findings.append(finding(category,code,diagnostic.get('entity'),diagnostic.get('source'),diagnostic.get('represented')))
    dates,checks=compare_dates(data,conversion,observation=observation,profile=profile)
    findings.extend(dates)
    findings += [finding('local_unsupported','local_scheduler_prepared_unsupported','model'),
                 finding('plugin_unobserved','specific_plan_plugin_result_not_verified','plugin')]
    return {'findings':findings,'dates':checks,'profile':profile,'profile_sha256':fingerprint(profile),
            'local_model':{'status':'unsupported','reason':profile['local_scheduler'],
                           'capability_reference':'MppReader/references/scheduler-capability-matrix.md'},
            'plugin_observation':observation,'source_graph':data['diagnose_graph']}


def compact_receipt_diagnostics(admission, evidence_id=None):
    """Bounded CLI projection; full source/represented values stay in evidence."""
    groups={}
    for check in admission['checks']:
        key=(check['row'],check['category'],check['code'],check.get('exit_code',0),bool(check.get('accepted_deviation')))
        if key not in groups:
            groups[key]={'row':key[0],'category':key[1],'code':key[2],'exit_code':key[3],
                         'accepted_deviation':key[4],'count':0,'example_entities':[]}
        group=groups[key];group['count']+=1
        entity=str(check.get('entity',''))
        if entity not in group['example_entities'] and len(group['example_entities'])<3:
            group['example_entities'].append(entity)
    warnings={}
    for warning in admission['warnings']:
        warnings[warning['code']]=warnings.get(warning['code'],0)+1
    ref='artifact:'+evidence_id if evidence_id else None
    return ({'status':admission['schedule']['status'],'checks':[groups[k] for k in sorted(groups)],
             'limitations':admission['schedule']['limitations'],'evidence_ids':[evidence_id] if evidence_id else []},
            [{'code':code,'message':code+': '+str(count)+' проверок; подробности в свидетельстве',
              'details_ref':ref} for code,count in sorted(warnings.items())])
