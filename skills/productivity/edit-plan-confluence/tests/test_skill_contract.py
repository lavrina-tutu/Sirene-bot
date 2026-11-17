"""Stage 12: active loading, executable documentation and real CLI boundaries."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import shlex
import subprocess
import sys
from types import SimpleNamespace

import pytest
import cli
from test_plan_batch import batch_case, fake_export

S = Path(__file__).resolve().parents[1]
H = S.parents[2]
A = Path.home() / '.hermes/skills'
REFS = ('cli-contract', 'batch-and-inbox', 'identity-and-rules',
        'history-and-verification', 'testing-and-acceptance',
        'operations-and-recovery', 'cases-trisigma', 'mpp-to-gantt')


def examples():
    return [(p.name, line) for p in sorted((S/'references').glob('*.md'))
            for block in re.findall(r'```cli-example\n(.*?)```', p.read_text(), re.S)
            for line in block.splitlines() if line.strip()]


def test_active_library_loads_both_names(request):
    # Use the installed loader/interpreter, without changing its roots or code.
    code = '''
import hashlib,json,sys
from pathlib import Path
sys.path.insert(0,str(Path.home()/'hermes-agent'))
from tools.skills_tool import skill_view,skill_search_dirs
records=[]
for name in ('edit-plan-confluence','confluence-gantt-plan','productivity/edit-plan-confluence','productivity/confluence-gantt-plan'):
    result=json.loads(skill_view(name,preprocess=False))
    assert result.get('success'), result.get('error')
    path=skill_search_dirs()[1]/result['path']
    expected=Path.home()/'hermes-workspace/skills/productivity'/result['name']/'SKILL.md'
    assert path.resolve()==expected.resolve()
    assert result['content']==expected.read_text()==path.read_text()
    records.append(dict(requested_name=name,path=str(path),resolved_path=str(path.resolve()),
        sha256=hashlib.sha256(result['content'].encode()).hexdigest(),success=True))
print(json.dumps(dict(status='passed',skills=records)))
'''
    interpreter = Path.home()/'hermes-agent/.venv/bin/python'
    proc = subprocess.run([str(interpreter), '-c', code], capture_output=True, text=True, timeout=60)
    assert proc.returncode == 0, proc.stderr
    result = json.loads(proc.stdout)
    assert len(result['skills']) == 4
    root = getattr(request.config, '_acceptance_root', None)
    if root:
        (root/'reports/skill-loads.json').write_text(json.dumps(result, indent=2)+'\n')
        (root/'reports/skill-loader.stderr').write_text(proc.stderr)


def test_wrapper_has_one_canon_and_no_algorithm():
    path = A/'productivity/confluence-gantt-plan/SKILL.md'
    text = path.read_text()
    body = text.split('---', 2)[2]
    assert 'skill_view(name="edit-plan-confluence")' in body
    assert (path.parent/'../edit-plan-confluence/SKILL.md').resolve() == S/'SKILL.md'
    assert len(body.splitlines()) <= 12
    assert not re.search(r'--drop-dep|published_at|/tmp/|cli\.py|longest.path|--confirm', body)


@pytest.mark.parametrize('source,line', examples())
def test_documented_cli_examples_parse(source, line):
    argv = shlex.split(line)
    assert argv.pop(0) == 'cli.py'
    args = cli.build_parser().parse_args(argv)
    assert callable(args.func), source
    # A global after the first command is never silently accepted.
    subcommands = {'preview','diff','apply','publish','save','batch','operation','resume',
                   'history','compare','identity','publication','convert','archive-history'}
    command_index = next(i for i, value in enumerate(argv) if value in subcommands)
    assert not {'--db','--workvault','--cache-dir','--allow-live-ab'} & set(argv[command_index+1:])


def test_documented_options_cover_parser():
    text = (S/'references/cli-contract.md').read_text()
    def walk(parser):
        for action in parser._actions:
            for flag in action.option_strings:
                assert flag in ('-h','--help') or flag in text, flag
            if isinstance(action, argparse._SubParsersAction):
                for name, child in action.choices.items():
                    assert name in text
                    walk(child)
    walk(cli.build_parser())


@pytest.mark.parametrize('flag,value', [('--db','/isolated/db'),('--workvault','/isolated/WorkVault'),
                                        ('--cache-dir','/isolated/cache'),('--allow-live-ab',None)])
def test_global_parameters_cannot_follow_subcommand(flag, value, capsys):
    with pytest.raises(SystemExit) as exc:
        cli.build_parser().parse_args(['history','--project-slug','trisigma',flag]+([value] if value else []))
    assert exc.value.code == 2
    assert json.loads(capsys.readouterr().out)['exit_code'] == 2


@pytest.mark.parametrize('words,module,function,expected', [
    ('publish --mpp /inputs/p.mpp --page-id test-page --project-slug trisigma', 'pipeline','publish_plan','publish'),
    ('save --mpp /inputs/p.mpp --project-slug trisigma','plan_save','save_snapshot','save'),
    ('batch save --inbox /inputs/Inbox --project-slug trisigma --batch-id b','plan_batch','create_batch','batch'),
    ('history --project-slug trisigma --view files','plan_queries','query_history','history'),
    ('compare --project-slug trisigma --from snapshot:a --to snapshot:b','plan_queries','query_compare','compare'),
    ('batch show --batch-id b --view errors','plan_batch','show_batch','batch-errors'),
    ('resume --operation-id op','plan_decision','resume_operation','resume'),
])
def test_user_routes_dispatch_with_global_isolation(words, module, function, expected, tmp_path, monkeypatch, capsys):
    import importlib
    calls=[]
    def invoked(*args, **kwargs):
        calls.append((args, kwargs))
        payload={'schema_version':1,'exit_code':0,'action':expected,'published':False}
        return SimpleNamespace(exit_code=0,to_dict=lambda:payload) if expected in ('publish','save') else payload
    monkeypatch.setattr(importlib.import_module(module),function,invoked)
    roots=['--db',str(tmp_path/'state/index.sqlite'),'--workvault',str(tmp_path/'WorkVault'),
           '--cache-dir',str(tmp_path/'cache')]
    assert cli.main(roots+shlex.split(words)) == 0
    assert len(calls)==1
    params=calls[0][1]
    assert params['db_path']==tmp_path/'state/index.sqlite'
    assert params['workvault']==tmp_path/'WorkVault'
    assert params['cache_dir']==tmp_path/'cache'
    assert json.loads(capsys.readouterr().out)['action']==expected


@pytest.mark.archive_integration
def test_real_archive_stdout_and_receipts_redact_secrets(batch_case, monkeypatch, capsys):
    context,sources=batch_case
    monkeypatch.setattr('plan_save.run_export_full',lambda *a,**k:fake_export(sources[0]))
    canary='stage12-secret-canary-7ff59d'
    monkeypatch.setenv('CONFLUENCE_TOKEN',canary)
    argv=['--db',str(context.db),'--workvault',str(context.workvault),'--cache-dir',str(context.cache_dir),
          'save','--mpp',str(sources[0]),'--project-slug','batch']
    assert cli.main(argv)==0
    captured=capsys.readouterr()
    data=json.loads(captured.out)
    assert data['published'] is False and data['snapshot_id']
    assert len(captured.out)<20000 and len(captured.out.splitlines())==1
    assert not any(word in captured.out+captured.err for word in (canary,'Traceback','Authorization:','tasks": ['))
    receipts=list((context.workvault/'_plan-receipts').rglob('*.json'))
    assert receipts
    assert all(canary not in p.read_text() for p in receipts)


def test_invalid_arguments_do_not_echo_secret(capsys):
    canary='stage12-invalid-secret-42'
    with pytest.raises(SystemExit) as exc:
        cli.main(['history','--project-slug','trisigma','--invalid',canary])
    out=capsys.readouterr()
    assert exc.value.code==2 and canary not in out.out+out.err
    assert json.loads(out.out)['exit_code']==2


def test_today_example_uses_local_midnights_and_offsets():
    from datetime import datetime
    text=(S/'references/history-and-verification.md').read_text()
    code=re.search(r'```python\n(.*?)```',text,re.S).group(1)
    result={};exec(compile(code,'documented-today','exec'),result)
    since,until=(datetime.fromisoformat(result[key]) for key in ('since','until'))
    assert since.tzinfo and until.tzinfo
    assert since.hour==until.hour==0
    assert (until.date()-since.date()).days==1
    # Reuse exactly the documented algorithm for a DST day: 23 hours, not 86400s.
    code=code.replace("zone = ZoneInfo('Europe/Moscow')", "zone = ZoneInfo('Europe/Berlin')")
    code=code.replace('day = datetime.now(zone).date()', 'day = datetime(2026, 3, 29).date()')
    result={};exec(compile(code,'documented-today-dst','exec'),result)
    since,until=(datetime.fromisoformat(result[key]) for key in ('since','until'))
    assert (until-since).total_seconds()==23*3600


def test_reference_links_and_json_examples():
    import jsonschema
    for name in REFS:
        path=S/'references'/(name+'.md')
        assert path.is_file()
        for target in re.findall(r'\]\(([^)]+)\)',path.read_text()):
            if not target.startswith(('http:','https:','#')):
                assert (path.parent/target.split('#')[0]).exists(), (name,target)
    for name,schema in [('batch-and-inbox','batch-manifest'),('identity-and-rules','identity-mapping')]:
        text=(S/'references'/(name+'.md')).read_text()
        for block in re.findall(r'```json\n(.*?)```',text,re.S):
            jsonschema.validate(json.loads(block),json.loads((S/'references/schemas'/(schema+'.schema.json')).read_text()))


def test_forbidden_legacy_routes_removed():
    canon=(S/'SKILL.md').read_text();wrapper=(H/'skills/productivity/confluence-gantt-plan/SKILL.md').read_text()
    for text in (canon,wrapper):
        assert 'НЕ ГРУЗИТСЯ' not in text and 'published_at is NULL' not in text
        assert 'cp <original.mpp>' not in text and 'ПО УМОЛЧАНИЮ ВСЕГДА исключать' not in text
    assert 'Повторное общее «да» не требуется' in canon
