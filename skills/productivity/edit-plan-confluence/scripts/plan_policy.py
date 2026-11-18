"""Executable §20.3.6.2 matrix. Findings cannot choose their own severity."""
from __future__ import annotations

from dataclasses import dataclass
from prepared_plan import fingerprint

POLICY_VERSION = 'publication-admission-v1'


def owner_decision():
    """Versioned owner evidence; unavailable/tampered evidence fails closed."""
    import hashlib, json
    from prepared_plan import ROOT
    policy = json.loads((ROOT/'references/profiles/owner-decision-v1.json').read_text())
    def verify(path, expected):
        evidence = (ROOT/path).resolve()
        if ROOT.resolve() not in evidence.parents or not evidence.is_file() or hashlib.sha256(evidence.read_bytes()).hexdigest() != expected:
            raise ValueError('owner_decision_evidence_integrity')
        return {'path': str(evidence), 'sha256': expected}
    verify(policy['evidence_path'], policy['evidence_sha256'])
    if 'round_the_clock_calendar' in policy or 'round_the_clock_calendar_evidence' in policy:
        receipt = policy.get('round_the_clock_calendar_evidence')
        if (policy.get('round_the_clock_calendar') != 'publish_as_is' or not isinstance(receipt,dict)
                or set(receipt) != {'decision_id','evidence_path','evidence_sha256'}
                or receipt.get('decision_id') != 'owner-20261118-round-the-clock-calendar'):
            raise ValueError('round_the_clock_owner_decision_invalid')
        verified = verify(receipt['evidence_path'], receipt['evidence_sha256'])
        policy['round_the_clock_calendar_evidence_verified'] = verified
    return policy


def round_the_clock_calendars(data):
    """Return exact, fully enumerated source calendars encoded as seven 24/7 days."""
    from copy import deepcopy
    from itogo import field_value
    required = {'MONDAY','TUESDAY','WEDNESDAY','THURSDAY','FRIDAY','SATURDAY','SUNDAY'}
    collections = data.get('collections', {})
    cstate = collections.get('calendars', {})
    rows = data.get('calendars')
    if (not isinstance(rows,list) or cstate.get('status') != 'complete'
            or cstate.get('enumeration_complete') is not True
            or cstate.get('count') != len(rows) or cstate.get('record_count') != len(rows)
            or cstate.get('error_count') != 0 or any('error' in c for c in rows)):
        return {}
    keys=[c.get('calendar_key') for c in rows if isinstance(c,dict)]
    if len(keys)!=len(rows) or any(not isinstance(k,str) or not k for k in keys) or len(set(keys))!=len(keys):
        return {}
    result = {}
    for cal in rows:
        key = cal.get('calendar_key')
        days = cal.get('weekdays')
        quality = cal.get('weekdays_quality')
        quality = quality.get('status') if isinstance(quality,dict) else quality
        if (not isinstance(key,str) or not key or key in result or not isinstance(days,list)
                or quality not in ('ok','complete') or len(days) != 7):
            continue
        if cal.get('quality_issues') not in (None,[]):
            continue
        day_names = [d.get('day') for d in days if isinstance(d,dict)]
        if len(day_names) != 7 or set(day_names) != required or len(set(day_names)) != 7:
            continue
        valid = True
        for day in days:
            if day.get('quality_issues') not in (None,[]):
                valid=False;break
            typ, working, intervals = (field_value(day.get(k)) for k in ('day_type','working','intervals'))
            def field_ok(name):
                raw=day.get(name)
                return isinstance(raw,dict) and raw.get('quality')=='ok' and field_value(raw) is not None
            if (typ != 'WORKING' or working is not True or not field_ok('day_type')
                    or not field_ok('working') or not field_ok('intervals')
                    or not isinstance(intervals,list) or len(intervals) != 1):
                valid=False;break
            window=intervals[0]
            if not isinstance(window,dict): valid=False;break
            start,end=field_value(window.get('start')),field_value(window.get('end'))
            sq=window.get('start',{}).get('quality') if isinstance(window.get('start'),dict) else None
            eq=window.get('end',{}).get('quality') if isinstance(window.get('end'),dict) else None
            if start not in ('00:00','00:00:00') or end not in ('00:00','00:00:00') or sq!='ok' or eq!='ok':
                valid=False;break
        if not valid: continue
        parent_raw=cal.get('parent_key'); parent=field_value(parent_raw); parent_uid=cal.get('parent_uid')
        parent_absent=(parent is None and isinstance(parent_raw,dict)
                       and parent_raw.get('quality')=='missing' and parent_raw.get('reason')=='not_set'
                       and parent_uid is None)
        if not parent_absent: continue
        # Explicit quality and empty enumeration are required; absence is not proof.
        ok=True
        for name in ('exceptions','work_weeks'):
            values=cal.get(name); q=cal.get(name+'_quality')
            if values != [] or not isinstance(q,dict) or q.get('status')!='complete' or q.get('count')!=0: ok=False
        if not ok: continue
        result[key]=deepcopy(cal)
    return {key:result[key] for key in sorted(result)}



@dataclass(frozen=True)
class AdmissionRule:
    row: int
    category: str
    code: int
    consent: bool = False
    warning: bool = False


# One entry per normative row, in the document's order.
MATRIX = (
    AdmissionRule(1, 'complete', 0),
    AdmissionRule(2, 'nonimpact_incomplete', 0, warning=True),
    AdmissionRule(3, 'incomplete', 5, consent=True),
    AdmissionRule(4, 'timezone', 3),
    AdmissionRule(5, 'local_unsupported', 0, warning=True),
    AdmissionRule(6, 'plugin_unobserved', 0, warning=True),
    AdmissionRule(7, 'plugin_unknown', 5),
    AdmissionRule(8, 'unsupported_semantics', 5, consent=True),
    AdmissionRule(9, 'graph', 5, consent=True),
    AdmissionRule(10, 'external_resolved', 0),
    AdmissionRule(11, 'date_mismatch', 5, consent=True),
    AdmissionRule(12, 'input', 5),
    AdmissionRule(13, 'binding', 3),
    AdmissionRule(14, 'identity', 3),
    AdmissionRule(15, 'archive', 5),
    AdmissionRule(16, 'attachment', 5),
    AdmissionRule(17, 'storage', 5),
    AdmissionRule(18, 'network_unknown', 5),
    AdmissionRule(19, 'target_conflict', 4),
    AdmissionRule(20, 'display_only', 0, warning=True),
)
BY_CATEGORY = {r.category: r for r in MATRIX}


def evaluate(findings, *, proposals=(), accepted_deviations=()):
    """Consent only exposes an addressable next step; it never suppresses a check.

    Transformed representations are diagnosed again by the caller. A date
    deviation can be accepted for precisely the saved finding fingerprint.
    """
    blockers, warnings, checks = [], [], []
    accepted = set(accepted_deviations)
    for original in findings:
        finding = dict(original)
        rule = BY_CATEGORY.get(finding.get('category'), BY_CATEGORY['incomplete'])
        finding.update(row=rule.row, finding_sha256=fingerprint(original))
        code = rule.code
        if finding.get('code') in ('expected_hash_mismatch','binding_conflict','mapping_revision_conflict',
                                    'mapping_revision_scope_mismatch','mapping_revision_inactive','foreign_page_change'):
            code = 4
        concrete = any(p.get('finding_sha256') == finding['finding_sha256']
                       and p.get('action') in ('exclude_dependency','accept_date_deviation')
                       and p.get('losses') for p in proposals)
        if code and rule.consent and concrete:
            code = 3
        if rule.category == 'date_mismatch' and finding['finding_sha256'] in accepted:
            code = 0
            finding['accepted_deviation'] = True
            warnings.append(finding)
        elif code:
            finding['exit_code'] = code
            blockers.append(finding)
        elif rule.warning:
            warnings.append(finding)
        checks.append(finding)
    rc = 4 if any(b['exit_code']==4 for b in blockers) else 5 if any(b['exit_code']==5 for b in blockers) else 3 if blockers else 0
    schedule = 'mismatch' if any(f['category']=='date_mismatch' and not f.get('accepted_deviation') for f in checks) else (
        'accepted_deviation' if any(f.get('accepted_deviation') for f in checks) else 'not_verified')
    # schedule:verified is assigned only by a complete, bound live observation.
    return {'policy_revision': POLICY_VERSION, 'allowed': not blockers, 'exit_code': rc,
            'status': 'prepared' if not blockers else 'needs_decision' if rc==3 else 'conflict' if rc==4 else 'failed',
            'blockers': blockers, 'warnings': warnings, 'checks': checks,
            'schedule': {'status':schedule, 'checks': checks,
                         'limitations':['local_scheduler_not_run','plan_plugin_result_not_verified'], 'evidence_ids':[]}}
