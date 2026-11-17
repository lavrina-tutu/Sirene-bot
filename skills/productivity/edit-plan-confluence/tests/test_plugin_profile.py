"""Version/evidence integrity, unknown capability and deployed-profile contract."""
from copy import deepcopy
from pathlib import Path
import hashlib
import json
import pytest
from plugin_profile import PluginProfile


def test_profile_codes_only_verified_capabilities(stage08_profile):
    stage08_profile.validate()
    assert stage08_profile.code('relation','FS')==12
    assert stage08_profile.code('relation','unknown') is None
    assert stage08_profile.code('relation',None) is None
    stage08_profile.document['capabilities']['relation:FS']['status']='not_verified'
    assert stage08_profile.code('relation','FS') is None


@pytest.mark.parametrize('kind',['hash','version','evidence','claim','shape','code'])
def test_profile_rejects_unverified_contract(stage08_profile,tmp_path,kind):
    d=stage08_profile.document
    if kind=='hash':(tmp_path/'test-only-evidence.json').write_text('tampered')
    if kind=='version':
        with pytest.raises(ValueError,match='version_mismatch'):
            stage08_profile.validate(installed_version='other')
        return
    if kind=='evidence':d['capabilities']['relation:FS']['evidence']=['missing']
    if kind=='claim':d['capabilities']['relation:FS']['evidence']=[]
    if kind=='shape':d['codes']['relation']['UNKNOWN']=0
    if kind=='code':d['codes']['relation']['FS']=99
    with pytest.raises(Exception):stage08_profile.validate()


def test_installed_profile_has_only_evidence_bound_claims():
    p=PluginProfile.load()
    assert p.document['id']=='installed-gantt-profile'
    # The final profile pins the installed frontend build; unknown release metadata stays explicit.
    assert p.document['plugin']['version']
    assert p.document['evidence']
    for kind,codes in p.document['codes'].items():
        for name in codes:
            assert p.supports(kind+':'+name)


def test_context_installed_profiles_from_registry(tmp_path):
    from plan_context import PlanContext
    ctx=PlanContext.resolve(db=tmp_path/'db',workvault=tmp_path/'WorkVault',cache_dir=tmp_path/'cache')
    profiles=ctx.snapshot()['profiles']
    assert profiles['SUMMARY_PROFILE']['status']=='available'
    assert profiles['PLUGIN_PROFILE']['status']=='available'
    assert profiles['PLUGIN_PROFILE']['sha256']==hashlib.sha256((Path(__file__).parents[1]/'references/profiles/installed-gantt-profile.json').read_bytes()).hexdigest()


@pytest.mark.parametrize('change', ['wrapper', 'field', 'method', 'checks', 'schedule'])
def test_separate_field_capability_rejects_unbound_proof(change):
    d = deepcopy(PluginProfile.load().document)
    cap = d['capabilities']['display:actual_finish:customtext']
    if change == 'wrapper':
        d['plugin']['wrapper_asset_sha256'] = '0'*64
    elif change == 'field':
        cap['source_field'] = 'actual_start'
    elif change == 'method':
        cap['representation'] = 'native'
    elif change == 'checks':
        cap['required_checks'] = ['unobserved.field']
    else:
        # Reusing a positive display witness cannot authorize native scheduling.
        d['capabilities']['schedule:actual_finish:native'] = {**cap, 'layer':'schedule', 'representation':'native'}
    with pytest.raises(ValueError, match='capability_'):
        PluginProfile(d).validate()


def test_display_capability_cannot_grant_schedule():
    p = PluginProfile.load()
    for field in ('actual_start','actual_finish','actual_duration','actual_work','stop','resume'):
        assert p.supports_field(field, layer='display', representation='customtext')
        assert not p.supports_field(field, layer='schedule', representation='native')
        assert not p.supports_field(field, layer='display', representation='native')
