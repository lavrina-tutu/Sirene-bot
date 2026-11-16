"""Executable §20.3.6.2 matrix. Findings cannot choose their own severity."""
from __future__ import annotations

from dataclasses import dataclass
from prepared_plan import fingerprint

POLICY_VERSION = 'publication-admission-v1'


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
