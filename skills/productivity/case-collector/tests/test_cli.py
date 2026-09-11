from __future__ import annotations

import sqlite3
import subprocess
import sys
from pathlib import Path
from unittest import mock

import pytest

from conftest import TEST_SINCE_ISO, TEST_UNTIL_ISO, TS_IN
import case_collector as cc
from split_llm import FakeLlmAdapter


def _run_cli(args: list[str], *, cwd: Path) -> subprocess.CompletedProcess:
    script = cwd / "scripts" / "case_collector.py"
    py = sys.executable
    venv = Path.home() / "hermes-agent" / ".venv" / "bin" / "python3"
    if venv.is_file():
        py = str(venv)
    return subprocess.run(
        [py, str(script), *args],
        cwd=str(cwd),
        capture_output=True,
        text=True,
    )


def test_help_exit_0(skill_root):
    r = _run_cli(["--help"], cwd=skill_root)
    assert r.returncode == 0
    assert "--db" in r.stdout
    assert "--dry-run" in r.stdout
    assert "--since" in r.stdout


def test_missing_since_until(skill_root):
    r = _run_cli(["--since", TEST_SINCE_ISO], cwd=skill_root)
    assert r.returncode == 2


def test_db_not_found(skill_root, tmp_path):
    out = tmp_path / "missing_out.xlsx"
    r = _run_cli(
        [
            "--db",
            str(tmp_path / "nope.db"),
            "--since",
            TEST_SINCE_ISO,
            "--until",
            TEST_UNTIL_ISO,
            "--output",
            str(out),
            "--dry-run",
        ],
        cwd=skill_root,
    )
    assert r.returncode == 2
    assert not out.exists()


def test_model_unresolved(
    skill_root, tmp_path, fixture_db, isolated_output, monkeypatch, capsys
):
    monkeypatch.delenv("CASE_COLLECTOR_LLM_MODEL", raising=False)
    cfg = tmp_path / "config.yaml"
    cfg.write_text("other: x\n", encoding="utf-8")
    code = cc.main(
        [
            "--db",
            str(fixture_db),
            "--since",
            TEST_SINCE_ISO,
            "--until",
            TEST_UNTIL_ISO,
            "--output",
            str(isolated_output),
            "--config",
            str(cfg),
        ]
    )
    assert code == 2
    assert "модель не задана" in capsys.readouterr().err


def test_model_cli_overrides_env_and_config(tmp_path, monkeypatch):
    cfg = tmp_path / "config.yaml"
    cfg.write_text("model:\n  default: from-config\n", encoding="utf-8")
    monkeypatch.setenv("CASE_COLLECTOR_LLM_MODEL", "from-env")
    assert cc.resolve_model("from-cli", cfg) == "from-cli"
    assert cc.resolve_model(None, cfg) == "from-env"
    monkeypatch.delenv("CASE_COLLECTOR_LLM_MODEL", raising=False)
    assert cc.resolve_model(None, cfg) == "from-config"


def test_dry_run_does_not_call_llm(
    skill_root, fixture_db, isolated_output, fake_adapter, monkeypatch
):
    monkeypatch.setattr(
        cc,
        "resolve_backend",
        lambda *a, **k: (_ for _ in ()).throw(AssertionError("LLM called")),
    )
    code = cc.main(
        [
            "--db",
            str(fixture_db),
            "--since",
            TEST_SINCE_ISO,
            "--until",
            TEST_UNTIL_ISO,
            "--output",
            str(isolated_output),
            "--dry-run",
        ]
    )
    assert code == 0
    assert fake_adapter.calls == 0


def test_no_hardcoded_model_slug_in_scripts(scripts_dir):
    for py in scripts_dir.glob("*.py"):
        assert "deepseek/" not in py.read_text(encoding="utf-8")


def test_no_home_tkachenkoav_in_scripts(scripts_dir, skill_root):
    for path in list(scripts_dir.glob("*.py")) + [skill_root / "SKILL.md"]:
        assert "/home/tkachenkoav" not in path.read_text(encoding="utf-8")


def test_exclude_cron_kanban_subagent(
    skill_root, fixture_db, isolated_output, fake_adapter, monkeypatch
):
    monkeypatch.setattr(cc, "resolve_backend", lambda *a, **k: fake_adapter)
    code = cc.main(
        [
            "--db",
            str(fixture_db),
            "--since",
            TEST_SINCE_ISO,
            "--until",
            TEST_UNTIL_ISO,
            "--output",
            str(isolated_output),
            "--model",
            "test-model",
            "--llm-backend",
            "hermes",
        ]
    )
    assert code == 0
    pytest.importorskip("openpyxl")
    from openpyxl import load_workbook

    wb = load_workbook(isolated_output)
    sources = [row[7] for row in wb["Кейсы"].iter_rows(min_row=2, values_only=True) if row[0]]
    for bad in ("cron", "kanban", "subagent"):
        assert bad not in sources


def test_llm_error_does_not_abort(
    skill_root, fixture_db, isolated_output, monkeypatch
):
    def bad_json(payload):
        sid = payload["session_id"]
        if sid == "S-tg-1":
            return "not-json"
        return (
            '{"schema_version":"1.1","session_id":"'
            + sid
            + '","cases":[{"topic":"t","start_msg_id":201,"end_msg_id":202,'
            '"confidence":"high","resolution":"resolved","resolution_reason":"ok"}]}'
        )

    adapter = FakeLlmAdapter(bad_json)
    monkeypatch.setattr(cc, "resolve_backend", lambda *a, **k: adapter)
    code = cc.main(
        [
            "--db",
            str(fixture_db),
            "--since",
            TEST_SINCE_ISO,
            "--until",
            TEST_UNTIL_ISO,
            "--output",
            str(isolated_output),
            "--model",
            "m",
            "--llm-backend",
            "hermes",
        ]
    )
    assert code == 0
    pytest.importorskip("openpyxl")
    from openpyxl import load_workbook

    wb = load_workbook(isolated_output)
    assert wb["Кейсы"].max_row >= 2


def test_volume_warn(skill_root, tmp_path, isolated_output, monkeypatch, capsys):
    db = tmp_path / "big.db"
    conn = sqlite3.connect(db)
    conn.execute(
        "CREATE TABLE sessions (id TEXT PRIMARY KEY, source TEXT, started_at REAL NOT NULL, archived INTEGER)"
    )
    conn.execute(
        """CREATE TABLE messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT, role TEXT, content TEXT, timestamp REAL, active INTEGER
        )"""
    )
    for i in range(201):
        sid = f"S-{i}"
        conn.execute(
            "INSERT INTO sessions VALUES (?, ?, ?, NULL)",
            (sid, "telegram", TS_IN),
        )
        conn.execute(
            "INSERT INTO messages (session_id, role, content, timestamp, active) VALUES (?, ?, ?, ?, ?)",
            (sid, "user", "hi", TS_IN, 1),
        )
    conn.commit()
    conn.close()
    code = cc.main(
        [
            "--db",
            str(db),
            "--since",
            TEST_SINCE_ISO,
            "--until",
            TEST_UNTIL_ISO,
            "--output",
            str(isolated_output),
            "--dry-run",
        ]
    )
    assert code == 0
    captured = capsys.readouterr()
    assert "201" in captured.err or "200" in captured.err


def test_skill_md_has_no_linux_abspath(skill_root):
    assert "/home/tkachenkoav" not in (skill_root / "SKILL.md").read_text(encoding="utf-8")


def test_skill_md_frontmatter(skill_root):
    text = (skill_root / "SKILL.md").read_text(encoding="utf-8")
    assert "name: case-collector" in text
    assert "windows" in text
