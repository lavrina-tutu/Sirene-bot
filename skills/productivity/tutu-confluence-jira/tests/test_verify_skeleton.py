"""Verify skeleton checklist (B0)."""
from __future__ import annotations

from pathlib import Path

from verify_skeleton import verify_from_files, verify_skeleton


def test_verify_ok(storage_ok: str, fixtures_dir: Path):
  result = verify_skeleton(
    storage_ok,
    expected_version=10,
    actual_version=11,
    reference_macro_count=1,
    section_heading="Ключевые поставки и сроки",
    removed_keywords=["ПИЛОТ"],
    reference_td_count=4,
  )
  assert result.ok
  assert all(result.checks.values())


def test_verify_heading_gone_fails(storage_heading_gone: str):
  result = verify_skeleton(
    storage_heading_gone,
    reference_macro_count=1,
    section_heading="Ключевые поставки и сроки",
    reference_td_count=4,
  )
  assert not result.ok
  assert result.checks.get("section_heading") is False


def test_verify_brief_leak_fails(storage_ok: str):
  leaked = storage_ok + "<p>Не копировать из пилота</p>"
  result = verify_skeleton(
    leaked,
    section_heading="Ключевые поставки и сроки",
    reference_macro_count=1,
    reference_td_count=4,
  )
  assert not result.ok
  assert result.checks.get("no_brief_leak") is False


def test_verify_from_files(storage_ok: str, fixtures_dir: Path):
  ok_path = fixtures_dir / "storage_deliveries_ok.xml"
  result = verify_from_files(
    storage_file=ok_path,
    reference_file=ok_path,
    section_heading="Ключевые поставки и сроки",
    version=5,
  )
  assert result.ok
