from __future__ import annotations

import sys
from pathlib import Path

import pytest

from itogo import (
    apply_itogo,
    build_itogo_html,
    compute_itogo_from_csv,
    format_thousands,
    parse_itogo_text,
    patch_itogo,
    record_itogo_observation,
    strip_trudozatraty,
)
from macro import build_macro_html, macro_span

MOFS_ROOT = Path.home() / "USERTOOLS" / "MofsIndex"
if str(MOFS_ROOT) not in sys.path:
    sys.path.insert(0, str(MOFS_ROOT))


def test_itogo_from_csv_080926(tasks_csv, assignments_csv):
    d1, d2, n, m = compute_itogo_from_csv(tasks_csv, assignments_csv)
    assert d1 == "28.09.26"
    assert d2 == "18.05.27"
    assert n == 154
    assert m == 2356


def test_format_thousands():
    assert format_thousands(1960) == "1 960"
    assert format_thousands(2356) == "2 356"


def test_build_itogo_html():
    html = build_itogo_html("28.09.26", "18.05.27", 154, 2356)
    assert "Итого: с 28.09.26 по 18.05.27 - 154 рабочих дней" in html
    assert "Трудозатраты" not in html
    assert "70%" not in html


def test_patch_existing_itogo():
    storage = (
        "<p><strong>Итого: с 01.01.26 по 02.02.26 - 10 рабочих дней</strong></p>"
        "<p><strong>Трудозатраты: 100 человек-часа</strong></p>"
        "<p><strong>Загрузка 70% — не трогать</strong></p>"
        "<p>macro</p>"
    )
    out = patch_itogo(storage, "28.09.26", "18.05.27", 154, 2356)
    assert "28.09.26" in out
    assert "154" in out
    assert "Трудозатраты" not in out
    assert "человек-часа" not in out
    assert "2 356" not in out
    assert "Загрузка 70%" in out


def test_patch_existing_itogo_line1_only():
    storage = (
        "<p><strong>Итого: с 01.01.26 по 02.02.26 - 10 рабочих дней</strong></p>"
        "<p>macro</p>"
    )
    out = patch_itogo(storage, "28.09.26", "18.05.27", 154, 2356)
    assert out.count("Итого:") == 1
    assert "18.05.27" in out
    assert "154" in out
    assert "Трудозатраты" not in out


def test_insert_itogo_above_macro_no_block():
    macro_html = build_macro_html("new-macro-id", "pid", "phash")
    storage = "<p>Intro text</p>" + macro_html
    span = macro_span(storage)
    assert span is not None
    out = apply_itogo(storage, "28.09.26", "18.05.27", 154, 2356, macro_start=span[0])
    macro_pos = out.index("gantt-chart-planner")
    itogo_pos = out.index("Итого:")
    assert itogo_pos < macro_pos
    assert out.count("Итого:") == 1
    assert "154" in out
    assert "Трудозатраты" not in out


def test_apply_itogo_strips_line2_updates_line1():
    storage = (
        "<p><strong>Итого: с 01.01.26 по 02.02.26 - 10 рабочих дней</strong></p>"
        "<p><strong>Трудозатраты: 100 человек-часа</strong></p>"
        "<p><strong>Загрузка 70% — не трогать</strong></p>"
        "<p>macro</p>"
    )
    out = apply_itogo(storage, "28.09.26", "18.05.27", 154, 2356)
    assert "28.09.26" in out
    assert "18.05.27" in out
    assert "154" in out
    assert "Трудозатраты" not in out
    assert "Загрузка 70%" in out
    assert out.count("Итого:") == 1


def test_apply_itogo_line2_only_inserts_line1():
    macro_html = build_macro_html("new-macro-id", "pid", "phash")
    storage = "<p><strong>Трудозатраты: 100 человек-часа</strong></p>" + macro_html
    span = macro_span(storage)
    assert span is not None
    out = apply_itogo(storage, "28.09.26", "18.05.27", 154, 2356, macro_start=span[0])
    macro_pos = out.index("gantt-chart-planner")
    itogo_pos = out.index("Итого:")
    assert itogo_pos < macro_pos
    assert out.count("Итого:") == 1
    assert "Трудозатраты" not in out


def test_strip_trudozatraty_variants():
    canon = "<p><strong>Трудозатраты: 100 человек-часа</strong></p>"
    assert strip_trudozatraty(canon) == ""
    alt = "<p><strong>Трудозатраты: 50 человеко-часов</strong></p>"
    assert strip_trudozatraty(alt) == ""
    nbsp = "<p><strong>Трудозатраты: 2\xa0356 человек-часа</strong></p>"
    assert strip_trudozatraty(nbsp) == ""
    plain = "<p>Трудозатраты: 10 человек-часов</p>"
    assert "Трудозатраты" not in strip_trudozatraty(plain)
    assert strip_trudozatraty(strip_trudozatraty(canon)) == ""


def test_parse_itogo_text_found():
    storage = "<p><strong>Итого: с 01.01.26 по 02.02.26 - 10 рабочих дней</strong></p>"
    d1, d2, n = parse_itogo_text(storage)
    assert (d1, d2, n) == ("01.01.26", "02.02.26", 10)


def test_parse_itogo_text_missing_is_none_not_fabricated():
    d1, d2, n = parse_itogo_text("<p>нет итого тут</p>")
    assert (d1, d2, n) == (None, None, None)


@pytest.fixture
def plan_conn(tmp_path):
    from mofs_index.db import connect, initialize
    from mofs_index.plan.migrate import ensure_plan_schema
    from mofs_index.plan import writer as plan_writer

    c = connect(tmp_path / "index.sqlite", durable=True)
    initialize(c)
    ensure_plan_schema(c)
    plan_id = plan_writer.ensure_plan(c, "zd")
    yield c, plan_id
    c.close()


def test_record_itogo_observation_known(plan_conn):
    conn, plan_id = plan_conn
    storage = "<p><strong>Итого: с 01.01.26 по 02.02.26 - 10 рабочих дней</strong></p>"
    obs_id = record_itogo_observation(
        plan_id, "537561928", page_version=1, raw_storage=storage, conn=conn,
    )
    row = conn.execute(
        "SELECT itogo_d1, itogo_d2, itogo_n, quality FROM plan_page_observation WHERE observation_id=?",
        (obs_id,),
    ).fetchone()
    assert tuple(row) == ("01.01.26", "02.02.26", 10, "ok")


def test_record_itogo_observation_missing_is_unknown_not_fabricated(plan_conn):
    """AC-110: отсутствующий исторический «Итого» помечен unknown, не
    выдуман как 01.01.00."""
    conn, plan_id = plan_conn
    obs_id = record_itogo_observation(
        plan_id, "537561928", page_version=4, raw_storage="<p>нет итого</p>", conn=conn,
    )
    row = conn.execute(
        "SELECT itogo_d1, itogo_n, quality FROM plan_page_observation WHERE observation_id=?",
        (obs_id,),
    ).fetchone()
    assert tuple(row) == (None, None, "unknown")


def test_record_itogo_observation_two_observations_not_glued_by_number(plan_conn):
    """Разные наблюдения с совпадающим N не склеиваются: каждое — отдельная строка."""
    conn, plan_id = plan_conn
    storage = "<p><strong>Итого: с 01.01.26 по 02.02.26 - 10 рабочих дней</strong></p>"
    obs1 = record_itogo_observation(plan_id, "537561928", page_version=1, raw_storage=storage, conn=conn)
    obs2 = record_itogo_observation(plan_id, "537561928", page_version=2, raw_storage=storage, conn=conn)
    assert obs1 != obs2
    count = conn.execute("SELECT COUNT(*) FROM plan_page_observation").fetchone()[0]
    assert count == 2


from copy import deepcopy
from decimal import Decimal
from itogo import compute_itogo_from_prepared, format_work_hours, work_metrics
from prepared_plan import PreparedPlan


@pytest.mark.parametrize('duration,expected',[('84.875',85),('76.875',77),('106.875',107),('0',0)])
def test_prepared_summary_ceil(stage08_export,duration,expected):
    stage08_export['tasks'][1]['duration']['quantity']['amount']=duration
    result=compute_itogo_from_prepared(PreparedPlan.from_export(stage08_export,timezone_hint='Europe/Moscow'))
    assert result['n_days']==expected
    assert result['publishable']
    assert result['duration_working_days']==duration
    assert 'ч-ч' not in result['storage_html'] and 'Трудозатраты' not in result['storage_html']
    assert result['work']['hours']=='0.3'


def test_prepared_work_exact_summary_service_milestone_and_timephased(stage08_export):
    result=work_metrics(stage08_export)
    assert result['hours']=='0.3' and result['quality']=='complete'
    assert result['known_assignments']==2 and result['excluded_assignments']==2
    assert format_work_hours('1.2345')=='1.235'
    assert format_work_hours('1.2344')=='1.234'
    assert format_work_hours('1576.000')=='1576'
    assert format_work_hours(None) is None
    # A repeated serialized record is not a second actual assignment.
    stage08_export['assignments'].append(deepcopy(stage08_export['assignments'][0]))
    assert work_metrics(stage08_export)['hours']=='0.3'


def test_prepared_work_missing_partial_not_zero(stage08_export):
    a=stage08_export['assignments'][0]
    a['work']={'value':None,'quantity':None,'quality':'missing','reason':'not_set'}
    result=work_metrics(stage08_export)
    assert result['hours']=='0.2' and result['quality']=='partial'
    stage08_export['assignments'][1]['work']=deepcopy(a['work'])
    result=work_metrics(stage08_export)
    assert result['hours'] is None and result['quality']=='missing'
    stage08_export['assignments']=[]
    stage08_export['collections']['assignments']['status']='missing'
    assert work_metrics(stage08_export)['hours'] is None


def test_prepared_multiple_roots_explicit_choice(stage08_export):
    other=deepcopy(stage08_export['tasks'][1]);other.update(task_key='other',id=7,uid=7)
    stage08_export['tasks'].append(other);stage08_export['collections']['tasks']['count']+=1
    p=PreparedPlan.from_export(stage08_export,timezone_hint='Europe/Moscow')
    result=compute_itogo_from_prepared(p)
    assert result['root_task_key'] is None and 'summary_root_choice_required' in result['reasons']
    assert result['storage_html'] is None
    assert compute_itogo_from_prepared(p,root_task_key='other')['root_task_key']=='other'
    with pytest.raises(ValueError,match='invalid_summary_root'):
        compute_itogo_from_prepared(p,root_task_key='service')


@pytest.mark.parametrize('kind',['units','elapsed','basis','timezone','date'])
def test_prepared_unknown_basis_blocks_summary(stage08_export,kind):
    root=stage08_export['tasks'][1]
    if kind=='units':root['duration']['quantity']['units']='FORTNIGHTS'
    if kind=='elapsed':root['duration']['quantity'].update(units='ELAPSED_DAYS',elapsed=True)
    if kind=='basis':stage08_export['project']['minutes_per_day']={'value':None,'quality':'missing','reason':'not_set'}
    if kind=='date':root['start']={'value':None,'quality':'missing','reason':'not_set'}
    p=PreparedPlan.from_export(stage08_export,timezone_hint=None if kind=='timezone' else 'Europe/Moscow')
    result=compute_itogo_from_prepared(p)
    assert not result['publishable'] and result['storage_html'] is None
    if kind in ('units','elapsed','basis'):assert result['n_days'] is None


def test_prepared_source_coefficients_and_timezone(stage08_export):
    root=stage08_export['tasks'][1]
    root['duration']['quantity'].update(amount='510',units='MINUTES')
    stage08_export['project']['minutes_per_day']['value']='300'
    root['start']['value']='2026-01-04T23:00:00Z'
    p=PreparedPlan.from_export(stage08_export,timezone_hint='Europe/Moscow')
    result=compute_itogo_from_prepared(p)
    assert result['duration_working_days']=='1.7' and result['n_days']==2
    assert result['d1']=='05.01.26'
    stage08_export['assignments'][0]['work']['quantity'].update(amount='1.5',units='DAYS')
    assert work_metrics(stage08_export)['hours']=='7.7'


@pytest.mark.mpp_fixtures
@pytest.mark.parametrize('case,expected',[('A','1576'),('B','2096'),('C','2088'),('D','3136')])
def test_real_prepared_work_tolerance(case,expected,tmp_path,request):
    import hashlib,json,shutil,subprocess
    fixtures=Path(__file__).parent/'fixtures/real'
    manifest=json.loads((fixtures/'manifest.json').read_text())
    records=manifest.get('fixtures',manifest)
    if isinstance(records,list):entry=next(r for r in records if r.get('case')==case or r.get('id')==case)
    else:entry=records[case]
    digest=entry.get('sha256',entry.get('source_sha256'))
    source=fixtures/(digest+'.mpp')
    target=tmp_path/source.name;shutil.copyfile(source,target)
    assert hashlib.sha256(target.read_bytes()).hexdigest()==digest
    proc=subprocess.run(['/usr/bin/python3.9','/home/tkachenkoav/USERTOOLS/MppReader/plan_export.py',str(target)],capture_output=True,text=True,timeout=120)
    assert proc.returncode==0,proc.stderr
    export=json.loads(proc.stdout[proc.stdout.index('{'):])
    p=PreparedPlan.from_export(export,timezone_hint='Europe/Moscow')
    out=compute_itogo_from_prepared(p)
    delta=abs(Decimal(out['work']['hours'])-Decimal(expected))
    assert delta<=Decimal('0.001')
    expected_counts={'A':(58,57,53),'B':(62,61,60),'C':(62,61,61),'D':(72,71,76)}
    counts=out['counts']
    assert (counts['archive_task_count'],counts['display_task_count'],counts['dependency_count'])==expected_counts[case]
    assert export['telemetry']['MPXJ_read']==1
    evidence={'case':case,'source_sha256':digest,'expected_hours':expected,'actual_hours':out['work']['hours'],
              'absolute_delta_hours':str(delta),'tolerance_hours':'0.001','summary':out,
              'archive_task_count':len(export['tasks']),'service_task_count':sum(t.get('id')==0 for t in export['tasks']),
              'display_task_count':sum(t.get('id')!=0 for t in export['tasks']),
              'MPXJ_read':export['telemetry']['MPXJ_read']}
    root=getattr(request.config,'_acceptance_root',tmp_path)
    (root/'reports'/('stage08-work-'+case+'.json')).write_text(json.dumps(evidence,ensure_ascii=False,indent=2))
