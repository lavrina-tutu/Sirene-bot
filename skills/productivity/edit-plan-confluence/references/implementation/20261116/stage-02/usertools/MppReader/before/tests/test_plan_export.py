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
        data = plan_export.export_full(path)
        assert data["provenance"]["sha256"] == expected_hash
        assert data["collections"]["tasks"]["status"] == "complete"
