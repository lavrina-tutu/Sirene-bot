"""Unit-тесты v2.0 — оркестрация с моками FFClient (без реального FF API).

Ключевые сценарии ТЗ §11 (DoD):
  - новая встреча скачивается → status=completed, файлы на диске, запись в реестре;
  - уже скачанная встреча пропускается (по meeting_id);
  - ошибка одной встречи → запись НЕ создаётся, остальные продолжают;
  - FF недоступен → exit 3;
  - lock busy → exit 2.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from movefromff import __main__ as main_mod
from movefromff.__main__ import RunSummary, process_meeting
from movefromff.config import Settings
from movefromff.ff_client import FFAuthError, FFTransientError
from movefromff.ff_schema import FFMeeting, FFSentence, FFSummary
from movefromff.registry import MeetingRecord, Registry, load_registry


# ----------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------


def _make_meeting(mid="mid-1", title="Test", date_ms=1779276600000) -> FFMeeting:
    return FFMeeting.model_validate({
        "id": mid,
        "title": title,
        "date": date_ms,
        "duration": 5.0,
        "participants": ["a@b.com"],
        "sentences": [
            FFSentence(speaker_id="A", speaker_name="Иван", text="hi", start_time=1.0),
        ],
        "summary": FFSummary(overview="ov", action_items="ai", keywords=["k"]),
    })


def _make_settings(tmp_path: Path) -> Settings:
    return Settings(
        workvault_path=tmp_path / "vault",
        project_path=tmp_path / "proj",
        fireflies_api_key="dummy",
    )


# ----------------------------------------------------------------------
# Tests: process_meeting (unit-level, без CLI)
# ----------------------------------------------------------------------


def test_new_meeting_downloaded(tmp_path: Path):
    """Новая встреча: рендерим 3 файла + добавляем запись в реестр (status=completed)."""
    new_dir = tmp_path / "NewMeetings"
    new_dir.mkdir()
    reg = Registry()
    summary = RunSummary(mode="test")
    m = _make_meeting("mid-new")

    ff_mock = MagicMock()
    # full fetch не нужен — sentences уже есть; но всё равно мокаем для безопасности
    ff_mock.fetch_meeting.return_value = m

    process_meeting(m, reg, new_dir, dry_run=False, summary=summary, ff=ff_mock)

    assert summary.downloaded == 1
    assert summary.skipped == 0
    assert summary.errors == []
    assert "mid-new" in reg.meetings
    rec = reg.meetings["mid-new"]
    assert rec.status == "completed"
    assert set(rec.files.keys()) == {"transcript", "summary", "actions"}
    # Файлы реально записаны
    for fn in rec.files.values():
        assert (new_dir / fn).exists()
    assert rec.fetched_at is not None and rec.fetched_at.endswith("Z")


def test_already_downloaded_is_skipped(tmp_path: Path):
    """Уже скачанная (есть в реестре) — пропускается, никаких записей файлов."""
    new_dir = tmp_path / "NewMeetings"
    new_dir.mkdir()
    reg = Registry()
    # Положим запись о mid-old в реестр заранее.
    reg.meetings["mid-old"] = MeetingRecord(
        title="Old", status="completed", files={"transcript": "x.md"}
    )

    summary = RunSummary(mode="cron")
    m = _make_meeting("mid-old")

    ff_mock = MagicMock()
    process_meeting(m, reg, new_dir, dry_run=False, summary=summary, ff=ff_mock)

    assert summary.skipped == 1
    assert summary.downloaded == 0
    assert summary.errors == []
    # Не было вызова fetch_meeting (потому что записывать не нужно).
    ff_mock.fetch_meeting.assert_not_called()
    # Никаких новых файлов в директории.
    assert list(new_dir.iterdir()) == []


def test_write_error_does_not_create_registry_entry(tmp_path: Path, monkeypatch):
    """ТЗ §3.4: ошибка записи → в реестр НИЧЕГО не пишем, добавляем в errors."""
    new_dir = tmp_path / "NewMeetings"
    new_dir.mkdir()
    reg = Registry()
    summary = RunSummary(mode="cron")
    m = _make_meeting("mid-err")

    # Заставим writer.write_meeting_files падать
    def boom(meeting, out_dir):
        raise RuntimeError("disk full")

    monkeypatch.setattr(main_mod, "write_meeting_files", boom)

    ff_mock = MagicMock()
    ff_mock.fetch_meeting.return_value = m

    process_meeting(m, reg, new_dir, dry_run=False, summary=summary, ff=ff_mock)

    assert summary.downloaded == 0
    assert len(summary.errors) == 1
    assert summary.errors[0][0] == "mid-err"
    # ВАЖНО: в реестр запись не добавилась
    assert "mid-err" not in reg.meetings


def test_one_meeting_fails_others_continue(tmp_path: Path, monkeypatch):
    """Падение одной встречи не мешает обработать остальные."""
    new_dir = tmp_path / "NewMeetings"
    new_dir.mkdir()
    reg = Registry()
    summary = RunSummary(mode="cron")
    m_ok1 = _make_meeting("mid-ok-1", date_ms=1779276600000)
    m_bad = _make_meeting("mid-bad", date_ms=1779276700000)
    m_ok2 = _make_meeting("mid-ok-2", date_ms=1779276800000)

    real_write = main_mod.write_meeting_files

    def maybe_boom(meeting, out_dir):
        if meeting.id == "mid-bad":
            raise RuntimeError("simulated")
        return real_write(meeting, out_dir)

    monkeypatch.setattr(main_mod, "write_meeting_files", maybe_boom)

    ff_mock = MagicMock()
    ff_mock.fetch_meeting.side_effect = lambda mid: {
        "mid-ok-1": m_ok1, "mid-bad": m_bad, "mid-ok-2": m_ok2
    }[mid]

    for m in (m_ok1, m_bad, m_ok2):
        process_meeting(m, reg, new_dir, dry_run=False, summary=summary, ff=ff_mock)

    assert summary.downloaded == 2
    assert len(summary.errors) == 1
    assert summary.errors[0][0] == "mid-bad"
    assert "mid-ok-1" in reg.meetings
    assert "mid-ok-2" in reg.meetings
    assert "mid-bad" not in reg.meetings


def test_dry_run_no_writes(tmp_path: Path):
    """dry-run: ничего не пишется на диск, в реестр тоже."""
    new_dir = tmp_path / "NewMeetings"
    new_dir.mkdir()
    reg = Registry()
    summary = RunSummary(mode="test")
    m = _make_meeting("mid-dry")

    ff_mock = MagicMock()
    process_meeting(m, reg, new_dir, dry_run=True, summary=summary, ff=ff_mock)

    assert summary.downloaded == 0
    assert summary.skipped == 0
    assert "mid-dry" not in reg.meetings
    assert list(new_dir.iterdir()) == []


# ----------------------------------------------------------------------
# Tests: CLI / main() — с моками FFClient
# ----------------------------------------------------------------------


def _patch_settings(monkeypatch, settings: Settings) -> None:
    monkeypatch.setattr(main_mod, "load_settings", lambda: settings)


def test_main_downloads_new_meetings(tmp_path: Path, monkeypatch):
    """Полный прогон --mode test: одна новая встреча → exit 0, файлы и реестр на диске."""
    settings = _make_settings(tmp_path)
    _patch_settings(monkeypatch, settings)

    m = _make_meeting("mid-new")
    ff_instance = MagicMock()
    ff_instance.ping.return_value = {"user": {"user_id": "u"}}
    ff_instance.fetch_range.return_value = [m]
    ff_instance.fetch_meeting.return_value = m
    monkeypatch.setattr(main_mod, "FFClient", lambda *a, **kw: ff_instance)
    # Отключим TG
    monkeypatch.setattr(main_mod, "send_message", lambda *a, **kw: True)

    code = main_mod.main(["--mode", "test"])

    assert code == 0
    # Реестр существует
    reg_path = settings.registry_json
    assert reg_path.exists()
    data = json.loads(reg_path.read_text(encoding="utf-8"))
    assert data["schema_version"] == "2.0"
    assert "mid-new" in data["meetings"]
    assert data["meetings"]["mid-new"]["status"] == "completed"
    # _registry.md и _log.md тоже
    assert settings.registry_md.exists()
    assert settings.log_md.exists()


def test_main_skips_already_downloaded(tmp_path: Path, monkeypatch):
    """Если встреча уже в реестре — downloaded=0, skipped=1."""
    settings = _make_settings(tmp_path)
    _patch_settings(monkeypatch, settings)

    # Подготовим реестр с уже скачанной встречей
    settings.new_meetings_dir.mkdir(parents=True, exist_ok=True)
    existing = Registry()
    existing.meetings["mid-old"] = MeetingRecord(
        title="Old", status="completed", files={"transcript": "x.md"}
    )
    from movefromff.registry import save_registry
    save_registry(existing, settings.registry_json)

    m = _make_meeting("mid-old")
    ff_instance = MagicMock()
    ff_instance.ping.return_value = {}
    ff_instance.fetch_range.return_value = [m]
    monkeypatch.setattr(main_mod, "FFClient", lambda *a, **kw: ff_instance)
    monkeypatch.setattr(main_mod, "send_message", lambda *a, **kw: True)

    code = main_mod.main(["--mode", "cron"])

    assert code == 0
    # fetch_meeting не должен был дёргаться
    ff_instance.fetch_meeting.assert_not_called()

    # Реестр остался прежним (1 запись)
    data = json.loads(settings.registry_json.read_text(encoding="utf-8"))
    assert list(data["meetings"].keys()) == ["mid-old"]


def test_main_ff_unavailable_returns_3(tmp_path: Path, monkeypatch):
    """Ping FF падает → exit 3."""
    settings = _make_settings(tmp_path)
    _patch_settings(monkeypatch, settings)

    ff_instance = MagicMock()
    ff_instance.ping.side_effect = FFTransientError("HTTP 503")
    monkeypatch.setattr(main_mod, "FFClient", lambda *a, **kw: ff_instance)
    monkeypatch.setattr(main_mod, "send_message", lambda *a, **kw: True)

    code = main_mod.main(["--mode", "test"])
    assert code == 3


def test_main_ff_auth_error_returns_3(tmp_path: Path, monkeypatch):
    settings = _make_settings(tmp_path)
    _patch_settings(monkeypatch, settings)

    ff_instance = MagicMock()
    ff_instance.ping.side_effect = FFAuthError("401")
    monkeypatch.setattr(main_mod, "FFClient", lambda *a, **kw: ff_instance)
    monkeypatch.setattr(main_mod, "send_message", lambda *a, **kw: True)

    code = main_mod.main(["--mode", "test"])
    assert code == 3


def test_main_partial_failure_returns_1(tmp_path: Path, monkeypatch):
    """Если у части встреч произошла ошибка скачивания → exit 1."""
    settings = _make_settings(tmp_path)
    _patch_settings(monkeypatch, settings)

    m_ok = _make_meeting("mid-ok", date_ms=1779276600000)
    m_bad = _make_meeting("mid-bad", date_ms=1779276700000)

    ff_instance = MagicMock()
    ff_instance.ping.return_value = {}
    ff_instance.fetch_range.return_value = [m_ok, m_bad]
    ff_instance.fetch_meeting.side_effect = lambda mid: {"mid-ok": m_ok, "mid-bad": m_bad}[mid]
    monkeypatch.setattr(main_mod, "FFClient", lambda *a, **kw: ff_instance)
    monkeypatch.setattr(main_mod, "send_message", lambda *a, **kw: True)

    # Заставим writer падать только для mid-bad
    real_write = main_mod.write_meeting_files

    def selective_boom(meeting, out_dir):
        if meeting.id == "mid-bad":
            raise RuntimeError("synthetic write fail")
        return real_write(meeting, out_dir)

    monkeypatch.setattr(main_mod, "write_meeting_files", selective_boom)

    code = main_mod.main(["--mode", "test"])
    assert code == 1
    data = json.loads(settings.registry_json.read_text(encoding="utf-8"))
    assert "mid-ok" in data["meetings"]
    assert "mid-bad" not in data["meetings"]


def test_main_lock_busy_returns_2(tmp_path: Path, monkeypatch):
    """Если лок уже занят — exit 2."""
    settings = _make_settings(tmp_path)
    _patch_settings(monkeypatch, settings)

    # Любой FFClient (не должен дёргаться)
    monkeypatch.setattr(main_mod, "FFClient", lambda *a, **kw: MagicMock())
    monkeypatch.setattr(main_mod, "send_message", lambda *a, **kw: True)

    # Захватим лок руками в этом же процессе → второй вызов в main() через
    # `with acquire_lock(...)` должен бросить LockBusy.
    import portalocker
    settings.locks_dir.mkdir(parents=True, exist_ok=True)
    settings.logs_dir.mkdir(parents=True, exist_ok=True)
    settings.new_meetings_dir.mkdir(parents=True, exist_ok=True)
    fh = open(settings.lock_file, "a+")
    portalocker.lock(fh, portalocker.LOCK_EX | portalocker.LOCK_NB)
    try:
        code = main_mod.main(["--mode", "test"])
    finally:
        portalocker.unlock(fh)
        fh.close()

    assert code == 2


def test_main_tg_only_for_manual(tmp_path: Path, monkeypatch):
    """ТЗ §7: TG шлёт ТОЛЬКО --mode manual; cron/test — молчат."""
    settings = _make_settings(tmp_path)
    settings.telegram_bot_token = "token"
    settings.telegram_chat_id = "chat"
    _patch_settings(monkeypatch, settings)

    ff_instance = MagicMock()
    ff_instance.ping.return_value = {}
    ff_instance.fetch_range.return_value = []
    monkeypatch.setattr(main_mod, "FFClient", lambda *a, **kw: ff_instance)

    tg_calls = []
    monkeypatch.setattr(
        main_mod, "send_message", lambda *a, **kw: tg_calls.append(a) or True
    )

    # cron — TG не дёргается
    code = main_mod.main(["--mode", "cron"])
    assert code == 0
    assert tg_calls == []

    # test — TG не дёргается
    code = main_mod.main(["--mode", "test"])
    assert code == 0
    assert tg_calls == []

    # manual — TG отправляется
    code = main_mod.main(["--mode", "manual", "--from-date", "2026-05-19", "--to-date", "2026-05-21"])
    assert code == 0
    assert len(tg_calls) == 1


def test_main_no_tg_flag_suppresses_manual(tmp_path: Path, monkeypatch):
    settings = _make_settings(tmp_path)
    settings.telegram_bot_token = "token"
    settings.telegram_chat_id = "chat"
    _patch_settings(monkeypatch, settings)

    ff_instance = MagicMock()
    ff_instance.ping.return_value = {}
    ff_instance.fetch_range.return_value = []
    monkeypatch.setattr(main_mod, "FFClient", lambda *a, **kw: ff_instance)

    tg_calls = []
    monkeypatch.setattr(
        main_mod, "send_message", lambda *a, **kw: tg_calls.append(a) or True
    )

    code = main_mod.main([
        "--mode", "manual",
        "--from-date", "2026-05-19", "--to-date", "2026-05-21",
        "--no-tg",
    ])
    assert code == 0
    assert tg_calls == []


def test_main_dry_run_no_registry_write(tmp_path: Path, monkeypatch):
    settings = _make_settings(tmp_path)
    _patch_settings(monkeypatch, settings)

    m = _make_meeting("mid-new")
    ff_instance = MagicMock()
    ff_instance.ping.return_value = {}
    ff_instance.fetch_range.return_value = [m]
    ff_instance.fetch_meeting.return_value = m
    monkeypatch.setattr(main_mod, "FFClient", lambda *a, **kw: ff_instance)
    monkeypatch.setattr(main_mod, "send_message", lambda *a, **kw: True)

    code = main_mod.main(["--mode", "test", "--dry-run"])
    assert code == 0
    # Файла _registry.json быть не должно
    assert not settings.registry_json.exists()
    # Файлов встречи тоже нет
    new_files = [p for p in settings.new_meetings_dir.iterdir() if p.is_file()]
    assert new_files == []
