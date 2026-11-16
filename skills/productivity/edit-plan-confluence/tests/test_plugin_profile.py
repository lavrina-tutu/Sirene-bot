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
