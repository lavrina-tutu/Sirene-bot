"""Versioned, evidence-bound installed-plugin contract; no CLI or network."""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

from prepared_plan import ROOT, fingerprint


@dataclass(frozen=True)
class PluginProfile:
    document: dict

    @classmethod
    def load(cls, path=None, *, evidence_root=None, installed_version=None):
        if path is None:
            from env import load_settings
            selected = load_settings().values.get('PLUGIN_PROFILE')
            if selected != 'installed-gantt-profile':
                raise ValueError('unknown_plugin_profile_selection')
            path = ROOT / 'references/profiles' / (selected + '.json')
        profile = cls(json.loads(Path(path).read_text()))
        profile.validate(evidence_root=evidence_root, installed_version=installed_version)
        return profile

    def validate(self, *, evidence_root=None, installed_version=None):
        import jsonschema
        schema = json.loads((ROOT / 'references/profiles/plugin-profile.schema.json').read_text())
        jsonschema.validate(self.document, schema)
        d = self.document
        if installed_version is not None and d['plugin']['version'] != installed_version:
            raise ValueError('installed_plugin_version_mismatch')
        root = Path(evidence_root or ROOT).resolve()
        evidence = d['evidence']
        documents = {}
        for key, item in evidence.items():
            p = (root / item['path']).resolve()
            if root not in p.parents or not p.is_file() or hashlib.sha256(p.read_bytes()).hexdigest() != item['sha256']:
                raise ValueError('plugin_evidence_integrity:' + key)
            if p.suffix == '.json':
                documents[key] = json.loads(p.read_text())
        for cap in d['capabilities'].values():
            if cap['status'] == 'tested_supported':
                if not d['plugin']['version'] or not cap['evidence']:
                    raise ValueError('supported_capability_without_version_or_evidence')
            if any(key not in evidence for key in cap['evidence']):
                raise ValueError('unknown_capability_evidence')
        if d['plugin']['key'] == 'com.ricksoft-inc.plugins.gantt-chart-planner-for-confluence':
            matching = [w for w in documents.values() if w.get('frontend_build')
                        and 'frontend-build:'+w['frontend_build'] == d['plugin']['version']
                        and w.get('asset_sha256') == d['plugin']['asset_sha256']
                        and w.get('confluence_version') == d['confluence_version']]
            if not matching:
                raise ValueError('installed_version_without_matching_metadata_evidence')
        corrective = {'publication:source_snapshot_dates','calendar:inheritance','calendar:bindings:tasks','calendar:bindings:resources',
            'calendar:bindings:assignments','resource:availability','assignment:start','assignment:finish',
            'task:segments','task:active','dependency:summary_endpoint','resource:default_availability','assignment:coincident_task_interval'}
        for name, capability in d['capabilities'].items():
            separated = name.startswith(('display:', 'schedule:'))
            needs_behavior = (separated or name in corrective or name.startswith(('task:actual_', 'task:task_type:', 'task:constraint:')))
            if (needs_behavior and capability['status'] == 'tested_supported'
                    and d['plugin']['key'] == 'com.ricksoft-inc.plugins.gantt-chart-planner-for-confluence'):
                witnesses = [documents[k] for k in capability['evidence'] if k in documents]
                def proves(w):
                    checks = w.get('checks', {})
                    return (name in w.get('capabilities', []) and w.get('status') == 'passed'
                        and w.get('assertion_kind') == 'supported' and bool(checks)
                        and all(c.get('passed') is True and c.get('expected') == c.get('actual') for c in checks.values())
                        and 'frontend-build:'+str(w.get('build')) == d['plugin']['version']
                        and w.get('asset_sha256') == d['plugin']['asset_sha256']
                        and w.get('confluence_version') == d['confluence_version']
                        and w.get('input_sha256') is not None
                        and w.get('input_sha256') == w.get('browser_received_sha256'))
                if not any(proves(w) for w in witnesses):
                    raise ValueError('capability_without_behavior_control:'+name)
                if separated:
                    layer = name.split(':', 1)[0]
                    if (capability.get('layer') != layer or not capability.get('source_field')
                            or not capability.get('representation') or not capability.get('required_checks')):
                        raise ValueError('capability_scope_missing:'+name)
                    if name != ':'.join((layer, capability['source_field'], capability['representation'])):
                        raise ValueError('capability_scope_mismatch:'+name)
                    # Status/custom columns live in the wrapper, not the engine.
                    def scoped(w):
                        return (proves(w) and (layer != 'schedule' or w.get('schedule_verification', {}).get('status') == 'verified')
                            and d['plugin'].get('wrapper_asset_sha256') is not None
                            and w.get('wrapper_asset_sha256') == d['plugin']['wrapper_asset_sha256']
                            and all(k in w.get('checks', {}) for k in capability['required_checks']))
                    if not any(scoped(w) for w in witnesses):
                        raise ValueError('capability_without_scoped_wrapper_proof:'+name)
        relation_names = {'FS':'EndToStart','SS':'StartToStart','FF':'EndToEnd','SF':'StartToEnd'}
        for kind, codes in d['codes'].items():
            for name, code in codes.items():
                capability = d['capabilities'].get(kind+':'+name,{})
                if capability.get('status') != 'tested_supported':
                    continue
                witnesses = [documents[key] for key in capability['evidence'] if key in documents]
                if kind == 'relation':
                    supported = any(w.get('relation_codes',{}).get(relation_names[name]) == code for w in witnesses)
                else:
                    supported = any(any(dep.get('lagUnit') == code for dep in w.get('dependencies',[])) for w in witnesses)
                if not supported:
                    raise ValueError('plugin_code_without_matching_observation:'+kind+':'+name)
        return self

    @property
    def fingerprint(self):
        return fingerprint(self.document)

    def supports(self, name):
        return self.document['capabilities'].get(name, {}).get('status') == 'tested_supported'

    def supports_field(self, field, *, layer, representation):
        """Display evidence never grants scheduling support, or another method."""
        cap = self.document['capabilities'].get(layer+':'+field+':'+representation, {})
        return (cap.get('status') == 'tested_supported' and cap.get('layer') == layer
                and cap.get('source_field') == field and cap.get('representation') == representation)

    def code(self, kind, name):
        if not isinstance(name, str) or not self.supports(kind + ':' + name):
            return None
        return self.document['codes'].get(kind, {}).get(name)
