"""ParseIntent unit tests."""
from __future__ import annotations

import pytest

from vestnik_theme_errors import VestnikError
from vestnik_theme_intent import parse_intent


def test_three_ids_order():
  intent = parse_intent(
    page_ids=["517104066", "517103955", "517103930"],
    command_text=None,
    apply=False,
  )
  assert len(intent.page_ids) == 3
  assert intent.page_ids[0] == "517104066"


def test_viewpage_url():
  intent = parse_intent(
    page_ids=[],
    command_text="https://dom.tutu.ru/pages/viewpage.action?pageId=517103930",
    apply=False,
  )
  assert intent.page_ids == ["517103930"]


def test_display_url_stays_raw_ref():
  intent = parse_intent(
    page_ids=[],
    command_text="https://dom.tutu.ru/display/TRAVELCENTER/Some+Title",
    apply=False,
  )
  assert intent.page_ids == []
  assert len(intent.raw_refs) == 1
  assert "display" in intent.raw_refs[0]


def test_month_from_command():
  intent = parse_intent(
    page_ids=["517103930"],
    command_text="добавь в сентябре",
    apply=False,
  )
  assert intent.month == "сентябрь"


def test_tab_name_without_month_not_used():
  intent = parse_intent(
    page_ids=["517103930"],
    command_text="Август-Сентябрь 2026",
    apply=False,
  )
  assert intent.month is None


def test_empty_input_raises():
  with pytest.raises(VestnikError, match="page ids"):
    parse_intent(page_ids=[], command_text=None, apply=False)


def test_free_phrase_not_leak_into_page_ids():
  """«добавь тему в Вестник Новый экран поездок <ссылки>» — только ссылки в id."""
  intent = parse_intent(
    page_ids=[],
    command_text="Новый экран поездок https://dom.tutu.ru/pages/viewpage.action?pageId=517103930 https://dom.tutu.ru/pages/viewpage.action?pageId=517103955",
    apply=False,
  )
  assert intent.page_ids == ["517103930", "517103955"]
  assert not any(c in intent.page_ids for c in ("Новый", "экран", "поездок"))


def test_comma_page_ids_splits():
  intent = parse_intent(
    page_ids=["517103930,517103955,517104066"],
    command_text=None,
    apply=False,
  )
  assert intent.page_ids == ["517103930", "517103955", "517104066"]


def test_theme_extracted_from_free_phrase():
  intent = parse_intent(
    page_ids=[],
    command_text="добавь тему Новый экран поездок https://dom.tutu.ru/pages/viewpage.action?pageId=517103930",
    apply=False,
  )
  assert intent.page_ids == ["517103930"]
  assert intent.theme == "Новый экран поездок"


def test_month_from_command_still_works():
  intent = parse_intent(
    page_ids=["517103930", "517103955,517104066"],
    command_text="добавь тему в сентябре",
    apply=False,
  )
  assert intent.month == "сентябрь"


def test_extract_tab_month_last():
  from vestnik_theme_intent import extract_tab_month
  assert extract_tab_month("Август-Сентябрь 2026") == "сентябрь"
  assert extract_tab_month("Январь 2025") == "январь"
  assert extract_tab_month("") is None


def test_neighbor_month_most_common():
  from vestnik_theme_intent import neighbor_month
  html = "<td>Сентябрь</td><td>Сентябрь</td><td>Октябрь</td>"
  assert neighbor_month(html) == "сентябрь"
