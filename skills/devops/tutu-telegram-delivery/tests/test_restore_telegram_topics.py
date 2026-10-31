"""Restore script: narrow YAML allowlist drift → apply → check ok; tokens never in stdout."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

SKILL_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = SKILL_ROOT / "scripts" / "restore_telegram_topics.py"

FAKE_YAML_TOKEN = "8821170000:AAFAKESECRET_c4d5e6f7g8h9i0j1k2l3"
FAKE_ENV_TOKEN = "8630220000:AAFakeSireneTokenValue________"


def _load_module():
    spec = importlib.util.spec_from_file_location("restore_telegram_topics", SCRIPT_PATH)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules["restore_telegram_topics"] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture
def restore_mod():
    return _load_module()


@pytest.fixture
def temp_hermes(monkeypatch, tmp_path):
    home = tmp_path / ".hermes"
    home.mkdir()
    prof = home / "profiles" / "default"
    prof.mkdir(parents=True)
    (home / ".env").write_text(
        f"TELEGRAM_BOT_TOKEN={FAKE_ENV_TOKEN}\n",
        encoding="utf-8",
    )
    (prof / ".env").write_text("\n", encoding="utf-8")
    (home / "config.yaml").write_text(
        "telegram:\n"
        "  allowed_chats: 400307920\n"
        "  require_mention: false\n"
        "  guest_mode: false\n"
        "gateway:\n"
        f"  telegram:\n"
        f"    token: \"{FAKE_YAML_TOKEN}\"\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("HERMES_HOME", str(home))
    monkeypatch.setenv("TG_TOPICS_SNAPSHOT", str(SKILL_ROOT / "references" / "sirene-workspace-topics.yaml"))
    return home


def test_apply_fixes_drift_without_leaking_tokens(restore_mod, temp_hermes, capsys):
    check_code = restore_mod.cmd_check()
    out_check, _ = capsys.readouterr()
    assert check_code != 0
    assert FAKE_YAML_TOKEN not in out_check
    assert FAKE_ENV_TOKEN not in out_check

    apply_code = restore_mod.cmd_apply()
    out_apply, _ = capsys.readouterr()
    assert apply_code == 0
    assert FAKE_YAML_TOKEN not in out_apply
    assert FAKE_ENV_TOKEN not in out_apply

    root_env = (temp_hermes / ".env").read_text(encoding="utf-8")
    prof_env = (temp_hermes / "profiles" / "default" / ".env").read_text(encoding="utf-8")
    assert "TELEGRAM_ADDITIONAL_STARTUP_CHANNELS=-1004300127777:1" in root_env
    assert "TELEGRAM_ADDITIONAL_STARTUP_CHANNELS=-1004300127777:1" in prof_env

    import yaml

    cfg = yaml.safe_load((temp_hermes / "config.yaml").read_text(encoding="utf-8"))
    assert cfg["gateway"]["telegram"]["token"].startswith("863022")
    assert "-1004300127777" in str(cfg["telegram"]["allowed_chats"])

    assert restore_mod.cmd_check() == 0

    mtime_after_apply = (temp_hermes / "config.yaml").stat().st_mtime
    dry_code = restore_mod.cmd_dry_run()
    out_dry, _ = capsys.readouterr()
    assert dry_code == 0
    assert FAKE_ENV_TOKEN not in out_dry
    assert (temp_hermes / "config.yaml").stat().st_mtime == mtime_after_apply
