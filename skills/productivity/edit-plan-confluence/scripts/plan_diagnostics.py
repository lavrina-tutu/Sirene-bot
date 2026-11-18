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
from plan_policy import round_the_clock_calendars
from itogo import field_value


def policy_profile():
    return json.loads((ROOT/'references/profiles/publication-policy-v1.json').read_text())


def finding(category, code, entity, source=None, represented=None, *, model=None, observed=None):
    return dict(category=category,code=code,entity=entity,source=source,represented=represented,model=model,observed=observed)


def completeness(data, profile):
    """Classify original causes once; aggregate partial never grants permission.

    Quality mirrors contribute provenance only after exact source validation.
    A fully enumerated collection with only nonimpact field failures can warn;
    unknown reasons, missing rows or affecting causes remain blockers.
    """
    import re
    from copy import deepcopy
    issues, mirrors, findings, absences = {}, [], [], set()
    def canonical(path):
        return re.sub(r'\[(\d+)\]', r'.\1', path).replace('.field_quality.', '.')
    def nonimpact(path):
        return any(fnmatchcase(path,p) for p in profile['nonimpact_fields'])
    def known(reason):
        return isinstance(reason,str) and (reason in profile.get('known_failure_reasons', []) or
            any(re.fullmatch(pattern,reason) for pattern in profile.get('known_failure_reason_patterns', [])))
    def add(path, quality, reason, source, origin):
        if quality=='missing' and reason in profile['known_absence_reasons']:
            absences.add((canonical(path),quality,reason))
            return
        key=canonical(path)
        identity=(key,quality,reason)
        if identity not in issues:
            issues[identity]={'path':key,'quality':quality,'reason':reason,'source':source,'origins':[]}
        issues[identity]['origins'].append(origin)
    def walk(value,path):
        if isinstance(value,dict):
            if value.get('quality') in ('partial','missing','unsupported'):
                add(path,value['quality'],value.get('reason'),value,path)
            if value.get('status') in ('partial','missing','unsupported'):
                add(path,value['status'],value.get('reason'),value,path)
            for k,v in value.items():
                if k=='quality_issues':
                    mirrors.append((path,v));continue
                walk(v,path+'.'+k if path else k)
        elif isinstance(value,list):
            for index,v in enumerate(value):walk(v,path+'.'+str(index))
    groups=('project','tasks','dependencies','resources','assignments','calendars','external_dependencies')
    for name in groups:walk(data[name],name)
    for prefix,rows in mirrors:
        if not isinstance(rows,list):
            findings.append(finding('incomplete','invalid_quality_issues',prefix+'.quality_issues',rows));continue
        for index,row in enumerate(rows):
            if not isinstance(row,dict):
                findings.append(finding('incomplete','invalid_quality_issue',prefix+'.quality_issues.'+str(index),row));continue
            key=canonical(prefix+'.'+str(row.get('field','')))
            identity=(key,row.get('quality'),row.get('reason'))
            if identity in absences:
                continue
            if identity in issues:
                issues[identity]['origins'].append(prefix+'.quality_issues.'+str(index))
            else:
                # A mirror alone cannot prove its origin or lower its category.
                findings.append(finding('incomplete','quality_issue_origin_unresolved',key,deepcopy(row)))
    by_group={}
    for item in issues.values():
        path=item['path'];category='nonimpact_incomplete' if nonimpact(path) and known(item['reason']) else 'incomplete'
        code='field_'+item['quality'] if known(item['reason']) else 'unknown_incompleteness_reason'
        row=finding(category,code,path,deepcopy(item['source']))
        row['provenance_paths']=item['origins'][:]
        findings.append(row);by_group.setdefault(path.split('.')[0],[]).append(row)
    for name,status in data['collections'].items():
        if status.get('enumeration_complete') is False:
            findings.append(finding('incomplete','collection_enumeration_unproven','collections.'+name,deepcopy(status)))
            continue
        if status['status']=='complete':continue
        rows=(data.get(name) if name!='baseline_values' else [b for t in data['tasks'] for b in t.get('baseline_values',[])])
        causes=by_group.get(name,[])
        record_count=status.get('record_count')
        enumerated=(isinstance(rows,list) and record_count==len(rows)==status.get('count')
                    and status.get('error_count')==0 and not any('error' in row for row in rows))
        affected_rows={int(f['entity'].split('.')[1]) for f in causes
                       if len(f['entity'].split('.'))>1 and f['entity'].split('.')[1].isdigit()}
        aggregate_reason='read_errors:0;items_with_field_issues:'+str(len(affected_rows))
        if (status['status']=='partial' and enumerated and causes
                and status.get('reason')==aggregate_reason):
            for cause in causes:
                cause.setdefault('collection_provenance',[]).append({'field':'collections.'+name,'source':deepcopy(status)})
            continue
        if name=='dependencies' and status.get('reason')=='raw_relations_discarded':
            audit=data.get('diagnose_graph',{}).get('raw_relation_enumeration',{})
            raw=audit.get('value') or {};discarded=data['diagnose_graph'].get('discarded_relation_records')
            if (audit.get('quality')=='ok' and raw.get('enumeration_complete') is True
                    and raw.get('expected_count')==raw.get('observed_count')==len(raw.get('records',[]))
                    and discarded and all(r.get('disposition') in ('self_reference','dangling_endpoint','project_summary_endpoint','short_fixed_data','missing_fixed_data') for r in discarded)):
                # graph_findings classifies these exact raw records; never warn.
                continue
        findings.append(finding('incomplete','collection_'+status['status'],'collections.'+name,deepcopy(status)))
    audit=data.get('diagnose_graph',{}).get('raw_relation_enumeration')
    if audit is not None:
        raw=audit.get('value') or {}
        if (audit.get('quality')!='ok' or raw.get('enumeration_complete') is not True
                or raw.get('expected_count')!=raw.get('observed_count')
                or raw.get('observed_count')!=len(raw.get('records',[]))
                or audit.get('visible_records_match') is False):
            findings.append(finding('incomplete','raw_relation_completeness_unproven','diagnose_graph.raw_relation_enumeration',deepcopy(audit)))
    for group,properties in profile['known_record_fields'].items():
        rows=[data[group]] if group=='project' else data[group]
        for index,row in enumerate(rows):
            for key in row.keys()-set(properties):
                path=group+'.'+str(index)+'.'+key
                # An unknown field has no nonimpact proof, including mirrors.
                findings.append(finding('incomplete','unknown_source_field',path,deepcopy(row[key])))
    return findings


def capability_findings(data, plugin_profile, conversion=None):
    issues=[]
    from mpp_calendar import default_availability_equivalent, coincident_assignment_interval
    tasks={t['task_key']:t for t in data['tasks'] if 'error' not in t}
    nodes = flatten((conversion or {}).get('gantt', {}).get('eventsData', []))
    round_clock = round_the_clock_calendars(data)
    from plan_policy import owner_decision
    round_clock_owner = owner_decision() if round_clock else {}
    root_key = (conversion or {}).get('summary', {}).get('root_task_key')
    for task in data['tasks']:
        if task.get('id')==0:continue
        if plugin_profile.supports('publication:source_snapshot_dates'):
            from mpp_convert import SNAPSHOT_COLUMN, snapshot_text
            ident = (conversion or {}).get('mappings', {}).get('tasks', {}).get(task['task_key'])
            node = nodes.get(ident, {})
            gantt = (conversion or {}).get('gantt', {})
            visible = all(any(c.get('id')==SNAPSHOT_COLUMN and c.get('hidden') is False
                for c in gantt.get('initialState',{}).get(mode,{}).get('columns',[])) for mode in ('view','edit'))
            expected_snapshot = snapshot_text(task)
            if (round_clock and round_clock_owner.get('round_the_clock_calendar') == 'publish_as_is'
                    and round_clock_owner.get('round_the_clock_calendar_evidence_verified')
                    and task.get('task_key') == root_key):
                note = ('В исходнике круглосуточный календарь (7 дней, 00:00–00:00). '
                    'Даты показаны снимком MPP без пересчёта; исходные интервалы сохранены в архиве.'
                    + '\nКалендари: ' + ', '.join(round_clock))
                expected_snapshot = snapshot_text(task, note)
            exact = (node.get('manuallyScheduled') is True and node.get('skipNonWorkingTimeWhenSchedulingManually') is False
                and node.get(SNAPSHOT_COLUMN)==expected_snapshot and visible
                and gantt.get('customColumns',{}).get(SNAPSHOT_COLUMN,{}).get('type')=='customtext'
                and node.get('startDate')==field_value(task.get('start')) and node.get('endDate')==field_value(task.get('finish')))
            from itogo import quantity_minutes
            duration, _, _ = quantity_minutes(task.get('duration'), data['project'], working_only=True)
            if task.get('milestone') is True and duration == 0 and field_value(task.get('start')) != field_value(task.get('finish')):
                from plan_policy import owner_decision
                decision = owner_decision()
                if decision.get('milestone_interval_conflict') == 'publish_collapsed':
                    issues.append(finding('display_only','source_milestone_interval_collapsed',task['task_key'],
                        {'start':task.get('start'),'finish':task.get('finish'),'duration':task.get('duration'),'milestone':True},
                        {'reason':'Веха публикуется как есть; плагин рисует её точкой на одну дату, интервал сжат при отображении; обе исходные даты сохранены в архиве (решение владельца).','owner_decision':decision['decision_id']}))
                else:
                    issues.append(finding('unsupported_semantics','source_milestone_interval_conflict',task['task_key'],
                        {'start':task.get('start'),'finish':task.get('finish'),'duration':task.get('duration'),'milestone':True},
                        {'reason':'Installed plugin collapses zero-duration milestone to one date; no source date or duration is invented.'}))
            row = finding('display_only' if exact else 'unsupported_semantics',
                'source_snapshot_dates' if exact else 'source_snapshot_display_unverified',task['task_key'],task.get('task_mode'),
                {'source_mode':snapshot_text(task),'plugin_recalculation':False,'verified':exact})
            row['classification'] = 'display-only' if exact else 'schedule-affecting'
            issues.append(row)
        for field in ('actual_start','actual_finish','actual_duration','actual_work','stop','resume'):
            raw=task.get(field);value=field_value(raw)
            quantity=raw.get('quantity',{}) if isinstance(raw,dict) else {}
            empty=value in (None,False,0,'0','0.0','0.0h','0.0d') or quantity.get('amount') in ('0','0.0')
            if not empty:
                # Describe an exact display without presenting it as calendar proof.
                from mpp_convert import SOURCE_COLUMNS, source_value_text
                column = SOURCE_COLUMNS[field][0]
                ident = (conversion or {}).get('mappings', {}).get('tasks', {}).get(task['task_key'])
                value = nodes.get(ident, {}).get(column)
                display = {'method':'customtext', 'field':column, 'value':value,
                    'source_match':value == source_value_text(raw),
                    'profile_supported':plugin_profile.supports_field(field, layer='display', representation='customtext'),
                    'calendar_semantics':'not_verified'}
                node = nodes.get(ident, {})
                from itogo import quantity_minutes, decimal_value
                minutes, _, reason = quantity_minutes(task.get('duration'), data['project'], working_only=True)
                day = decimal_value(field_value(data['project'].get('minutes_per_day')))
                duration = decimal_value(node.get('duration'))
                planned = (node.get('startDate') == field_value(task.get('start'))
                    and node.get('endDate') == field_value(task.get('finish'))
                    and not reason and minutes is not None and day is not None and day > 0
                    and duration is not None and duration * day == minutes)
                gantt = (conversion or {}).get('gantt', {})
                column_type = gantt.get('customColumns', {}).get(column, {}).get('type')
                visible = all(any(c.get('id') == column and c.get('hidden') is False
                    for c in gantt.get('initialState', {}).get(mode, {}).get('columns', []))
                    for mode in ('view', 'edit'))
                native_fields = ('actualStart', 'actualEnd', 'actualFinish', 'actualDuration',
                    'actualStartDate', 'actualEndDate', 'actualFinishDate', 'actualEffort',
                    'actualWork', 'stopDate', 'resumeDate', 'stop', 'resume',
                    'actual_start', 'actual_finish', 'actual_duration', 'actual_work')
                isolated = not any(k in node for k in native_fields)
                display.update(planned_schedule_preserved=planned, visible=visible,
                    isolated_from_schedule=isolated)
                admissible = (display['source_match'] and display['profile_supported']
                    and column_type == 'customtext' and visible and isolated and planned)
                row = finding('display_only' if admissible else 'unsupported_semantics',
                    ('task_actuals_display_only:' if admissible else 'task_actuals_unrepresented:')+field,
                    task['task_key'], raw, display)
                row['classification'] = 'display-only' if admissible else 'schedule-affecting'
                issues.append(row)
    for resource in data['resources']:
        if (resource.get('availability') and not plugin_profile.supports('resource:availability')
                and not (plugin_profile.supports('resource:default_availability') and default_availability_equivalent(resource,data))):
            issues.append(finding('unsupported_semantics','resource_availability_unrepresented',resource['resource_key'],resource['availability']))
    for assignment in data['assignments']:
        from mpp_convert import unassigned_source, unassigned_text, UNASSIGNED_COLUMN
        if unassigned_source(assignment, tasks):
            from plan_policy import owner_decision
            decision = owner_decision()
            ident = (conversion or {}).get('mappings', {}).get('tasks', {}).get(assignment['task_key'])
            node = nodes.get(ident, {})
            gantt = (conversion or {}).get('gantt', {})
            text = unassigned_text(assignment)
            matching = [a for a in data['assignments'] if a.get('task_key') == assignment['task_key'] and unassigned_source(a, tasks)]
            expected = '\n'.join(unassigned_text(a) for a in matching)
            visible = all(any(c.get('id') == UNASSIGNED_COLUMN and c.get('hidden') is False
                for c in gantt.get('initialState', {}).get(mode, {}).get('columns', [])) for mode in ('view','edit'))
            native = [a for a in gantt.get('assignmentsData', [])
                if a.get('id') == (conversion or {}).get('mappings', {}).get('assignments', {}).get(assignment['assignment_key'])]
            planned = node.get('startDate') == field_value(tasks[assignment['task_key']].get('start')) and node.get('endDate') == field_value(tasks[assignment['task_key']].get('finish'))
            admissible = (decision['unassigned_resources'] == 'preserve_source_display' and planned
                and node.get(UNASSIGNED_COLUMN) == expected and visible and not native
                and gantt.get('customColumns', {}).get(UNASSIGNED_COLUMN, {}).get('type') == 'customtext')
            issues.append(finding('display_only' if admissible else 'unsupported_semantics',
                'unassigned_resource_source_display' if admissible else 'unassigned_resource_display_unverified',
                assignment['assignment_key'], assignment,
                {'message':'назначение без ресурса публикуется как есть (resource_uid: missing)',
                 'resource':None,'text':text,'verified':admissible,'owner_decision':decision}))
            if admissible:
                continue
        for field in ('start','finish','segments'):
            value=field_value(assignment.get(field))
            equivalent=(plugin_profile.supports('assignment:coincident_task_interval')
                        and coincident_assignment_interval(assignment,tasks.get(assignment.get('task_key'))))
            if value not in (None,[]) and not plugin_profile.supports('assignment:'+field) and not equivalent:
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
    for index,record in enumerate(data['diagnose_graph'].get('discarded_relation_records',[])):
        findings.append(finding('graph','raw_relation_'+str(record.get('disposition','unknown')),
            'diagnose_graph.discarded_relation_records.'+str(index),record))
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
    if plugin_profile is not None:findings+=capability_findings(data,plugin_profile,conversion)
    if data['resolved_timezone'] is None:
        findings.append(finding('timezone','timezone_required','source_dates',None))
    if plugin_profile is None or not plugin_profile.document['plugin'].get('version'):
        findings.append(finding('plugin_unknown','plugin_profile_required','plugin'))
    round_clock = {}
    round_clock_decision = None
    round_clock_diagnostics = {}
    if plugin_profile is not None:
        from plan_policy import owner_decision
        round_clock = round_the_clock_calendars(data)
        if round_clock and plugin_profile.supports('publication:source_snapshot_dates'):
            try: round_clock_decision = owner_decision()
            except (OSError,ValueError,KeyError,TypeError): round_clock_decision = None
    root_ok = False
    if (round_clock and round_clock_decision
            and round_clock_decision.get('round_the_clock_calendar') == 'publish_as_is'
            and round_clock_decision.get('round_the_clock_calendar_evidence_verified')
            and conversion.get('summary',{}).get('root_task_key')):
        from mpp_convert import SNAPSHOT_COLUMN, snapshot_text, flatten_events
        root_key=conversion['summary']['root_task_key']
        root_task=next((t for t in data['tasks'] if t.get('task_key')==root_key and 'error' not in t),None)
        root_id=conversion.get('mappings',{}).get('tasks',{}).get(root_key)
        roots=conversion.get('gantt',{}).get('eventsData',[])
        nodes={ident:node for root in roots for ident,node in flatten_events(root).items()}
        node=nodes.get(root_id,{})
        note=('В исходнике круглосуточный календарь (7 дней, 00:00–00:00). '
            'Даты показаны снимком MPP без пересчёта; исходные интервалы сохранены в архиве.'
            + '\nКалендари: ' + ', '.join(round_clock))
        visible=all(any(c.get('id')==SNAPSHOT_COLUMN and c.get('hidden') is False
            for c in conversion.get('gantt',{}).get('initialState',{}).get(mode,{}).get('columns',[]))
            for mode in ('view','edit'))
        root_ok=(root_task is not None and node.get(SNAPSHOT_COLUMN)==snapshot_text(root_task,note)
            and node.get('manuallyScheduled') is True
            and node.get('skipNonWorkingTimeWhenSchedulingManually') is False and visible)
    if root_ok:
        from copy import deepcopy
        for diagnostic in conversion['diagnostics']:
            key=diagnostic.get('entity'); calendar=round_clock.get(key)
            if calendar is None or key in excluded: continue
            code=diagnostic.get('code'); source=diagnostic.get('source')
            matched_day=next((d for d in calendar.get('weekdays',[]) if source == d),None)
            matched_window=next((w for d in calendar.get('weekdays',[])
                for w in (d.get('intervals',{}).get('value') or []) if source == w),None)
            eligible=(code=='calendar_intervals_unsupported' and matched_day is not None)
            eligible |= (code=='calendar_interval_invalid' and plugin_profile.supports('calendar:intervals')
                and matched_window is not None)
            if eligible:
                round_clock_diagnostics.setdefault(key,[]).append(deepcopy(diagnostic))
    for key, records in sorted(round_clock_diagnostics.items()):
        evidence=round_clock_decision['round_the_clock_calendar_evidence']
        verified=round_clock_decision['round_the_clock_calendar_evidence_verified']
        findings.append(finding('display_only','source_calendar_24h_publish_as_is',key,
            {'calendar':round_clock[key],'diagnostics':records},
            {'description':'Исходный круглосуточный календарь сохранён в архиве; даты задач показаны снимком MPP без пересчёта.',
             'decision_id':evidence['decision_id'],'evidence_path':verified['path'],'evidence_sha256':verified['sha256'],
             'calendar_keys':list(round_clock),'snapshot_verified':root_ok}))
    for diagnostic in conversion['diagnostics']:
        if diagnostic in [item for rows in round_clock_diagnostics.values() for item in rows]:
            continue
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
    friendly={'source_calendar_24h_publish_as_is':'Круглосуточный календарь показан как снимок MPP без пересчёта'}
    return ({'status':admission['schedule']['status'],'checks':[groups[k] for k in sorted(groups)],
             'limitations':admission['schedule']['limitations'],'evidence_ids':[evidence_id] if evidence_id else []},
            [{'code':code,'message':friendly.get(code,code)+': '+str(count)+' проверок; подробности в свидетельстве',
              'details_ref':ref} for code,count in sorted(warnings.items())])
