from __future__ import annotations

from pathlib import Path

from env import load_confluence_env


def test_load_confluence_env_ignores_foreign_keys(tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text(
        "CONFLUENCE_TOKEN=secret-token\n"
        "WORKVAULT_PATH=/tmp/wv\n"
        "OTHER_KEY=should-be-ignored\n"
        "DATABASE_URL=postgres://x\n",
        encoding="utf-8",
    )
    out = load_confluence_env(env_file)
    assert out == {"CONFLUENCE_TOKEN": "secret-token", "WORKVAULT_PATH": "/tmp/wv"}
    assert "OTHER_KEY" not in out
    assert "DATABASE_URL" not in out


def test_unified_only_credentials_do_not_read_local_env(tmp_path, monkeypatch):
    import os
    import env
    import usertools_env
    shared = tmp_path / "shared.env"
    shared.write_text("CONFLUENCE_TOKEN=fixture-token\nUNRELATED_SECRET=ignored\n")
    monkeypatch.setenv("CONFLUENCE_TOKEN", "")  # record absence for teardown, then let the loader populate it
    monkeypatch.delenv("CONFLUENCE_TOKEN")
    monkeypatch.setattr(usertools_env, "_HERMES_ENV", shared)
    monkeypatch.setattr(env.unified, "_HERMES_ENV", shared)
    manifest = env.unified.load_manifest()
    manifest["config"]["tools"]["confluence_sync"]["migration_status"] = "unified_only"
    monkeypatch.setattr(env.unified, "load_manifest", lambda: manifest)
    original = usertools_env._parse_env_file
    paths = []
    def guarded(path):
        paths.append(path)
        assert path == shared
        return original(path)
    monkeypatch.setattr(usertools_env, "_parse_env_file", guarded)
    assert env.get_token() == "fixture-token"
    assert paths == [shared]
    monkeypatch.delenv("UNRELATED_SECRET", raising=False)


def test_python_selection_fails_closed(tmp_path, monkeypatch):
    import env
    import pytest
    from mpp_input import _pick_python
    config = env.Settings({"MPXJ_PYTHON": "/nonexistent/python"}, {})
    with pytest.raises(RuntimeError, match="No working MPXJ Python"):
        env.select_mpxj_python(settings=config)
    monkeypatch.setattr(env, "select_mpxj_python", lambda: (_ for _ in ()).throw(RuntimeError("no runtime")))
    with pytest.raises(RuntimeError, match="no runtime"):
        _pick_python()


def test_process_env_priority_and_no_yaml_write(tmp_path, monkeypatch):
    import env
    path = tmp_path / "config.yaml"
    path.write_text("shared:\n  WORKVAULT_PATH: /fixture/vault\n  CONFLUENCE_URL: https://example.invalid\ntools:\n  edit_plan_confluence:\n    enabled: true\n    CACHE_DIR: /fixture/cache\n")
    before = path.read_bytes()
    monkeypatch.setenv("CACHE_DIR", "/override/cache")
    settings = env.load_settings(ecosystem_path=path)
    assert settings.values["CACHE_DIR"] == "/override/cache"
    assert settings.sources["CACHE_DIR"] == "process_env"
    assert path.read_bytes() == before


def test_save_context_resumes_frozen_paths_without_loader(tmp_path, monkeypatch):
    from plan_context import PlanContext
    context = PlanContext.resolve(db=tmp_path/"state/index.sqlite", workvault=tmp_path/"vault", cache_dir=tmp_path/"parse-cache")
    saved = context.snapshot()
    def forbidden(*a, **k):
        raise AssertionError("resume consulted current defaults")
    monkeypatch.setattr("plan_context.load_settings", forbidden)
    monkeypatch.setattr("env.load_confluence_env", forbidden)
    restored = PlanContext.from_snapshot(saved)
    assert restored.snapshot() == saved
    assert restored.db == context.db and restored.workvault == context.workvault and restored.cache_dir == context.cache_dir
