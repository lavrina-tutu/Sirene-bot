from __future__ import annotations

from pathlib import Path

from gate_diff import build_diff
from mpp_convert import compute_id_counter, convert_mpp_csv, copy_parent_gantt, count_tasks, empty_gantt, flatten_events


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
