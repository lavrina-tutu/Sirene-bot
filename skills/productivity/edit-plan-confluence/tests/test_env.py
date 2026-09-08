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
