"""Resolve display names for case-collector output."""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from db import SessionRow


@dataclass(frozen=True)
class UserMap:
    by_session_key: dict[str, str]
    by_source_chat_thread: dict[str, str]
    by_thread_id: dict[str, str]
    by_user_id: dict[str, str]


class IdentityAdapter(Protocol):
    def session_key(self, row: SessionRow) -> str | None: ...
    def source(self, row: SessionRow) -> str: ...
    def chat_id(self, row: SessionRow) -> str | None: ...
    def thread_id(self, row: SessionRow) -> str | None: ...
    def user_id(self, row: SessionRow) -> str | None: ...
    def origin(self, row: SessionRow) -> dict: ...
    def chat_topic(self, row: SessionRow) -> str | None: ...
    def origin_user_name(self, row: SessionRow) -> str | None: ...


class DefaultIdentityAdapter:
    def session_key(self, row: SessionRow) -> str | None:
        return row.session_key

    def source(self, row: SessionRow) -> str:
        return row.source

    def chat_id(self, row: SessionRow) -> str | None:
        return row.chat_id

    def thread_id(self, row: SessionRow) -> str | None:
        return row.thread_id

    def user_id(self, row: SessionRow) -> str | None:
        return row.user_id

    def origin(self, row: SessionRow) -> dict:
        if not row.origin_json:
            return {}
        try:
            data = json.loads(row.origin_json)
            return data if isinstance(data, dict) else {}
        except json.JSONDecodeError:
            return {}

    def chat_topic(self, row: SessionRow) -> str | None:
        topic = self.origin(row).get("chat_topic")
        if isinstance(topic, str) and topic.strip():
            return topic.strip()
        return None

    def origin_user_name(self, row: SessionRow) -> str | None:
        name = self.origin(row).get("user_name")
        if isinstance(name, str) and name.strip():
            return name.strip()
        return None


def load_user_map(path: Path) -> UserMap:
    suffix = path.suffix.lower()
    raw: object
    if suffix == ".json":
        raw = json.loads(path.read_text(encoding="utf-8"))
    elif suffix in (".yaml", ".yml"):
        try:
            import yaml
        except ImportError as e:
            raise RuntimeError("поставь PyYAML или дай JSON") from e
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    else:
        raise ValueError(f"unsupported user-map format: {suffix}")

    by_session_key: dict[str, str] = {}
    by_source_chat_thread: dict[str, str] = {}
    by_thread_id: dict[str, str] = {}
    by_user_id: dict[str, str] = {}

    if isinstance(raw, dict):
        if any(k in raw for k in ("session_key", "source_chat_thread", "thread_id", "user_id")):
            sk = raw.get("session_key") or {}
            sct = raw.get("source_chat_thread") or {}
            tid = raw.get("thread_id") or {}
            uid = raw.get("user_id") or {}
            if isinstance(sk, dict):
                by_session_key = {str(k): str(v) for k, v in sk.items()}
            if isinstance(sct, dict):
                by_source_chat_thread = {str(k): str(v) for k, v in sct.items()}
            if isinstance(tid, dict):
                by_thread_id = {str(k): str(v) for k, v in tid.items()}
            if isinstance(uid, dict):
                by_user_id = {str(k): str(v) for k, v in uid.items()}
        else:
            for k, v in raw.items():
                key = str(k)
                val = str(v)
                if key.count(":") >= 3 or key.startswith("agent:"):
                    by_session_key[key] = val
                else:
                    by_thread_id[key] = val
    return UserMap(
        by_session_key=by_session_key,
        by_source_chat_thread=by_source_chat_thread,
        by_thread_id=by_thread_id,
        by_user_id=by_user_id,
    )


def source_chat_thread_key(
    source: str, chat_id: str | None, thread_id: str | None
) -> str:
    return f"{source}:{chat_id or ''}:{thread_id or ''}"


def resolve_display_name(
    row: SessionRow,
    user_map: UserMap | None,
    *,
    adapter: IdentityAdapter | None = None,
    prefer_origin_user_name: bool = False,
) -> str:
    ad = adapter or DefaultIdentityAdapter()
    sk = ad.session_key(row)
    if user_map and sk and sk in user_map.by_session_key:
        return user_map.by_session_key[sk]
    sct = source_chat_thread_key(ad.source(row), ad.chat_id(row), ad.thread_id(row))
    if user_map and sct in user_map.by_source_chat_thread:
        return user_map.by_source_chat_thread[sct]
    tid = ad.thread_id(row)
    if user_map and tid and tid in user_map.by_thread_id:
        return user_map.by_thread_id[tid]
    uid = ad.user_id(row)
    if user_map and uid and uid in user_map.by_user_id:
        return user_map.by_user_id[uid]
    if prefer_origin_user_name:
        oun = ad.origin_user_name(row)
        if oun:
            return oun
    topic = ad.chat_topic(row)
    if topic:
        return topic
    return sct
