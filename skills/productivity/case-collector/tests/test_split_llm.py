from __future__ import annotations

import json
from pathlib import Path

import pytest

from split_llm import (
    FakeLlmAdapter,
    ValidationError,
    build_payload,
    compute_bounds,
    load_split_prompt,
    mark_overlaps,
    merge_chunk_cases,
    parse_and_validate,
    resolve_backend,
    split_session,
    strip_fences,
)
from split_llm import CaseDraft
from transcript import Turn


def test_parse_valid_json():
    raw = json.dumps(
        {
            "schema_version": "1.1",
            "session_id": "s1",
            "cases": [
                {
                    "topic": "тема",
                    "start_msg_id": 1,
                    "end_msg_id": 2,
                    "confidence": "high",
                    "resolution": "resolved",
                    "resolution_reason": "готово",
                }
            ],
        }
    )
    drafts = parse_and_validate(raw, session_id="s1", allowed_ids={1, 2})
    assert len(drafts) == 1
    assert drafts[0].topic == "тема"
    assert drafts[0].resolution == "resolved"


def test_strip_fences():
    raw = '```json\n{"a":1}\n```'
    assert strip_fences(raw) == '{"a":1}'


def test_session_id_mismatch_raises():
    raw = json.dumps(
        {"schema_version": "1.0", "session_id": "other", "cases": []}
    )
    with pytest.raises(ValidationError):
        parse_and_validate(raw, session_id="s1", allowed_ids=set())


def test_invented_msg_id_dropped_or_retry():
    raw = json.dumps(
        {
            "schema_version": "1.0",
            "session_id": "s1",
            "cases": [{"topic": "t", "start_msg_id": 99, "end_msg_id": 100}],
        }
    )
    assert parse_and_validate(raw, session_id="s1", allowed_ids={1, 2}) == []


def test_confidence_coerced():
    raw = json.dumps(
        {
            "schema_version": "1.0",
            "session_id": "s1",
            "cases": [
                {
                    "topic": "t",
                    "start_msg_id": 1,
                    "end_msg_id": 1,
                    "confidence": "maybe",
                }
            ],
        }
    )
    d = parse_and_validate(raw, session_id="s1", allowed_ids={1})[0]
    assert d.confidence == "medium"


def test_ignore_llm_iso_dates():
    raw = json.dumps(
        {
            "schema_version": "1.0",
            "session_id": "s1",
            "cases": [
                {
                    "topic": "t",
                    "start_msg_id": 1,
                    "end_msg_id": 2,
                    "start": "2020-01-01",
                    "end": "2020-01-02",
                }
            ],
        }
    )
    drafts = parse_and_validate(raw, session_id="s1", allowed_ids={1, 2})
    turns = [
        Turn(1, "2026-09-09T10:00:00+03:00", "user", "a"),
        Turn(2, "2026-09-09T11:00:00+03:00", "user", "b"),
    ]
    start, end = compute_bounds(turns, drafts[0].start_msg_id, drafts[0].end_msg_id)
    assert start.startswith("2026")


def test_compute_bounds_min_max_user():
    turns = [
        Turn(1, "2026-09-09T10:00:00+03:00", "user", "a"),
        Turn(2, "2026-09-09T12:00:00+03:00", "user", "b"),
        Turn(3, "2026-09-09T11:00:00+03:00", "assistant", "stub"),
    ]
    start, end = compute_bounds(turns, 1, 2)
    assert start == "2026-09-09T10:00:00+03:00"
    assert end == "2026-09-09T12:00:00+03:00"


def test_retry_once_then_ok():
    adapter = FakeLlmAdapter(
        {
            "s1": json.dumps(
                {
                    "schema_version": "1.1",
                    "session_id": "s1",
                    "cases": [
                        {
                            "topic": "t",
                            "start_msg_id": 1,
                            "end_msg_id": 1,
                            "confidence": "high",
                            "resolution": "resolved",
                            "resolution_reason": "ok",
                        }
                    ],
                }
            )
        },
        fail_first=True,
    )
    turns = [Turn(1, "t", "user", "hello")]
    res = split_session(
        adapter, session_id="s1", turns=turns, tz_name="Europe/Moscow", max_input_chars=12000
    )
    assert adapter.calls == 2
    assert res.status == "ok"


def test_retry_exhausted_llm_error():
    adapter = FakeLlmAdapter({"s1": "broken json"})
    turns = [Turn(1, "t", "user", "hello")]
    res = split_session(
        adapter, session_id="s1", turns=turns, tz_name="Europe/Moscow", max_input_chars=12000
    )
    assert res.status == "llm_error"


def test_empty_cases_no_task():
    adapter = FakeLlmAdapter(
        {
            "s1": json.dumps(
                {"schema_version": "1.1", "session_id": "s1", "cases": []}
            )
        }
    )
    turns = [Turn(1, "t", "user", "hello")]
    res = split_session(
        adapter, session_id="s1", turns=turns, tz_name="Europe/Moscow", max_input_chars=12000
    )
    assert res.status == "no_task"
    assert adapter.calls >= 1


def test_overlap_flag():
    cases = [
        CaseDraft("a", 1, 5, "high"),
        CaseDraft("b", 4, 8, "high"),
    ]
    marked = mark_overlaps(cases)
    assert all("overlap" in c.flags for c in marked)


def test_chunk_merge_same_topic():
    a = [CaseDraft("Тема А", 1, 2, "high")]
    b = [CaseDraft("тема а", 3, 4, "low")]
    merged = merge_chunk_cases([a, b])
    assert len(merged) == 1
    assert "chunked" in merged[0].flags
    assert merged[0].confidence == "low"


def test_chunk_no_merge_different_topic():
    a = [CaseDraft("одна", 1, 2, "high")]
    b = [CaseDraft("другая", 3, 4, "high")]
    merged = merge_chunk_cases([a, b])
    assert len(merged) == 2


def test_no_second_merge_llm():
    adapter = FakeLlmAdapter({})
    merge_chunk_cases([[CaseDraft("a", 1, 1, "high")], [CaseDraft("a", 2, 2, "high")]])
    assert adapter.calls == 0


def test_fake_no_network():
    adapter = FakeLlmAdapter(
        {
            "s1": json.dumps(
                {
                    "schema_version": "1.1",
                    "session_id": "s1",
                    "cases": [],
                }
            )
        }
    )
    adapter.complete(
        [{"role": "user", "content": '{"session_id":"s1"}'}],
        timeout=1,
        max_tokens=10,
    )
    assert adapter.calls == 1


def test_auto_fail_loud_without_backend(monkeypatch, tmp_path):
    import split_llm as mod

    class FailAdapter:
        def __init__(self, *a, **k):
            raise RuntimeError("hermes backend unavailable")

    monkeypatch.setattr(mod, "HermesCallLlmAdapter", FailAdapter)
    monkeypatch.delenv("CASE_COLLECTOR_LLM_BASE_URL", raising=False)
    monkeypatch.delenv("CASE_COLLECTOR_LLM_API_KEY", raising=False)
    cfg = tmp_path / "config.yaml"
    cfg.write_text("model:\n  default: m1\n", encoding="utf-8")
    with pytest.raises(SystemExit):
        resolve_backend("auto", model="m1", config_path=cfg)


def test_tools_never_in_payload():
    turns = [Turn(1, "t", "user", "hi")]
    payload = build_payload("s1", "Europe/Moscow", turns)
    assert all(t["role"] != "tool" for t in payload["turns"])


def test_no_jira_loop_exchange_jobsjson_in_scripts(scripts_dir):
    patterns = ("jira", "Loop", "Exchange", "jobs.json")
    for py in scripts_dir.glob("*.py"):
        text = py.read_text(encoding="utf-8").lower()
        for pat in patterns:
            assert pat.lower() not in text, f"{py.name} contains {pat}"


def test_two_cases_in_one_session(fake_adapter):
    turns = [Turn(i, "t", "user", "x") for i in range(101, 107)]
    res = split_session(
        fake_adapter,
        session_id="S-tg-1",
        turns=turns,
        tz_name="Europe/Moscow",
        max_input_chars=12000,
    )
    assert res.status == "ok"
    assert len(res.cases) == 2


def test_prompt_file_exists_and_forbids_dates(skill_root):
    path = skill_root / "references" / "split-prompt.md"
    assert path.exists()
    text = path.read_text(encoding="utf-8")
    assert "schema_version" in text
    assert "ISO-даты" in text or "даты" in text
    assert "markdown" in text


def test_no_subprocess_agent_in_scripts(scripts_dir):
    for py in scripts_dir.glob("*.py"):
        text = py.read_text(encoding="utf-8")
        assert "import cursor" not in text
        assert "subprocess" not in text or "agent" not in text


def _case_json(**fields):
    base = {
        "topic": "t",
        "start_msg_id": 1,
        "end_msg_id": 1,
        "confidence": "high",
        "resolution": "resolved",
        "resolution_reason": "reason",
    }
    base.update(fields)
    return base


def test_parse_resolution_missing_or_invalid_coerced_to_unclear():
    for bad in (None, "", "maybe"):
        raw = json.dumps(
            {
                "schema_version": "1.1",
                "session_id": "s1",
                "cases": [_case_json(resolution=bad)],
            },
            default=str,
        )
        d = parse_and_validate(raw, session_id="s1", allowed_ids={1})[0]
        assert d.resolution == "unclear"


def test_parse_schema_10_legacy_resolution():
    raw = json.dumps(
        {
            "schema_version": "1.0",
            "session_id": "s1",
            "cases": [
                {
                    "topic": "t",
                    "start_msg_id": 1,
                    "end_msg_id": 1,
                    "confidence": "high",
                }
            ],
        }
    )
    d = parse_and_validate(raw, session_id="s1", allowed_ids={1})[0]
    assert d.resolution == "unclear"
    assert d.resolution_reason == "нет вердикта в ответе LLM"


def test_split_session_empty_reason_after_retry_ok_with_flag():
    calls = {"n": 0}

    def mapping(payload: dict) -> str:
        calls["n"] += 1
        sid = payload["session_id"]
        return json.dumps(
            {
                "schema_version": "1.1",
                "session_id": sid,
                "cases": [
                    _case_json(
                        resolution="resolved",
                        resolution_reason="",
                    )
                ],
            }
        )

    adapter = FakeLlmAdapter(mapping)
    turns = [Turn(1, "t", "user", "hello")]
    res = split_session(
        adapter, session_id="s1", turns=turns, tz_name="Europe/Moscow", max_input_chars=12000
    )
    assert adapter.calls == 2
    assert res.status == "ok"
    assert res.cases[0].resolution_reason == "(нет обоснования)"
    assert "empty_reason" in res.cases[0].flags


def test_retry_on_empty_mandatory_reason():
    calls = {"n": 0}

    def mapping(payload: dict) -> str:
        calls["n"] += 1
        return json.dumps(
            {
                "schema_version": "1.1",
                "session_id": payload["session_id"],
                "cases": [
                    _case_json(
                        resolution="resolved",
                        resolution_reason="" if calls["n"] == 1 else "ok",
                    )
                ],
            }
        )

    adapter = FakeLlmAdapter(mapping)
    turns = [Turn(1, "t", "user", "x")]
    split_session(
        adapter, session_id="s1", turns=turns, tz_name="Europe/Moscow", max_input_chars=12000
    )
    assert adapter.calls == 2


def test_merge_same_resolution_picks_larger_context_reason():
    turns = [
        Turn(1, "t", "user", "a"),
        Turn(2, "t", "user", "bb"),
        Turn(3, "t", "user", "ccc"),
        Turn(4, "t", "user", "dddd"),
    ]
    a = [
        CaseDraft(
            "Тема",
            1,
            2,
            "high",
            resolution="resolved",
            resolution_reason="ранний",
        )
    ]
    b = [
        CaseDraft(
            "тема",
            3,
            4,
            "low",
            resolution="resolved",
            resolution_reason="поздний и длиннее",
        )
    ]
    merged = merge_chunk_cases([a, b], turns)
    assert merged[0].resolution == "resolved"
    assert merged[0].resolution_reason == "поздний и длиннее"


def test_merge_conflicting_resolution_becomes_unclear():
    turns = [Turn(1, "t", "user", "a"), Turn(2, "t", "user", "b")]
    a = [
        CaseDraft(
            "t",
            1,
            1,
            "high",
            resolution="resolved",
            resolution_reason="да",
        )
    ]
    b = [
        CaseDraft(
            "t",
            2,
            2,
            "high",
            resolution="unresolved",
            resolution_reason="нет",
        )
    ]
    merged = merge_chunk_cases([a, b], turns)
    assert merged[0].resolution == "unclear"
    assert "конфликт" in merged[0].resolution_reason


def test_split_session_propagates_resolution_11():
    raw = json.dumps(
        {
            "schema_version": "1.1",
            "session_id": "s1",
            "cases": [
                {
                    "topic": "настройка",
                    "start_msg_id": 1,
                    "end_msg_id": 1,
                    "confidence": "high",
                    "resolution": "resolved",
                    "resolution_reason": "пользователь подтвердил",
                }
            ],
        }
    )
    adapter = FakeLlmAdapter({"s1": raw})
    turns = [Turn(1, "t", "user", "done")]
    res = split_session(
        adapter, session_id="s1", turns=turns, tz_name="Europe/Moscow", max_input_chars=12000
    )
    assert res.status == "ok"
    assert res.cases[0].resolution == "resolved"
    assert res.cases[0].resolution_reason == "пользователь подтвердил"
