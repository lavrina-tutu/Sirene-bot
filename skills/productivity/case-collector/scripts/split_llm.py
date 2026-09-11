"""Semantic session split via LLM JSON contract."""
from __future__ import annotations

import json
import re
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Protocol, Sequence

from transcript import Chunk, Turn, chunk_turns

SCHEMA_VERSION: str = "1.1"
SCHEMA_VERSIONS_ALLOWED: frozenset[str] = frozenset({"1.0", "1.1"})
CONFIDENCE_ALLOWED: frozenset[str] = frozenset({"high", "medium", "low"})
RESOLUTION_ALLOWED: frozenset[str] = frozenset(
    {"resolved", "unresolved", "unclear", "n_a"}
)
RESOLUTION_REQUIRES_REASON: frozenset[str] = frozenset(
    {"resolved", "unresolved", "unclear"}
)
LEGACY_NO_VERDICT_REASON: str = "нет вердикта в ответе LLM"
EMPTY_REASON_PLACEHOLDER: str = "(нет обоснования)"
JSON_RETRY_ATTEMPTS: int = 1
DEFAULT_COMPLETE_TIMEOUT: float = 180.0
DEFAULT_MAX_TOKENS: int = 2048
ENV_BASE_URL: str = "CASE_COLLECTOR_LLM_BASE_URL"
ENV_API_KEY: str = "CASE_COLLECTOR_LLM_API_KEY"

_CONF_RANK = {"high": 3, "medium": 2, "low": 1}


class ValidationError(Exception):
    pass


@dataclass
class LlmUsage:
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    estimated_cost_usd: float | None = None


@dataclass
class LlmResult:
    text: str
    usage: LlmUsage | None = None


class LlmAdapter(Protocol):
    model: str

    def complete(
        self,
        messages: list[dict[str, str]],
        *,
        timeout: float,
        max_tokens: int,
    ) -> LlmResult: ...


@dataclass
class CaseDraft:
    topic: str
    start_msg_id: int
    end_msg_id: int
    confidence: str
    resolution: str = "unclear"
    resolution_reason: str = ""
    flags: list[str] = field(default_factory=list)


@dataclass
class SplitResult:
    session_id: str
    cases: list[CaseDraft]
    status: str
    usage: LlmUsage
    raw_error: str | None = None


def load_split_prompt(path: Path | None = None) -> str:
    if path is None:
        path = Path(__file__).resolve().parents[1] / "references" / "split-prompt.md"
    return path.read_text(encoding="utf-8")


def strip_fences(text: str) -> str:
    s = text.strip()
    if s.startswith("```"):
        s = re.sub(r"^```(?:json)?\s*", "", s)
        s = re.sub(r"\s*```$", "", s)
    return s.strip()


def build_payload(
    session_id: str,
    timezone_name: str,
    turns: Sequence[Turn],
    chunk: Chunk | None = None,
) -> dict:
    payload: dict = {
        "session_id": session_id,
        "timezone": timezone_name,
        "turns": [
            {"id": t.id, "ts": t.ts_iso, "role": t.role, "text": t.text} for t in turns
        ],
    }
    if chunk is not None:
        payload["chunk"] = {
            "i": chunk.index,
            "n": chunk.total,
            "overlap_ids": list(chunk.overlap_ids),
        }
    return payload


def build_messages(
    system_prompt: str, payload: dict, *, retry_hint: bool = False
) -> list[dict[str, str]]:
    sys_content = system_prompt
    if retry_hint:
        sys_content += (
            "\n\nверни только JSON по схеме 1.1, с resolution и обоснованием"
        )
    return [
        {"role": "system", "content": sys_content},
        {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
    ]


def _parse_resolution_fields(
    item: dict,
    *,
    legacy_schema: bool,
) -> tuple[str, str]:
    if legacy_schema:
        return "unclear", LEGACY_NO_VERDICT_REASON
    raw_res = item.get("resolution")
    if raw_res is None or str(raw_res).strip() == "":
        resolution = "unclear"
    else:
        resolution = str(raw_res).strip()
        if resolution not in RESOLUTION_ALLOWED:
            resolution = "unclear"
    reason = str(item.get("resolution_reason", "") or "").strip()
    if resolution == "n_a":
        return resolution, reason
    return resolution, reason


def _drafts_need_reason_retry(drafts: list[CaseDraft]) -> bool:
    for d in drafts:
        if d.resolution in RESOLUTION_REQUIRES_REASON and not d.resolution_reason:
            return True
    return False


def _fill_missing_reasons(drafts: list[CaseDraft]) -> None:
    for d in drafts:
        if d.resolution in RESOLUTION_REQUIRES_REASON and not d.resolution_reason:
            d.resolution_reason = EMPTY_REASON_PLACEHOLDER
            if "empty_reason" not in d.flags:
                d.flags.append("empty_reason")


def parse_and_validate(
    raw_text: str,
    *,
    session_id: str,
    allowed_ids: set[int],
) -> list[CaseDraft]:
    data = json.loads(strip_fences(raw_text))
    schema_version = data.get("schema_version")
    if schema_version not in SCHEMA_VERSIONS_ALLOWED:
        raise ValidationError("schema_version mismatch")
    if data.get("session_id") != session_id:
        raise ValidationError("session_id mismatch")
    legacy_schema = schema_version == "1.0"
    cases_raw = data.get("cases")
    if not isinstance(cases_raw, list):
        raise ValidationError("cases must be a list")
    drafts: list[CaseDraft] = []
    for item in cases_raw:
        if not isinstance(item, dict):
            continue
        topic = str(item.get("topic", "")).strip()
        if not topic or len(topic) > 200:
            continue
        try:
            start_id = int(item["start_msg_id"])
            end_id = int(item["end_msg_id"])
        except (KeyError, TypeError, ValueError):
            continue
        if start_id not in allowed_ids or end_id not in allowed_ids or start_id > end_id:
            continue
        conf = str(item.get("confidence", "medium"))
        if conf not in CONFIDENCE_ALLOWED:
            conf = "medium"
        resolution, resolution_reason = _parse_resolution_fields(
            item, legacy_schema=legacy_schema
        )
        drafts.append(
            CaseDraft(
                topic=topic,
                start_msg_id=start_id,
                end_msg_id=end_id,
                confidence=conf,
                resolution=resolution,
                resolution_reason=resolution_reason,
            )
        )
    return drafts


def normalize_topic(topic: str) -> str:
    return " ".join(topic.casefold().split())


def mark_overlaps(cases: list[CaseDraft]) -> list[CaseDraft]:
    for i, a in enumerate(cases):
        for j, b in enumerate(cases):
            if i >= j:
                continue
            if a.start_msg_id <= b.end_msg_id and b.start_msg_id <= a.end_msg_id:
                if "overlap" not in a.flags:
                    a.flags.append("overlap")
                if "overlap" not in b.flags:
                    b.flags.append("overlap")
    return cases


def _worst_confidence(a: str, b: str) -> str:
    ra = _CONF_RANK.get(a, 2)
    rb = _CONF_RANK.get(b, 2)
    return a if ra <= rb else b


def _context_volume(draft: CaseDraft, turns: Sequence[Turn]) -> int:
    total = 0
    for t in turns:
        if draft.start_msg_id <= t.id <= draft.end_msg_id:
            total += len(t.text)
    return total


def _pick_reason_by_context(
    earlier: CaseDraft, later: CaseDraft, turns: Sequence[Turn]
) -> str:
    vol_e = _context_volume(earlier, turns)
    vol_l = _context_volume(later, turns)
    if vol_l > vol_e or vol_l == vol_e:
        return later.resolution_reason
    return earlier.resolution_reason


def _merge_resolution_pair(
    earlier: CaseDraft, later: CaseDraft, turns: Sequence[Turn]
) -> tuple[str, str]:
    if earlier.resolution == later.resolution:
        reason = _pick_reason_by_context(earlier, later, turns)
        return earlier.resolution, reason
    reason = (
        f"конфликт: {earlier.resolution} ({earlier.resolution_reason}) "
        f"vs {later.resolution} ({later.resolution_reason})"
    )
    return "unclear", reason


def merge_chunk_cases(
    per_chunk: list[list[CaseDraft]],
    turns: Sequence[Turn] | None = None,
) -> list[CaseDraft]:
    if not per_chunk:
        return []
    turns = turns or ()
    merged: list[CaseDraft] = list(per_chunk[0])
    for chunk_cases in per_chunk[1:]:
        if not chunk_cases:
            continue
        if merged and chunk_cases:
            last = merged[-1]
            first = chunk_cases[0]
            if normalize_topic(last.topic) == normalize_topic(first.topic):
                resolution, resolution_reason = _merge_resolution_pair(
                    last, first, turns
                )
                merged[-1] = CaseDraft(
                    topic=last.topic,
                    start_msg_id=min(last.start_msg_id, first.start_msg_id),
                    end_msg_id=max(last.end_msg_id, first.end_msg_id),
                    confidence=_worst_confidence(last.confidence, first.confidence),
                    resolution=resolution,
                    resolution_reason=resolution_reason,
                    flags=list(dict.fromkeys([*last.flags, *first.flags, "chunked"])),
                )
                merged.extend(chunk_cases[1:])
                continue
        merged.extend(chunk_cases)
    return merged


def compute_bounds(
    turns: Sequence[Turn],
    start_msg_id: int,
    end_msg_id: int,
) -> tuple[str, str]:
    user_ts = [
        t.ts_iso
        for t in turns
        if t.role == "user" and start_msg_id <= t.id <= end_msg_id
    ]
    if not user_ts:
        raise ValueError("no user turns in range")
    return min(user_ts), max(user_ts)


def _add_usage(total: LlmUsage, part: LlmUsage | None) -> None:
    if part is None:
        return
    if part.prompt_tokens:
        total.prompt_tokens = (total.prompt_tokens or 0) + part.prompt_tokens
    if part.completion_tokens:
        total.completion_tokens = (total.completion_tokens or 0) + part.completion_tokens


def split_session(
    adapter: LlmAdapter,
    *,
    session_id: str,
    turns: Sequence[Turn],
    tz_name: str,
    max_input_chars: int,
    timeout: float = DEFAULT_COMPLETE_TIMEOUT,
    max_tokens: int = DEFAULT_MAX_TOKENS,
) -> SplitResult:
    usage = LlmUsage()
    if not turns:
        return SplitResult(
            session_id=session_id,
            cases=[],
            status="skipped_empty",
            usage=usage,
        )
    allowed_ids = {t.id for t in turns if t.role == "user"}
    chunks = chunk_turns(turns, max_input_chars=max_input_chars)
    system_prompt = load_split_prompt()
    per_chunk: list[list[CaseDraft]] = []

    for chunk in chunks:
        payload = build_payload(session_id, tz_name, chunk.turns, chunk)
        last_error: str | None = None
        drafts: list[CaseDraft] | None = None
        for attempt in range(JSON_RETRY_ATTEMPTS + 1):
            retry_hint = attempt > 0
            messages = build_messages(system_prompt, payload, retry_hint=retry_hint)
            try:
                result = adapter.complete(
                    messages, timeout=timeout, max_tokens=max_tokens
                )
                _add_usage(usage, result.usage)
                drafts = parse_and_validate(
                    result.text,
                    session_id=session_id,
                    allowed_ids=allowed_ids,
                )
                if _drafts_need_reason_retry(drafts) and attempt < JSON_RETRY_ATTEMPTS:
                    last_error = "empty resolution_reason"
                    continue
                _fill_missing_reasons(drafts)
                break
            except (ValidationError, json.JSONDecodeError, RuntimeError) as e:
                last_error = str(e)
                continue
        if drafts is None:
            return SplitResult(
                session_id=session_id,
                cases=[],
                status="llm_error",
                usage=usage,
                raw_error=last_error,
            )
        per_chunk.append(drafts)

    cases = merge_chunk_cases(per_chunk, turns)
    cases = mark_overlaps(cases)
    if not cases:
        return SplitResult(
            session_id=session_id,
            cases=[],
            status="no_task",
            usage=usage,
        )
    return SplitResult(
        session_id=session_id,
        cases=cases,
        status="ok",
        usage=usage,
    )


class FakeLlmAdapter:
    def __init__(
        self,
        mapping: dict[str, str] | Callable[..., str],
        *,
        fail_first: bool = False,
        model: str = "fake",
    ):
        self.mapping = mapping
        self.fail_first = fail_first
        self.model = model
        self.calls = 0
        self._fail_next = fail_first

    def complete(
        self,
        messages: list[dict[str, str]],
        *,
        timeout: float,
        max_tokens: int,
    ) -> LlmResult:
        self.calls += 1
        if self._fail_next:
            self._fail_next = False
            return LlmResult(text="not json {{{")
        payload = json.loads(messages[-1]["content"])
        session_id = payload["session_id"]
        if callable(self.mapping):
            text = self.mapping(payload)
        else:
            text = self.mapping.get(
                session_id,
                '{"schema_version":"1.1","session_id":"'
                + session_id
                + '","cases":[]}',
            )
        return LlmResult(text=text)


class HermesCallLlmAdapter:
    def __init__(self, model: str, hermes_root: Path | None = None):
        self.model = model
        self.hermes_root = hermes_root or Path.home() / "hermes-agent"
        self._call_llm = None

    def _ensure_call_llm(self):
        if self._call_llm is not None:
            return
        root = str(self.hermes_root)
        if root not in sys.path:
            sys.path.insert(0, root)
        try:
            from agent.auxiliary_client import call_llm
        except ImportError as e:
            raise RuntimeError("hermes backend unavailable") from e
        self._call_llm = call_llm

    def complete(
        self,
        messages: list[dict[str, str]],
        *,
        timeout: float,
        max_tokens: int,
    ) -> LlmResult:
        self._ensure_call_llm()
        response = self._call_llm(
            task="case_collector",
            model=self.model,
            messages=messages,
            timeout=timeout,
            max_tokens=max_tokens,
            tools=None,
        )
        content = response.choices[0].message.content
        if not content:
            raise RuntimeError("empty message content")
        usage = None
        if getattr(response, "usage", None):
            u = response.usage
            usage = LlmUsage(
                prompt_tokens=getattr(u, "prompt_tokens", None),
                completion_tokens=getattr(u, "completion_tokens", None),
            )
        return LlmResult(text=content, usage=usage)


class OpenAICompatAdapter:
    def __init__(self, model: str, base_url: str, api_key: str):
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key

    def complete(
        self,
        messages: list[dict[str, str]],
        *,
        timeout: float,
        max_tokens: int,
    ) -> LlmResult:
        url = f"{self.base_url}/chat/completions"
        body = json.dumps(
            {"model": self.model, "messages": messages, "max_tokens": max_tokens}
        ).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=body,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except urllib.error.URLError as e:
            raise RuntimeError(f"openai-compat request failed: {e}") from e
        content = data["choices"][0]["message"]["content"]
        usage = None
        if "usage" in data:
            usage = LlmUsage(
                prompt_tokens=data["usage"].get("prompt_tokens"),
                completion_tokens=data["usage"].get("completion_tokens"),
            )
        return LlmResult(text=content or "", usage=usage)


def _load_yaml_config(config_path: Path) -> dict:
    if not config_path.exists():
        return {}
    text = config_path.read_text(encoding="utf-8")
    try:
        import yaml
    except ImportError:
        return {}
    loaded = yaml.safe_load(text)
    return loaded if isinstance(loaded, dict) else {}


def load_openai_compat_from_env_or_config(
    model: str,
    config_path: Path,
) -> OpenAICompatAdapter:
    import os

    base_url = os.environ.get(ENV_BASE_URL)
    api_key = os.environ.get(ENV_API_KEY)
    cfg = _load_yaml_config(config_path)
    if not base_url or not api_key:
        provider = None
        model_cfg = cfg.get("model") or {}
        if isinstance(model_cfg, dict):
            provider = model_cfg.get("provider")
        if not provider and isinstance(cfg.get("custom_providers"), dict):
            for name in cfg["custom_providers"]:
                provider = name
                break
        providers = cfg.get("custom_providers") or {}
        if provider and isinstance(providers.get(provider), dict):
            pcfg = providers[provider]
            base_url = base_url or pcfg.get("base_url")
            api_key = api_key or pcfg.get("api_key")
    if not base_url or not api_key:
        raise SystemExit("адаптер не сконфигурирован")
    return OpenAICompatAdapter(model=model, base_url=str(base_url), api_key=str(api_key))


def resolve_backend(
    name: str,
    *,
    model: str,
    config_path: Path,
) -> LlmAdapter:
    if name == "hermes":
        try:
            return HermesCallLlmAdapter(model=model)
        except RuntimeError as e:
            raise SystemExit(str(e)) from e
    if name == "openai-compat":
        return load_openai_compat_from_env_or_config(model, config_path)
    if name == "auto":
        try:
            return HermesCallLlmAdapter(model=model)
        except RuntimeError:
            pass
        try:
            return load_openai_compat_from_env_or_config(model, config_path)
        except SystemExit as e:
            raise SystemExit("адаптер не сконфигурирован") from e
    raise SystemExit(f"unknown llm backend: {name}")
