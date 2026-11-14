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
