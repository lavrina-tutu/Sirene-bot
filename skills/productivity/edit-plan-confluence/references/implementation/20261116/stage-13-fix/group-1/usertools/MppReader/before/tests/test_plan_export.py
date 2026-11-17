"""Тесты plan_export.py (P2.MPP.1-6, R-012-014).

Требует mpxj/JVM (как read_mpp.py) — пропускается, если недоступно в
текущем интерпретаторе (обычно нужен ``/usr/bin/python3``, см. README.md).
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

pytest.importorskip("jpype")
pytest.importorskip("mpxj")

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

FIXTURE_MPP = (
    ROOT.parent.parent
    / "hermes-workspace" / "skills" / "productivity" / "edit-plan-confluence"
    / "tests" / "fixtures" / "ab_080926_пункт12.mpp"
)


@pytest.fixture(scope="module")
def export_data():
    import plan_export
    return plan_export.export_full(FIXTURE_MPP)


def test_export_full_provenance_matches_source_bytes(export_data):
    import hashlib
    expected = hashlib.sha256(FIXTURE_MPP.read_bytes()).hexdigest()
    assert export_data["provenance"]["sha256"] == expected
    assert export_data["provenance"]["size_bytes"] == FIXTURE_MPP.stat().st_size


def test_export_full_timezone_hint_default_none(export_data):
    assert export_data["timezone_hint"] is None


def test_export_full_tasks_collection_complete_with_ES_EF_LS_LF(export_data):
    assert export_data["collections"]["tasks"]["status"] == "complete"
    assert export_data["collections"]["tasks"]["count"] > 0
    task = export_data["tasks"][0]
    for field in ("early_start", "early_finish", "late_start", "late_finish",
                  "constraint_type", "actual_start", "remaining_duration"):
        assert field in task
        assert "quality" in task[field]


def test_export_full_known_empty_baseline_not_fabricated(export_data):
    """R-013/R-014: отсутствующий baseline-слот не заполняется догадкой —
    задача без присвоенного baseline просто не содержит записей слотов
    (а не 11 строк с нулями)."""
    for task in export_data["tasks"]:
        if "error" in task:
            continue
        for bv in task["baseline_values"]:
            assert 0 <= bv["slot"] <= 10
            # Хотя бы одно поле baseline-слота присутствует (иначе слот не
            # должен был попасть в вывод, см. _collect_tasks).
            assert any(bv[k] is not None for k in ("start", "finish", "duration", "work", "cost"))


def test_export_full_known_zero_vs_missing_quality_markers(export_data):
    for task in export_data["tasks"]:
        if "error" in task:
            continue
        assert task["early_start"]["quality"] in ("ok", "missing")


def test_diagnose_graph_detects_cycle_and_multiple_roots():
    import plan_export
    tasks = [
        {"task_key": "uid:1", "id": 1, "outline_level": 1},
        {"task_key": "uid:2", "id": 2, "outline_level": 1},
        {"task_key": "uid:0", "id": 0, "outline_level": 0},
    ]
    deps = [
        {"predecessor_task_key": "uid:1", "successor_task_key": "uid:2"},
        {"predecessor_task_key": "uid:2", "successor_task_key": "uid:1"},
    ]
    g = plan_export.diagnose_graph(tasks, deps)
    assert g["multiple_roots"] is True
    assert g["has_cycle"] is True
    assert ["uid:1", "uid:2", "uid:1"] in g["cycles"]
    assert g["has_service_row"] is True


def test_diagnose_graph_single_root_no_cycle_no_service_row():
    import plan_export
    tasks = [{"task_key": "uid:1", "id": 1, "outline_level": 1}]
    g = plan_export.diagnose_graph(tasks, [])
    assert g["multiple_roots"] is False
    assert g["has_cycle"] is False
    assert g["has_service_row"] is False


def test_export_full_missing_file_raises_not_fabricated():
    import plan_export
    with pytest.raises(FileNotFoundError):
        plan_export.export_full("/tmp/definitely-does-not-exist-12345.mpp")


def test_export_full_zd_hashes_match_r036(tmp_path):
    """Нормативные hash ТЗ (R-036 §10) — оба эталонных ZD MPP (если файлы
    присутствуют в окружении; иначе явный skip, не fabricated pass)."""
    import hashlib
    candidates = {
        "7d90831243a1ad1f7452a430b0cba76a7c0e3bfed7889345b55ffacd5abb375d":
            Path("/home/tkachenkoav/.hermes/cache/documents/doc_8d6bece30ad4_ZD. Закупка данных 121126.mpp"),
        "7b58e0a1efb1f5a3ba1cbd4690321f45ed5f065efe4a0c9a1c9f761c80cc2b13":
            Path("/home/tkachenkoav/.hermes/cache/documents/doc_94730ef53187_ZD. Закупка данных 131126.mpp"),
    }
    missing = [p for p in candidates.values() if not p.is_file()]
    if missing:
        pytest.skip(f"ZD MPP эталоны отсутствуют в этом окружении: {missing}")
    import plan_export
    for expected_hash, path in candidates.items():
        actual = hashlib.sha256(path.read_bytes()).hexdigest()
        assert actual == expected_hash
        import shutil
        copy = tmp_path / path.name
        shutil.copy2(path, copy)
        data = plan_export.export_full(copy)
        assert data["provenance"]["sha256"] == expected_hash
        assert data["collections"]["tasks"]["status"] == "complete"


def test_binary_relations_all_types_signed_elapsed_single_read(synthetic_dir):
    import plan_export
    events = []
    data = plan_export.export_full(synthetic_dir / "relations-all-types.mpp", read_observer=events.append)
    assert len(events) == 1 and data["telemetry"]["MPXJ_read"] == 1
    assert {r["link_type"] for r in data["dependencies"]} == {"FS", "SS", "FF", "SF"}
    by_type = {r["link_type"]:r for r in data["dependencies"]}
    assert by_type["SS"]["lag_value"]["value"] == {"amount":"-1", "units":"ELAPSED_DAYS", "source_units":"ed", "elapsed":True}
    assert by_type["FS"]["lag_value"]["value"]["amount"] == "1"
    assert by_type["FF"]["lag_value"]["value"]["amount"] == "0"
    for row in data["dependencies"]:
        assert row["lag_calendar"]["quality"] == "unsupported"
        assert row["lag_calendar"]["reason"] == "getter_unavailable:getCalendar"
        assert row["predecessor_uid"]["quality"] == "ok"
    assert data["export_version"] == "full-export-v2"
    assert data["provenance"]["mpxj"] == "16.4.0"


def test_binary_recipe_reproduces_fixture(synthetic_dir, tmp_path):
    import importlib.util
    spec = importlib.util.spec_from_file_location("binary_recipe", synthetic_dir / "binary_recipe.py")
    recipe = importlib.util.module_from_spec(spec);spec.loader.exec_module(recipe)
    target = tmp_path / "generated.mpp"
    recipe.make_elapsed_fixture(synthetic_dir / "mpp14relations.mpp", target)
    assert target.read_bytes() == (synthetic_dir / "relations-all-types.mpp").read_bytes()


def test_real_intraday_calendar_intervals_and_exceptions(export_data):
    calendars = export_data["calendars"]
    standard = next(c for c in calendars if c["name"] == "Стандартный")
    monday = next(d for d in standard["weekdays"] if d["day"] == "MONDAY")
    ranges = monday["intervals"]["value"]
    assert [(r["start"]["value"], r["end"]["value"]) for r in ranges] == [("09:00", "13:00"), ("14:00", "18:00")]
    short_day = next(e for e in standard["exceptions"] if e["name"]["value"] == "8 мая короткий")
    assert short_day["working"]["value"] is True
    assert short_day["intervals"]["value"][-1]["end"]["value"] == "17:00"
    assert any(c["parent_key"]["value"] for c in calendars)
    assert export_data["project"]["default_calendar_key"]["value"] == standard["calendar_key"]
    assert all(r["calendar_key"]["value"] in {c["calendar_key"] for c in calendars} for r in export_data["resources"])
    assert export_data["project"]["minutes_per_day"]["value"] == "480"


def test_real_binary_splits_and_elapsed_duration(synthetic_dir):
    import plan_export
    split = plan_export.export_full(synthetic_dir / "mpp14splittask.mpp")
    assert any(len(t["segments"]["value"] or []) >= 2 for t in split["tasks"])
    durations = plan_export.export_full(synthetic_dir / "mpp14duration.mpp")
    assert any(t["duration"]["quantity"] and t["duration"]["quantity"]["elapsed"] for t in durations["tasks"])
    assert all("actual_work" in t and "task_mode" in t and "parent_task_key" in t for t in split["tasks"])


def test_real_binary_recurring_exceptions_preserved(synthetic_dir):
    import plan_export
    data = plan_export.export_full(synthetic_dir / "calendar-recurring-exceptions-project2010-mpp14.mpp")
    recurring = [e["recurrence"]["value"] for c in data["calendars"] for e in c["exceptions"] if e["recurrence"]["value"]]
    assert recurring
    assert all("frequency" in r and "weekly_days" in r and "type" in r for r in recurring)


def test_real_cases_metadata_and_no_repeated_reads(real_cases):
    import plan_export
    expected = {"A":(58,53),"B":(62,60),"C":(62,61),"D":(72,76),"E":(78,84),"F":(86,93)}
    for row in real_cases:
        events = []
        data = plan_export.export_full(row["copy"], read_observer=events.append)
        assert len(events) == data["telemetry"]["MPXJ_read"] == 1
        assert data["provenance"]["sha256"] == row["sha256"]
        assert data["provenance"]["size_bytes"] == row["size_bytes"]
        assert data["timezone_hint"] is None
        assert not any("error" in t for t in data["tasks"])
        if row["id"] in expected:
            assert (len(data["tasks"]), len(data["dependencies"])) == expected[row["id"]]
            assert sum(t["id"] == 0 for t in data["tasks"]) == 1
        assert data["diagnose_graph"]["schedule_status"] == "not_verified"


def test_graph_four_errors_and_long_chain(synthetic_dir):
    import json
    import plan_export
    data = json.loads((synthetic_dir / "graph-invalid.json").read_text())
    result = plan_export.diagnose_graph(data["tasks"], data["dependencies"])
    assert result["has_cycle"] and result["self_references"]
    assert result["dangling_dependencies"] and result["external_dependencies"]
    tasks = [{"task_key":f"id:{i}", "id":i, "outline_level":2} for i in range(2500)]
    deps = [{"predecessor_task_key":f"id:{i}", "successor_task_key":f"id:{i+1}"} for i in range(2499)]
    assert not plan_export.diagnose_graph(tasks,deps)["has_cycle"]


def test_getter_errors_quality_and_deterministic_fallback():
    import plan_export as e
    class Task:
        def getID(self): return None
        def getUniqueID(self): return None
        def getName(self): return "no IDs"
        def getDuration(self): raise RuntimeError("cannot read duration")
        def getPercentageComplete(self): return 0
    class Project:
        def getTasks(self): return [Task(),Task()]
        def getCalendars(self): return []
    first, _ = e._collect_tasks(Project())
    second, _ = e._collect_tasks(Project())
    assert first == second
    assert first[0]["task_key"] == "local:task:000000"
    assert first[1]["task_key"] == "local:task:000001"
    assert first[0]["duration"]["quality"] == "missing"
    assert first[0]["duration"]["reason"].startswith("getter_failed:getDuration")
    assert first[0]["task_mode"]["quality"] == "unsupported"
    assert first[0]["percent_complete"]["value"] == "0"
    assert e._collection_status(first)["status"] == "partial"


def test_weekday_flags_alone_are_not_complete():
    import plan_export as e
    class Calendar:
        def getUniqueID(self): return 1
        def getName(self): return "flags-only"
        def isWorkingDay(self, day): return True
    class Project:
        def getCalendars(self): return [Calendar()]
    data = e._collect_calendars(Project())
    assert e._collection_status(data)["status"] == "partial"
    assert all(d["intervals"]["quality"] == "unsupported" for d in data[0]["weekdays"])


def test_binary_same_bytes_different_paths_same_semantics(synthetic_dir, tmp_path):
    import shutil
    import plan_export
    sys.path.insert(0, str(ROOT.parent.parent / "hermes-workspace/skills/productivity/edit-plan-confluence/scripts"))
    from prepared_plan import PreparedPlan
    one, two = tmp_path / "first.mpp", tmp_path / "another-name.mpp"
    for target in [one,two]:
        shutil.copy2(synthetic_dir / "relations-all-types.mpp", target)
    first = PreparedPlan.from_export(plan_export.export_full(one))
    second = PreparedPlan.from_export(plan_export.export_full(two))
    assert first.semantic_bytes() == second.semantic_bytes()


def test_binary_invalid_graph_filtered_records_are_explicit(synthetic_dir):
    import plan_export
    data = plan_export.export_full(synthetic_dir / "graph-invalid.mpp")
    assert len(data["dependencies"]) == 2  # two of four raw records were filtered inside MPXJ
    assert data["diagnose_graph"]["has_cycle"]
    quality = data["diagnose_graph"]["raw_relation_enumeration"]
    assert quality["quality"] == "unsupported"
    assert "filters_self_and_dangling" in quality["reason"]
    assert data["collections"]["dependencies"]["status"] == "partial"
