"""Fireflies GraphQL client с tenacity retry (v2.0).

ТЗ §3: ping + transcripts(fromDate, toDate, limit=50) + transcript(id) для деталей.
audio_url убрано — на тарифе Pro всегда null (ТЗ §2).
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import requests
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from .ff_schema import FFMeeting

FF_ENDPOINT = "https://api.fireflies.ai/graphql"

# Полная схема для transcript(id).
_MEETING_FIELDS_FULL = """
id
title
date
duration
participants
sentences {
  index
  speaker_id
  speaker_name
  text
  start_time
  end_time
}
summary {
  overview
  action_items
  keywords
  outline
}
""".strip()

# Лёгкая схема для transcripts(...) — FF тихо возвращает пустой массив, если
# запрос становится слишком тяжёлым (например, с sentences).
_MEETING_FIELDS_LIST = """
id
title
date
duration
participants
""".strip()


QUERY_PING = "query { user { user_id email } }"

QUERY_TRANSCRIPTS_BY_RANGE = (
    "query Transcripts($from: DateTime, $to: DateTime, $limit: Int, $skip: Int) {\n"
    "  transcripts(fromDate: $from, toDate: $to, limit: $limit, skip: $skip) {\n"
    f"    {_MEETING_FIELDS_LIST}\n"
    "  }\n"
    "}"
)

QUERY_TRANSCRIPT_BY_ID = (
    "query Transcript($id: String!) {\n"
    "  transcript(id: $id) {\n"
    f"    {_MEETING_FIELDS_FULL}\n"
    "  }\n"
    "}"
)


class FFAuthError(RuntimeError):
    pass


class FFNotFound(RuntimeError):
    pass


class FFTransientError(RuntimeError):
    pass


def _iso_z(dt: datetime) -> str:
    dt = dt.astimezone(timezone.utc).replace(microsecond=0)
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


class FFClient:
    def __init__(
        self,
        api_key: str,
        endpoint: str = FF_ENDPOINT,
        timeout: float = 15.0,
        session: Optional[requests.Session] = None,
    ) -> None:
        if not api_key:
            raise FFAuthError("Fireflies API key is empty")
        self.api_key = api_key
        self.endpoint = endpoint
        self.timeout = timeout
        self.session = session or requests.Session()

    @retry(
        reraise=True,
        retry=retry_if_exception_type(FFTransientError),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=2, min=2, max=8),
    )
    def _post(self, query: str, variables: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {"query": query, "variables": variables or {}}
        try:
            r = self.session.post(self.endpoint, json=payload, headers=headers, timeout=self.timeout)
        except requests.RequestException as exc:
            raise FFTransientError(f"Network error: {exc}") from exc

        if r.status_code in (401, 403):
            raise FFAuthError(f"FF auth failed: HTTP {r.status_code} {r.text[:200]}")
        if r.status_code >= 500 or r.status_code == 429:
            raise FFTransientError(f"HTTP {r.status_code}: {r.text[:200]}")
        if r.status_code >= 400:
            raise RuntimeError(f"FF HTTP {r.status_code}: {r.text[:500]}")

        try:
            body = r.json()
        except ValueError as exc:
            raise FFTransientError(f"Invalid JSON from FF: {exc}") from exc

        if "errors" in body and body["errors"]:
            msg = "; ".join(str(e.get("message", e)) for e in body["errors"])
            low = msg.lower()
            if "not found" in low or "no such" in low:
                raise FFNotFound(msg)
            if "unauthorized" in low or "forbidden" in low or "invalid api key" in low:
                raise FFAuthError(msg)
            raise RuntimeError(f"FF GraphQL error: {msg}")

        return body.get("data") or {}

    def ping(self) -> Dict[str, Any]:
        return self._post(QUERY_PING)

    def fetch_meeting(self, meeting_id: str) -> Optional[FFMeeting]:
        try:
            data = self._post(QUERY_TRANSCRIPT_BY_ID, {"id": meeting_id})
        except FFNotFound:
            return None
        m = (data or {}).get("transcript")
        if not m:
            return None
        return FFMeeting.model_validate(m)

    def fetch_range(
        self,
        from_dt: datetime,
        to_dt: datetime,
        page_size: int = 50,
        max_pages: int = 50,
    ) -> List[FFMeeting]:
        out: List[FFMeeting] = []
        skip = 0
        for _ in range(max_pages):
            data = self._post(
                QUERY_TRANSCRIPTS_BY_RANGE,
                {
                    "from": _iso_z(from_dt),
                    "to": _iso_z(to_dt),
                    "limit": page_size,
                    "skip": skip,
                },
            )
            batch = (data or {}).get("transcripts") or []
            if not batch:
                break
            for row in batch:
                try:
                    out.append(FFMeeting.model_validate(row))
                except Exception:
                    continue
            if len(batch) < page_size:
                break
            skip += len(batch)
        return out
