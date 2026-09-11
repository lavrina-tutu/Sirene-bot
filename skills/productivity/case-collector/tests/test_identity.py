from __future__ import annotations

import json
from pathlib import Path

from db import SessionRow
from identity import DefaultIdentityAdapter, load_user_map, resolve_display_name
from identity import UserMap


def test_map_session_key_wins():
    row = SessionRow(
        id="s1",
        source="telegram",
        started_at=1.0,
        session_key="agent:main:telegram:group:chat-example:topic-1",
        chat_id="chat-example",
        thread_id="t-1",
    )
    um = UserMap(
        by_session_key={"agent:main:telegram:group:chat-example:topic-1": "SK win"},
        by_source_chat_thread={"telegram:chat-example:t-1": "SCT lose"},
        by_thread_id={"t-1": "TID lose"},
        by_user_id={"u1": "UID lose"},
    )
    assert resolve_display_name(row, um) == "SK win"


def test_map_source_chat_thread():
    row = SessionRow(
        id="s1", source="telegram", started_at=1.0, chat_id="chat-example", thread_id="t-2"
    )
    um = UserMap({}, {"telegram:chat-example:t-2": "SCT win"}, {}, {})
    assert resolve_display_name(row, um) == "SCT win"


def test_map_thread_id():
    row = SessionRow(id="s1", source="telegram", started_at=1.0, thread_id="topic-3")
    um = UserMap({}, {}, {"topic-3": "TID win"}, {})
    assert resolve_display_name(row, um) == "TID win"


def test_map_user_id():
    row = SessionRow(
        id="s1", source="telegram", started_at=1.0, user_id="u-example"
    )
    um = UserMap({}, {}, {}, {"u-example": "UID win"})
    assert resolve_display_name(row, um) == "UID win"


def test_fallback_chat_topic():
    origin = json.dumps({"chat_topic": "Topic From Origin"})
    row = SessionRow(
        id="s1",
        source="telegram",
        started_at=1.0,
        chat_id="chatA",
        thread_id="t1",
        origin_json=origin,
    )
    assert resolve_display_name(row, None) == "Topic From Origin"


def test_fallback_surrogate():
    row = SessionRow(
        id="s1", source="telegram", started_at=1.0, chat_id="chatA", thread_id="t1"
    )
    assert resolve_display_name(row, None) == "telegram:chatA:t1"


def test_not_linux_user_name_by_default():
    origin = json.dumps({"user_name": "Alex Tkachenko"})
    row = SessionRow(
        id="s1",
        source="telegram",
        started_at=1.0,
        chat_id="chatA",
        thread_id="t1",
        origin_json=origin,
    )
    name = resolve_display_name(row, None)
    assert name != "Alex Tkachenko"
    assert name == "telegram:chatA:t1"


def test_prefer_origin_user_name():
    origin = json.dumps({"user_name": "Windows User"})
    row = SessionRow(
        id="s1",
        source="telegram",
        started_at=1.0,
        chat_id="chatA",
        thread_id="t1",
        origin_json=origin,
    )
    assert (
        resolve_display_name(row, None, prefer_origin_user_name=True) == "Windows User"
    )


def test_display_name_not_default():
    row = SessionRow(
        id="s1",
        source="telegram",
        started_at=1.0,
        chat_id="chatA",
        thread_id="t1",
        display_name="Workspace Bot",
    )
    assert resolve_display_name(row, None) == "telegram:chatA:t1"


def test_bad_origin_json():
    row = SessionRow(
        id="s1",
        source="telegram",
        started_at=1.0,
        chat_id="chatA",
        thread_id="t1",
        origin_json="{not json",
    )
    assert resolve_display_name(row, None) == "telegram:chatA:t1"


def test_example_yaml_loads(skill_root):
    path = skill_root / "references" / "user-map.example.yaml"
    um = load_user_map(path)
    assert um.by_session_key


def test_no_real_linux_ids_in_example(skill_root):
    text = (skill_root / "references" / "user-map.example.yaml").read_text(
        encoding="utf-8"
    )
    assert "-1004300127777" not in text
    assert "400307920" not in text
