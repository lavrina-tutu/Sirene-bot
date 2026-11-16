"""Регресс read_mpp.py CSV/JSON (P2.MPP хвост): plan_export.py — отдельный
путь, не меняет поведение существующего CSV/обычного JSON и их
потребителей (R-012)."""
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


def test_read_mpp_read_project_shape_unaffected_by_plan_export_import():
    """Импорт plan_export (который сам импортирует read_mpp._start_jvm) не
    меняет форму/содержимое read_mpp.read_project на том же файле."""
    import read_mpp

    data_before_import = read_mpp.read_project(str(FIXTURE_MPP))

    import plan_export  # noqa: F401 — факт импорта не должен повлиять на read_mpp

    data_after_import = read_mpp.read_project(str(FIXTURE_MPP))

    assert set(data_before_import.keys()) == set(data_after_import.keys())
    assert data_before_import["stats"] == data_after_import["stats"]
    assert data_before_import["project"] == data_after_import["project"]
    assert data_before_import["tasks"] == data_after_import["tasks"]
    assert data_before_import["resources"] == data_after_import["resources"]
    assert data_before_import["assignments"] == data_after_import["assignments"]


def test_read_mpp_cli_json_contract_keys_stable(tmp_path):
    """CLI-контракт ``read_mpp.py --format json`` (ключи top-level) не
    тронут Фазой 2 — потребители, парсящие этот JSON, не ломаются."""
    import subprocess

    proc = subprocess.run(
        [sys.executable, str(ROOT / "read_mpp.py"), str(FIXTURE_MPP),
         "--format", "json", "--out-dir", str(tmp_path), "--summary"],
        capture_output=True, text=True,
    )
    assert proc.returncode == 0, proc.stderr
    import json
    stdout = proc.stdout
    payload = json.loads(stdout[stdout.index("{"):])
    assert set(payload.keys()) == {"source", "project", "stats", "csv_files", "tasks_preview"}


def test_mpp_convert_unaffected_by_plan_export(mpp_convert_module):
    """mpp_convert.py (edit-plan-confluence) байт-в-байт тот же путь:
    convert_mpp_csv возвращает идентичный результат до/после импорта
    plan_export (общий JVM-бутстрап через read_mpp не пересекается с
    отдельным процессом mpp_convert, который использует CSV, не JVM
    напрямую — но тест фиксирует инвариант явно, не предположением)."""
    csvs_dir = FIXTURE_MPP.parent
    stem = FIXTURE_MPP.stem
    tasks_csv = csvs_dir / f"{stem}__tasks.csv"
    resources_csv = csvs_dir / f"{stem}__resources.csv"
    assignments_csv = csvs_dir / f"{stem}__assignments.csv"
    if not (tasks_csv.is_file() and resources_csv.is_file() and assignments_csv.is_file()):
        pytest.skip("CSV-фикстуры mpp_convert не найдены рядом с MPP-фикстурой")

    import json as _json
    empty_template = _json.loads(
        (csvs_dir.parents[1] / "references" / "empty-gantt-template.json").read_text(encoding="utf-8")
    )

    before = mpp_convert_module.convert_mpp_csv(
        tasks_csv, resources_csv, assignments_csv, template_json=empty_template,
    )
    import plan_export  # noqa: F401
    after = mpp_convert_module.convert_mpp_csv(
        tasks_csv, resources_csv, assignments_csv, template_json=empty_template,
    )
    assert before == after


@pytest.fixture
def mpp_convert_module():
    confluence_scripts = (
        ROOT.parent.parent / "hermes-workspace" / "skills" / "productivity"
        / "edit-plan-confluence" / "scripts"
    )
    if str(confluence_scripts) not in sys.path:
        sys.path.insert(0, str(confluence_scripts))
    import mpp_convert
    return mpp_convert


def test_csv_bytes_match_existing_consumer_fixtures(tmp_path):
    """Existing committed CSV expectations, independent of the exporter."""
    import csv
    import read_mpp
    data = read_mpp.read_project(str(FIXTURE_MPP))
    paths = read_mpp.write_csv(data, tmp_path, FIXTURE_MPP.stem)
    assert len(paths) == 3
    for actual in paths:
        expected = FIXTURE_MPP.parent / actual.name
        assert list(csv.DictReader(actual.open())) == list(csv.DictReader(expected.open()))


def test_read_boundary_observer_counts_actual_read_only():
    import read_mpp
    events = []
    project = read_mpp.read_project_file(str(FIXTURE_MPP), read_observer=events.append)
    assert project is not None
    assert events == [{"event":"MPXJ_read", "path":str(FIXTURE_MPP)}]
