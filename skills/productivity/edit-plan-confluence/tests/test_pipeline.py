from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from conf_client import ConfluenceError
from pipeline import LIVE_AB_PAGE, apply_plan, build_plan_empty, build_plan_from_mpp


def test_build_plan_empty():
    g = build_plan_empty("Мой план")
    assert g["eventsData"][0]["name"] == "Мой план"
    assert g["eventsData"][0]["children"] == []


def test_build_plan_from_mpp_offline(mpp_fixture, gantt_test_template):
    g = build_plan_from_mpp(mpp_fixture, gantt_test_template)
    assert g["idCounter"] != 300000
    assert len(g["calendarsData"][0]["intervals"]) > 4


def test_live_ab_guard():
    from pipeline import _guard_page

    with pytest.raises(PermissionError):
        _guard_page(LIVE_AB_PAGE, allow_live_ab=False)


def _mock_page_no_macro():
    return {
        "id": "519501810",
        "title": "Test Page",
        "version": {"number": 3},
        "body": {"storage": {"value": "<p>Some intro</p>"}},
    }


def test_apply_plan_without_confirm_writes_nothing(mpp_fixture):
    client = MagicMock()
    client.get_page.return_value = _mock_page_no_macro()
    with pytest.raises(PermissionError):
        apply_plan(client, "519501810", mpp_fixture, "нет")
    client.put_page.assert_not_called()
    client.list_attachments.assert_not_called()


def _fresh_page_no_macro(version: int) -> dict:
    return {
        "title": "Test Page",
        "version": {"number": version},
        "body": {"storage": {"value": "<p>Some intro</p>"}},
    }


def test_apply_plan_confirm_order_upload_then_put(mpp_fixture, monkeypatch, isolated_plan_db):
    client = MagicMock()
    client.get_page.side_effect = [
        _mock_page_no_macro(),
        _fresh_page_no_macro(5),
    ]
    client.list_attachments.return_value = []
    client.download_attachment.return_value = b"irrelevant-for-this-test"
    calls = []

    def track_upload(*args, **kwargs):
        calls.append("upload")
        return 2

    monkeypatch.setattr("pipeline.upload_gantt_json", track_upload)
    monkeypatch.setattr("pipeline.verify_uploaded", lambda *a, **k: (True, b""))

    def track_put(*args, **kwargs):
        calls.append("put")
        return {}

    client.put_page.side_effect = track_put
    apply_plan(client, "519501810", mpp_fixture, "лей", project_slug="testpage")
    assert calls == ["upload", "put"]
    client.put_page.assert_called_once()
    assert client.put_page.call_args[0][3] == 6


def test_apply_plan_put_version_is_incremented(mpp_fixture, monkeypatch, isolated_plan_db):
    client = MagicMock()
    client.get_page.side_effect = [
        _mock_page_no_macro(),
        _fresh_page_no_macro(18),
    ]
    client.list_attachments.return_value = []
    monkeypatch.setattr("pipeline.upload_gantt_json", lambda *a, **k: 1)
    monkeypatch.setattr("pipeline.verify_uploaded", lambda *a, **k: (True, b""))
    apply_plan(client, "519501810", mpp_fixture, "лей", project_slug="testpage")
    assert client.put_page.call_args[0][3] == 19


def test_apply_plan_itogo_above_new_macro(mpp_fixture, monkeypatch, isolated_plan_db):
    client = MagicMock()
    client.get_page.side_effect = [
        _mock_page_no_macro(),
        _fresh_page_no_macro(4),
    ]
    client.list_attachments.return_value = []
    monkeypatch.setattr("pipeline.upload_gantt_json", lambda *a, **k: 1)
    monkeypatch.setattr("pipeline.verify_uploaded", lambda *a, **k: (True, b""))
    apply_plan(client, "519501810", mpp_fixture, "лей", project_slug="testpage")
    storage = client.put_page.call_args[0][2]
    macro_pos = storage.index("gantt-chart-planner")
    itogo_pos = storage.index("Итого:")
    assert itogo_pos < macro_pos


def test_apply_plan_fresh_body_patch_preserves_foreign_paragraph(mpp_fixture, monkeypatch, isolated_plan_db):
    """AC-107: чужой абзац, добавленный между diff и apply (в fresh GET),
    сохраняется в итоговом PUT — патч строится от свежего body, не от
    устаревшего диффа."""
    client = MagicMock()
    client.get_page.side_effect = [
        _mock_page_no_macro(),
        {
            "title": "Test Page",
            "version": {"number": 9},
            "body": {"storage": {"value": "<p>Чужой абзац добавлен после diff</p>"}},
        },
    ]
    client.list_attachments.return_value = []
    monkeypatch.setattr("pipeline.upload_gantt_json", lambda *a, **k: 1)
    monkeypatch.setattr("pipeline.verify_uploaded", lambda *a, **k: (True, b""))
    apply_plan(client, "519501810", mpp_fixture, "лей", project_slug="testpage")
    storage = client.put_page.call_args[0][2]
    assert "Чужой абзац добавлен после diff" in storage
    assert client.put_page.call_args[0][3] == 10


def test_apply_plan_preflight_archives_before_put(mpp_fixture, monkeypatch, isolated_plan_db):
    """P1.W1.4: попытка зафиксирована в SQL (plan_import_attempt) ДО put_page."""
    from mofs_index.db import connect

    client = MagicMock()
    client.get_page.side_effect = [
        _mock_page_no_macro(),
        _fresh_page_no_macro(2),
    ]
    client.list_attachments.return_value = []
    monkeypatch.setattr("pipeline.upload_gantt_json", lambda *a, **k: 1)
    monkeypatch.setattr("pipeline.verify_uploaded", lambda *a, **k: (True, b""))

    apply_plan(client, "519501810", mpp_fixture, "лей", project_slug="testpage")

    conn = connect(isolated_plan_db, durable=True)
    attempts = conn.execute("SELECT COUNT(*) FROM plan_import_attempt").fetchone()[0]
    pubs = conn.execute("SELECT COUNT(*) FROM plan_publication").fetchone()[0]
    conn.close()
    assert attempts == 1
    assert pubs == 1


def test_apply_plan_put_409_retries_only_storage_stage(mpp_fixture, monkeypatch, isolated_plan_db):
    """Хвост Фазы 1 (AC-107, P1.W1.6): HTTP 409 на put_page делает свежий
    GET body.storage,version и повторяет ТОЛЬКО эту стадию — upload
    вложения не вызывается повторно, preflight не повторяется."""
    client = MagicMock()
    client.get_page.side_effect = [
        _mock_page_no_macro(),
        _fresh_page_no_macro(5),  # первая попытка fresh GET -> конфликт
        _fresh_page_no_macro(7),  # вторая попытка fresh GET -> успех
    ]
    client.list_attachments.return_value = []
    upload_calls = []
    monkeypatch.setattr(
        "pipeline.upload_gantt_json",
        lambda *a, **k: (upload_calls.append(1), 2)[1],
    )
    monkeypatch.setattr("pipeline.verify_uploaded", lambda *a, **k: (True, b""))

    put_calls = []

    def put_side_effect(page_id, title, storage, version):
        put_calls.append(version)
        if len(put_calls) == 1:
            raise ConfluenceError(409, "version conflict")
        return {}

    client.put_page.side_effect = put_side_effect
    apply_plan(client, "519501810", mpp_fixture, "лей", project_slug="testpage")

    assert len(upload_calls) == 1  # upload вложения не повторён
    assert client.put_page.call_count == 2
    assert put_calls == [6, 8]  # первая попытка от версии 5, вторая — от версии 7
    assert client.get_page.call_count == 3


def test_apply_plan_put_409_exhausted_retries_raises(mpp_fixture, monkeypatch, isolated_plan_db):
    client = MagicMock()
    client.get_page.side_effect = [
        _mock_page_no_macro(),
        _fresh_page_no_macro(5),
        _fresh_page_no_macro(6),
        _fresh_page_no_macro(7),
    ]
    client.list_attachments.return_value = []
    monkeypatch.setattr("pipeline.upload_gantt_json", lambda *a, **k: 1)
    monkeypatch.setattr("pipeline.verify_uploaded", lambda *a, **k: (True, b""))
    client.put_page.side_effect = ConfluenceError(409, "always conflicts")
    with pytest.raises(ConfluenceError):
        apply_plan(client, "519501810", mpp_fixture, "лей", project_slug="testpage")
    assert client.put_page.call_count == 3  # MAX_PUT_409_RETRIES


def test_apply_plan_records_itogo_observation(mpp_fixture, monkeypatch, isolated_plan_db):
    """Хвост Фазы 1 (AC-110): каждый apply автоматически пишет
    plan_page_observation, не только явный вызов record_itogo_observation."""
    from mofs_index.db import connect

    client = MagicMock()
    client.get_page.side_effect = [
        _mock_page_no_macro(),
        _fresh_page_no_macro(2),
    ]
    client.list_attachments.return_value = []
    monkeypatch.setattr("pipeline.upload_gantt_json", lambda *a, **k: 1)
    monkeypatch.setattr("pipeline.verify_uploaded", lambda *a, **k: (True, b""))

    apply_plan(client, "519501810", mpp_fixture, "лей", project_slug="testpage")

    conn = connect(isolated_plan_db, durable=True)
    obs = conn.execute("SELECT COUNT(*) FROM plan_page_observation").fetchone()[0]
    conn.close()
    assert obs == 1


def test_create_child_with_plan_resume_does_not_duplicate_upload(mpp_fixture, monkeypatch, tmp_path):
    """Хвост Фазы 1 (вторая половина AC-109): повтор create_child_with_plan
    с тем же attempt_id после сбоя между созданием дочки и подтверждением
    upload не вызывает upload_gantt_json повторно."""
    from pipeline import create_child_with_plan

    monkeypatch.setattr("plan_receipt.get_workvault_path", lambda: tmp_path / "WorkVault")

    client = MagicMock()
    client.get_page.return_value = {
        "id": "1", "title": "Родитель", "space": {"key": "SP"},
        "body": {"storage": {"value": "<p>no macro</p>"}},
    }
    client.create_page.return_value = {"id": "999"}
    upload_calls = []
    monkeypatch.setattr(
        "pipeline.upload_gantt_json",
        lambda *a, **k: (upload_calls.append(1), 3)[1],
    )

    result1 = create_child_with_plan(
        client, "1", "лей", mpp_path=mpp_fixture, attempt_id="resume-upload-1",
    )
    assert len(upload_calls) == 1
    assert result1.attachment_version == 3

    # Повтор с тем же attempt_id: страница не создаётся повторно (создана
    # child_page.py-резюме), upload тоже не повторяется.
    result2 = create_child_with_plan(
        client, "1", "лей", mpp_path=mpp_fixture, attempt_id="resume-upload-1",
    )
    assert client.create_page.call_count == 1
    assert len(upload_calls) == 1  # не выросло
    assert result2.attachment_version == 3


def test_apply_plan_preflight_failure_blocks_all_http(mpp_fixture, monkeypatch, isolated_plan_db):
    """AC-104: сбой preflight (файл/SQL) — ни один HTTP-запрос (POST/PUT)
    не выполнен."""
    from pipeline import preflight_archive

    client = MagicMock()
    client.get_page.return_value = _mock_page_no_macro()
    client.list_attachments.return_value = []

    def boom(*args, **kwargs):
        raise RuntimeError("simulated SQL/file failure")

    monkeypatch.setattr("pipeline.preflight_archive", boom)
    with pytest.raises(RuntimeError):
        apply_plan(client, "519501810", mpp_fixture, "лей", project_slug="testpage")
    client.list_attachments.assert_not_called()
    client.put_page.assert_not_called()
