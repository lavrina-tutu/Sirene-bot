from __future__ import annotations

import csv
from copy import deepcopy
from pathlib import Path

import pytest

from gate_diff import build_diff
from mpp_convert import (
    _parse_outline_level,
    build_event_tree,
    compute_id_counter,
    convert_mpp_csv,
    copy_parent_gantt,
    count_tasks,
    empty_gantt,
    flatten_events,
    read_csv_rows,
)
from mpp_convert import _leaf_template


def test_convert_task_count(tasks_csv, resources_csv, assignments_csv, gantt_test_template):
    gantt = convert_mpp_csv(
        tasks_csv,
        resources_csv,
        assignments_csv,
        template_json=gantt_test_template,
    )
    root = gantt["eventsData"][0]
    assert count_tasks(root) == 33


def test_id_counter_not_300000(tasks_csv, resources_csv, assignments_csv, gantt_test_template):
    gantt = convert_mpp_csv(
        tasks_csv,
        resources_csv,
        assignments_csv,
        template_json=gantt_test_template,
    )
    assert gantt["idCounter"] != 300000
    assert gantt["idCounter"] == compute_id_counter(gantt)


def test_fs_dependencies_only(tasks_csv, resources_csv, assignments_csv, gantt_test_template):
    gantt = convert_mpp_csv(
        tasks_csv,
        resources_csv,
        assignments_csv,
        template_json=gantt_test_template,
    )
    deps = gantt["dependenciesData"]
    assert len(deps) > 0
    assert all(d["type"] == 2 and d["lag"] == 0 for d in deps)


def test_naim_resource_added(tasks_csv, resources_csv, assignments_csv, gantt_test_template):
    gantt = convert_mpp_csv(
        tasks_csv,
        resources_csv,
        assignments_csv,
        template_json=gantt_test_template,
    )
    names = {r["name"] for r in gantt["resourcesData"]}
    assert "Найм" in names
    # dead copies pruned: one id per name
    by_name: dict[str, list] = {}
    for r in gantt["resourcesData"]:
        by_name.setdefault(r["name"], []).append(r["id"])
    assert all(len(v) == 1 for v in by_name.values())


def test_tree_structure(tasks_csv, resources_csv, assignments_csv, gantt_test_template):
    gantt = convert_mpp_csv(
        tasks_csv,
        resources_csv,
        assignments_csv,
        template_json=gantt_test_template,
    )
    root = gantt["eventsData"][0]
    assert root["id"] == 1
    assert len(root["children"]) == 18
    flat = flatten_events(root)
    assert len(flat) == 33

    def find_node(nid: int):
        return flat[nid]

    assert find_node(2)["duration"] == 0
    assert find_node(33)["duration"] == 0

    for node in flat.values():
        if node.get("rollup"):
            assert any(c.get("rollup") is False or c.get("rollup") is True for c in node.get("children", [])) or not node.get("children")
        parent_id = node.get("parentId")
        if parent_id is not None:
            parent = flat[parent_id]
            assert node in parent["children"]
            assert node["parentIndex"] == parent["children"].index(node)


def _service_header_row_217(donor: dict[str, str]) -> dict[str, str]:
    row = deepcopy(donor)
    row["id"] = "217"
    row["outline_level"] = "0"
    row["summary"] = "True"
    row["predecessors"] = "[1]"
    row["name"] = donor.get("name", "service header")
    return row


def _write_tasks_csv(path: Path, rows: list[dict[str, str]], fieldnames: list[str]) -> None:
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(rows)


def _gantt_with_header_217(
    tasks_csv: Path,
    tmp_path: Path,
    resources_csv: Path,
    assignments_csv: Path,
    gantt_test_template: dict,
    header_first: bool,
) -> dict:
    original_rows = read_csv_rows(tasks_csv)
    fieldnames = list(original_rows[0].keys())
    donor = next(r for r in original_rows if r["id"] == "1")
    header = _service_header_row_217(donor)
    if header_first:
        rows = [header] + original_rows
    else:
        rows = []
        for r in original_rows:
            rows.append(r)
            if r["id"] == "1":
                rows.append(header)
    out_csv = tmp_path / "tasks_with_header.csv"
    _write_tasks_csv(out_csv, rows, fieldnames)
    return convert_mpp_csv(
        out_csv,
        resources_csv,
        assignments_csv,
        template_json=gantt_test_template,
    )


def _assert_root_not_header_217(gantt: dict) -> None:
    root = gantt["eventsData"][0]
    assert root["id"] == 1
    assert "Доработки АБ-платформы" in root["name"]
    assert count_tasks(root) == 33
    flat = flatten_events(root)
    assert 217 not in flat
    assert len(flat) == 33
    deps = gantt["dependenciesData"]
    assert not any(d.get("from") == 217 or d.get("to") == 217 for d in deps)


def test_service_header_217_first(
    tasks_csv, tmp_path, resources_csv, assignments_csv, gantt_test_template
):
    gantt = _gantt_with_header_217(
        tasks_csv, tmp_path, resources_csv, assignments_csv, gantt_test_template, header_first=True
    )
    _assert_root_not_header_217(gantt)


def test_service_header_217_after_root(
    tasks_csv, tmp_path, resources_csv, assignments_csv, gantt_test_template
):
    gantt = _gantt_with_header_217(
        tasks_csv, tmp_path, resources_csv, assignments_csv, gantt_test_template, header_first=False
    )
    root = gantt["eventsData"][0]
    assert root["id"] == 1
    assert root["children"]
    _assert_root_not_header_217(gantt)


def test_parse_outline_level():
    assert _parse_outline_level("") == 0
    assert _parse_outline_level(None) == 0
    assert _parse_outline_level("0") == 0
    assert _parse_outline_level("0.0") == 0
    assert _parse_outline_level("abc") == 0
    assert _parse_outline_level("1") == 1
    assert _parse_outline_level("1.0") == 1
    assert _parse_outline_level("2") == 2


def test_only_service_header_raises(empty_template):
    donor = {"id": "1", "outline_level": "1", "name": "x", "duration": "1 d", "start": "", "finish": "", "milestone": "False", "summary": "True", "percent_complete": "0"}
    header = _service_header_row_217(donor)
    leaf = _leaf_template(empty_template)
    with pytest.raises(ValueError, match="No root task"):
        build_event_tree([header], leaf)


def test_copy_and_empty(gantt_test_template):
    empty = empty_gantt("Тест")
    root = empty["eventsData"][0]
    assert root["id"] == 1
    assert root["children"] == []
    assert empty["dependenciesData"] == []
    assert empty["assignmentsData"] == []
    diff = build_diff(
        page_id="519501810",
        title="T",
        operation="создание дочерней страницы с макросом",
        gantt=empty,
        empty_plan=True,
    )
    assert "план пустой" in diff

    parent = dict(gantt_test_template)
    parent["idCounter"] = 300000
    copied = copy_parent_gantt(parent)
    assert copied["idCounter"] != 300000
    assert copied["idCounter"] == compute_id_counter(copied)


from prepared_plan import PreparedPlan
from mpp_convert import convert_prepared_plan, representation_bytes


def test_prepared_dependencies_types_signed_lag_parallel_resources(stage08_export,stage08_profile):
    prepared=PreparedPlan.from_export(stage08_export,timezone_hint='Europe/Moscow')
    before=prepared.semantic_bytes()
    result=convert_prepared_plan(prepared,plugin_profile=stage08_profile)
    deps=result['gantt']['dependenciesData']
    assert [d['type'] for d in deps]==[12,10,13,11,12]
    assert [d['lag'] for d in deps]==[0,-1,2,0.5,1]
    assert deps[2]['lagUnit']=='eday'
    assert len(result['gantt']['resourcesData'])==2
    resources=result['mappings']['resources']
    assert resources['r1']!=resources['r2']
    asns=result['gantt']['assignmentsData']
    assert any(a['units']==0 and a['resource']==resources['r1'] for a in asns)
    assert all(n['id']!=0 for n in flatten_events(result['gantt']['eventsData'][0]).values())
    assert len(result['source_semantics']['tasks'])==4
    assert prepared.semantic_bytes()==before
    assert representation_bytes(result)==representation_bytes(convert_prepared_plan(prepared,plugin_profile=stage08_profile))


@pytest.mark.parametrize('kind',['type','lag','unit','elapsed','basis','endpoint','external'])
def test_prepared_unknown_dependency_never_fs_zero(stage08_export,stage08_profile,kind,monkeypatch):
    import plan_policy
    original=plan_policy.owner_decision
    def without_v2():
        result=original();result.pop('calendar',None);result.pop('calendar_evidence',None);result.pop('calendar_evidence_verified',None);return result
    monkeypatch.setattr(plan_policy,'owner_decision',without_v2)
    d=stage08_export['dependencies'][0]
    if kind=='type':d['link_type']=None
    if kind=='lag':d['lag_value']={'value':None,'quality':'missing','reason':'not_set'}
    if kind=='unit':d['lag_value']['value']['units']='FORTNIGHT'
    if kind=='elapsed':d['lag_value']['value']['elapsed']=True
    if kind=='basis':d['project_lag_calendar']['value']='UNKNOWN'
    if kind=='endpoint':d['successor_task_key']='nonexistent'
    if kind=='external':d['external']=True
    result=convert_prepared_plan(PreparedPlan.from_export(stage08_export),plugin_profile=stage08_profile)
    assert len(result['gantt']['dependenciesData'])==4
    assert not result['publishable']
    assert any(x.get('entity')=='dep0' for x in result['diagnostics'])
    assert result['source_semantics']['dependencies'][0]==d


def test_prepared_tree_uses_parent_keys_all_roots_and_partial_assignment(stage08_export,stage08_profile):
    stage08_export['tasks'][3]['parent_task_key']={'value':None,'quality':'missing','reason':'not_set'}
    stage08_export['assignments'][0]['units']={'value':None,'quality':'missing','reason':'not_set'}
    p=PreparedPlan.from_export(stage08_export)
    result=convert_prepared_plan(p,plugin_profile=stage08_profile)
    assert len(result['gantt']['eventsData'])==2
    assert not any(a['units']==100 and a['event']==2 for a in result['gantt']['assignmentsData'])
    assert any(d['code']=='assignment_partial' for d in result['diagnostics'])
    assert result['gantt']['eventsData'][0]['children'][0]['parentId']==1


def test_prepared_no_reader_in_converter_calendar_itogo(stage08_export,stage08_profile,monkeypatch):
    import mpp_calendar,mpp_input,subprocess
    def forbidden(*a,**k):raise AssertionError('reader/CSV/JVM forbidden')
    monkeypatch.setattr(subprocess,'run',forbidden)
    monkeypatch.setattr(mpp_input,'export_csv',forbidden)
    monkeypatch.setattr(mpp_calendar,'_ensure_jvm',forbidden)
    monkeypatch.setattr('mpp_convert.read_csv_rows',forbidden)
    result=convert_prepared_plan(PreparedPlan.from_export(stage08_export,timezone_hint='Europe/Moscow'),plugin_profile=stage08_profile)
    assert result['summary']['n_days']==85


def test_prepared_hierarchy_cycle_rejected(stage08_export,stage08_profile):
    stage08_export['tasks'][1]['parent_task_key']={'value':'a','quality':'ok','reason':None}
    with pytest.raises(ValueError,match='cyclic_task_hierarchy'):
        convert_prepared_plan(PreparedPlan.from_export(stage08_export),plugin_profile=stage08_profile)


def test_prepared_lag_basis_only_equivalent_calendars(stage08_export,stage08_profile,monkeypatch):
    from copy import deepcopy
    import plan_policy
    original=plan_policy.owner_decision
    def without_v2():
        result=original();result.pop('calendar',None);result.pop('calendar_evidence',None);result.pop('calendar_evidence_verified',None);return result
    monkeypatch.setattr(plan_policy,'owner_decision',without_v2)
    stage08_profile.document['capabilities']['lag_basis:PREDECESSOR']['status']='not_verified'
    cap=deepcopy(stage08_profile.document['capabilities']['lag:zero'])
    stage08_profile.document['capabilities']['lag_basis:equal_endpoint_calendars']=cap
    p=PreparedPlan.from_export(stage08_export)
    out=convert_prepared_plan(p,plugin_profile=stage08_profile)
    assert len(out['gantt']['dependenciesData'])==5
    stage08_export['tasks'][3]['effective_calendar_key']['value']='different'
    out=convert_prepared_plan(PreparedPlan.from_export(stage08_export),plugin_profile=stage08_profile)
    assert len(out['gantt']['dependenciesData'])==0
    assert any(d['code']=='dependency_calendar_basis_unsupported' for d in out['diagnostics'])


def test_prepared_golden_bytes_and_storage(stage08_export,stage08_profile,monkeypatch):
    import hashlib,json
    import plan_policy
    original=plan_policy.owner_decision
    def without_v2():
        result=original();result.pop('calendar',None);result.pop('calendar_evidence',None);result.pop('calendar_evidence_verified',None);return result
    monkeypatch.setattr(plan_policy,'owner_decision',without_v2)
    golden=Path(__file__).parent/'fixtures/golden'
    for item in json.loads((golden/'manifest.json').read_text())['fixtures']:
        assert hashlib.sha256((golden/item['path']).read_bytes()).hexdigest()==item['sha256']
    result=convert_prepared_plan(PreparedPlan.from_export(stage08_export,timezone_hint='Europe/Moscow'),plugin_profile=stage08_profile)
    assert representation_bytes(result)==(golden/'prepared-unit-gantt.json').read_bytes()
    assert result['summary']['storage_html']==(golden/'prepared-unit-storage.xml').read_text()
    assert 'Трудозатраты' not in result['summary']['storage_html']
    assert 'work' not in result['summary']['storage_html']



def test_prepared_summary_dependency_and_unrepresented_scheduling(stage08_export,stage08_profile):
    stage08_export['dependencies'][0]['predecessor_task_key']='root'
    stage08_export['tasks'][2]['active']={'value':False,'quality':'ok','reason':None}
    stage08_export['tasks'][2]['leveling_delay']['quantity']['amount']='1'
    out=convert_prepared_plan(PreparedPlan.from_export(stage08_export),plugin_profile=stage08_profile)
    codes={d['code'] for d in out['diagnostics']}
    assert {'summary_dependency_unverified','inactive_task_unverified','leveling_delay_unrepresented'}<=codes
    assert out['source_semantics']['dependencies'][0]['predecessor_task_key']=='root'
    assert not out['publishable']
