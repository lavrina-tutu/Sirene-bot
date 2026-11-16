from __future__ import annotations

import hashlib

import pytest

from itogo import build_itogo_html
from macro import build_macro_html, find_macro, find_macros
from plan_verify import verify_attachment_bytes, verify_storage_observation

MACRO = build_macro_html("macro-1", "id-1", "macro-hash-1")
STORAGE = '<h2>Проект</h2><p>Посторонний текст</p>' + build_itogo_html("01.01.26", "02.01.26", 2, 0) + MACRO


def verify(storage, actual_version=4):
    return verify_storage_observation(storage, expected_storage=STORAGE, expected_macro=find_macro(MACRO),
                                      expected_itogo=("01.01.26", "02.01.26", 2),
                                      expected_version=4, actual_version=actual_version)


def test_attachment_sha_is_independent_of_macro_hash():
    raw = b"payload"
    assert verify_attachment_bytes(raw, hashlib.sha256(raw).hexdigest()).ok
    assert not verify_attachment_bytes(raw, "macro-hash-1").ok
    assert not verify_attachment_bytes(b"other", hashlib.sha256(raw).hexdigest()).ok


def test_storage_positive_and_xml_attribute_order():
    assert verify(STORAGE).ok
    reordered = STORAGE.replace('ac:name="gantt-chart-planner" ac:schema-version="1"', 'ac:schema-version="1" ac:name="gantt-chart-planner"')
    assert verify(reordered).ok


@pytest.mark.parametrize("storage", [
    STORAGE + MACRO,
    STORAGE.replace("macro-1", "wrong"),
    STORAGE.replace("id-1", "wrong"),
    STORAGE.replace("macro-hash-1", "wrong"),
    STORAGE.replace("2 рабочих", "3 рабочих"),
    STORAGE + build_itogo_html("01.01.26", "02.01.26", 2, 0),
    STORAGE + '<p>Трудозатраты: 10 человеко-часов</p>',
    STORAGE + '<p><strong>Трудозатраты</strong>: 10 ч-ч</p>',
    STORAGE.replace("Посторонний текст", "потерян"),
    STORAGE.replace(MACRO, ""),
    STORAGE + '<ac:structured-macro ac:name="gantt-chart-planner" />',
])
def test_storage_negative_cases(storage):
    assert not verify(storage).ok


def test_exact_page_version_required():
    assert not verify(STORAGE, actual_version=5).ok
    assert not verify(STORAGE, actual_version=3).ok


def test_find_macro_cannot_hide_duplicate_or_incomplete_target():
    assert len(find_macros(MACRO + MACRO)) == 2
    with pytest.raises(ValueError):
        find_macro(MACRO + MACRO)
    with pytest.raises(ValueError):
        find_macro(MACRO + '<ac:structured-macro ac:name="gantt-chart-planner" />')


def test_nested_and_reordered_macro_enumerated():
    reordered = MACRO.replace('ac:name="gantt-chart-planner" ac:schema-version="1"', 'ac:schema-version="1" ac:name="gantt-chart-planner"')
    wrapped = '<ac:structured-macro ac:name="panel"><ac:rich-text-body>' + reordered + '</ac:rich-text-body></ac:structured-macro>'
    assert len(find_macros(wrapped)) == 1
    assert find_macro(wrapped).macro_id == "macro-1"


def test_test_root_rejects_production_symlink(tmp_path):
    from conftest import _validate_test_root
    link = tmp_path / "aliased-production"
    link.symlink_to(__import__('pathlib').Path.home() / "WorkVault", target_is_directory=True)
    with pytest.raises(pytest.UsageError, match="production"):
        _validate_test_root(link)


def test_unit_network_is_disabled():
    import socket
    with pytest.raises(AssertionError, match="network forbidden"):
        socket.create_connection(("example.invalid", 443))


@pytest.mark.archive_integration
def test_archive_client_construction_is_disabled():
    from conf_client import ConfluenceClient
    with pytest.raises(AssertionError, match="ConfluenceClient forbidden"):
        ConfluenceClient(token="test-token")
