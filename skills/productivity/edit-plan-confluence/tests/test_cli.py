from __future__ import annotations

import subprocess
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
# Единый механизм выбора интерпретатора с mpxj (питфолл: hermes-agent venv без mpxj).
# conftest добавляет scripts/ в sys.path.
from mpp_input import _pick_python  # noqa: E402

PYTHON = Path(_pick_python())


def test_cli_help():
    proc = subprocess.run(
        [str(PYTHON), str(SCRIPTS / "cli.py"), "--help"],
        capture_output=True,
        text=True,
        cwd=str(SCRIPTS),
    )
    assert proc.returncode == 0
    assert "edit-plan-confluence" in proc.stdout


def test_cli_convert_offline(mpp_fixture, tmp_path):
    out = tmp_path / "out.json"
    proc = subprocess.run(
        [
            str(PYTHON),
            str(SCRIPTS / "cli.py"),
            "convert",
            "--mpp",
            str(mpp_fixture),
            "--out",
            str(out),
        ],
        capture_output=True,
        text=True,
        cwd=str(SCRIPTS),
    )
    assert proc.returncode == 0, proc.stderr
    assert out.is_file()
    assert out.stat().st_size > 1000


def test_cli_apply_without_confirm_exit_2():
    proc = subprocess.run(
        [
            str(PYTHON),
            str(SCRIPTS / "cli.py"),
            "apply",
            "--page-id",
            "519501810",
            "--mpp",
            "/nonexistent.mpp",
            "--confirm",
            "нет",
        ],
        capture_output=True,
        text=True,
        cwd=str(SCRIPTS),
    )
    assert proc.returncode == 2


def test_cli_save_parser_global_paths():
    import cli
    args = cli.build_parser().parse_args(["--db", "/fixture/db", "--workvault", "/fixture/vault", "--cache-dir", "/fixture/cache",
        "save", "--mpp", "/fixture/input.zip", "--page-id", "123", "--lineage-id", "line1", "--source-version-date", "2026-11-15"])
    assert args.db == Path("/fixture/db") and args.lineage_id == "line1"
    assert args.source_version_date == "2026-11-15" and args.page_id == "123"


def test_cli_save_argument_errors_are_single_json(tmp_path):
    import json
    from plan_receipt import validate_single_receipt
    for tail in (["save"], ["save", "--mpp", "x", "--db", str(tmp_path/"x.sqlite")]):
        proc = subprocess.run(["/usr/bin/python3", str(SCRIPTS/"cli.py"), *tail], capture_output=True, text=True)
        assert proc.returncode == 2, proc.stderr
        receipt = json.loads(proc.stdout)
        validate_single_receipt(receipt)
        assert receipt["exit_code"] == 2 and receipt["operation_id"] is None


def test_cli_save_runtime_failure_is_single_json(tmp_path):
    import json
    proc = subprocess.run(["/usr/bin/python3", str(SCRIPTS/"cli.py"), "--db", str(tmp_path/"state/index.sqlite"),
        "--workvault", str(tmp_path/"vault"), "--cache-dir", str(tmp_path/"cache"),
        "save", "--mpp", str(tmp_path/"missing.mpp"), "--project-slug", "test"], capture_output=True, text=True)
    assert proc.returncode == 5, proc.stderr
    receipt = json.loads(proc.stdout)
    assert receipt["error"]["code"] == "input_missing" and receipt["item_id"]


def test_cli_rejects_unsupported_global_overrides(tmp_path):
    import json
    proc = subprocess.run(["/usr/bin/python3", str(SCRIPTS/"cli.py"), "--db", str(tmp_path/"db.sqlite"),
        "preview"], capture_output=True, text=True)
    assert proc.returncode == 2 and json.loads(proc.stdout)["error"]["code"] == "invalid_arguments"
