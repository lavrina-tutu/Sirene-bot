from pathlib import Path
import hashlib, json, shutil, subprocess, os, xml.etree.ElementTree as ET

H = Path('/home/tkachenkoav/hermes-workspace')
S = H/'skills/productivity/edit-plan-confluence'
T = Path(Path('/tmp/editplan-fix4-root').read_text())
F = T/'final'
R = F/'reports'
R.mkdir(parents=True, exist_ok=True)
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def dump(p, v):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(v, ensure_ascii=False, indent=2)+'\n')

old = json.loads((S/'references/implementation/20261116/stage-13-fix2/final/reports/external-checks.json').read_text())
packages = []
for index, item in enumerate(old['restoration_packages']):
    manifest = Path(item['manifest'])
    assert sha(manifest) == item['sha256']
    data = json.loads(manifest.read_text())
    base = manifest.parent
    out = T/'restoration'/str(index)
    patched = out/'patch'
    aftercopy = out/'after-copy'
    patched.mkdir(parents=True)
    aftercopy.mkdir()
    rows = []
    for row in data['files']:
        name = row.get('relative_path') or row.get('path')
        src = base/'after'/name
        assert src.is_file() and sha(src) == row['after_sha256'], (manifest, name)
        dest = aftercopy/name
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dest)
        before = base/'before'/name
        if row.get('before_sha256'):
            assert sha(before) == row['before_sha256']
            dest = patched/name
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(before, dest)
        rows.append((name, src, row))
    patch = base/'changes.patch'
    run = subprocess.run(['patch','--batch','-p1','-i',str(patch)], cwd=patched, capture_output=True, text=True)
    (out/'patch.log').write_text(run.stdout+run.stderr)
    assert run.returncode == 0, (manifest, run.stdout, run.stderr)
    binaries = []
    for name, src, row in rows:
        if b'\0' in src.read_bytes():
            binaries.append(name)
            dest=patched/name;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(src,dest)
        assert sha(patched/name) == row['after_sha256'], (manifest, name)
        assert sha(aftercopy/name) == row['after_sha256']
    packages.append({'manifest':str(manifest),'sha256':sha(manifest),'files_restored':len(rows),
        'after_copy_verified':True,'patch_text_and_binary_copy_verified':True,
        'binary_after_copies':binaries,'patch_sha256':sha(patch),'patch_rc':run.returncode,'log':str(out/'patch.log')})

sources=[]
for row in old['latest_external_sources']+old.get('historical_git_component_sources',[]):
    p=Path(row['path'])
    expected=row.get('sha256') or row.get('current_git_blob_sha256')
    assert sha(p)==expected, p
    sources.append({'path':str(p),'sha256':expected,'matches':True})
commits=[]
for row in old['previous_stage_commits']:
    subprocess.run(['git','cat-file','-e',row['commit']+'^{commit}'],cwd=H,check=True)
    p=Path(row['report']);assert sha(p)==row['report_sha256']
    assert json.loads(p.read_text())['gate']=='passed'
    commits.append(row)
original=old['original_stage13'];orig=S/'references/implementation/20261116/stage-13/stage-report.json'
assert sha(orig)==original['report_sha256'] and json.loads(orig.read_text())['gate']=='failed'
initial=json.loads((T/'initial-state.json').read_text())
initial['base_commit']=subprocess.check_output(['git','rev-parse','HEAD'],cwd=H,text=True).strip()
dump(R/'initial-state.json',initial)
result={'gate':'pending','restoration_ok':True,'restoration_packages':packages,'latest_external_sources':sources,
    'previous_stage_commits':commits,'original_stage13':original,'runs':[]}
dump(R/'external-checks.json',result)
env={**os.environ,'PYTHONPATH':'/home/tkachenkoav/.local/lib/python3.9/site-packages'}
for component, work, selection in [('MppReader','MppReader','tests'),('MofsIndex','MofsIndex','tests/plan')]:
    out=T/'external'/component;out.mkdir(parents=True)
    cmd=['/usr/bin/python3.9','-m','pytest',selection,'-q','-o','cache_dir='+str(out/'cache'),
         '--basetemp='+str(out/'tmp'),'--junitxml='+str(out/'junit.xml')]
    with (out/'pytest.log').open('w') as log:
        run=subprocess.run(cmd,cwd=Path.home()/'USERTOOLS'/work,env=env,stdout=log,stderr=subprocess.STDOUT)
    root=ET.parse(out/'junit.xml').getroot();suite=root.find('testsuite')
    result['runs'].append({'component':component,'rc':run.returncode,'results':suite.attrib,
        'command':cmd,'cwd':str(Path.home()/'USERTOOLS'/work),'junit':str(out/'junit.xml'),'log':str(out/'pytest.log')})
    dump(R/'external-checks.json',result)
    assert run.returncode==0,(component,run.returncode)
result['gate']='passed'
dump(R/'external-checks.json',result)
print(json.dumps({'restoration_packages':len(packages),'external_runs':result['runs']},ensure_ascii=False))
