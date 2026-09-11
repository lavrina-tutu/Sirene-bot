#!/usr/bin/env python3
"""Case collector CLI — read-only state.db → xlsx cases."""
from __future__ import annotations

import argparse
import os
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from db import (
    DbNotFoundError,
    SchemaMismatchError,
    SessionRow,
    connect_ro,
    count_sessions_with_activity_in_window_started_outside,
    fetch_messages,
    select_sessions,
)
from identity import UserMap, load_user_map, resolve_display_name
from split_llm import (
    LlmAdapter,
    SplitResult,
    compute_bounds,
    resolve_backend,
    split_session,
)
from transcript import build_compact_transcript, user_char_count
from xlsx_out import CaseRow, SessionInventoryRow, write_deliverable

DEFAULT_EXCLUDE_SOURCES: tuple[str, ...] = ("cron", "kanban", "subagent")
DEFAULT_MAX_INPUT_CHARS: int = 12000
DEFAULT_CONCURRENCY: int = 1
MAX_CONCURRENCY: int = 3
DEFAULT_TZ_NAME: str = "Europe/Moscow"
VOLUME_WARN_THRESHOLD: int = 200
ENV_MODEL: str = "CASE_COLLECTOR_LLM_MODEL"


class ModelNotSetError(Exception):
    pass


@dataclass
class RunConfig:
    since: datetime
    until: datetime
    db_path: Path
    output: Path
    exclude_sources: list[str]
    include_sources: list[str] | None
    user_map_path: Path | None
    model: str
    llm_backend: str
    dry_run: bool
    limit: int | None
    max_input_chars: int
    include_assistant_stubs: bool
    concurrency: int
    tz_name: str
    prefer_origin_user_name: bool
    config_path: Path


@dataclass
class RunStats:
    selected: int
    skipped: int
    llm_ran: int
    cases: int
    llm_error_ids: list[str]
    over_limit: int
    started_outside_count: int
    usage_prompt_tokens: int
    usage_completion_tokens: int


@dataclass
class RunOutput:
    output_path: Path
    output_kind: str
    warned_volume: bool


def default_db_path() -> Path:
    return Path.home() / ".hermes" / "state.db"


def default_config_path() -> Path:
    return Path.home() / ".hermes" / "config.yaml"


def default_output_path(since: datetime, until: datetime) -> Path:
    return (
        Path.home()
        / "WorkVault"
        / "Inbox"
        / f"case-collector_{since:%Y-%m-%d}_{until:%Y-%m-%d}.xlsx"
    )


def parse_window(raw: str, tz: ZoneInfo) -> datetime:
    raw = raw.strip()
    if "T" in raw or "+" in raw or raw.endswith("Z"):
        dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=tz)
        return dt
    parts = raw.split("-")
    if len(parts) == 3:
        y, m, d = int(parts[0]), int(parts[1]), int(parts[2])
        return datetime(y, m, d, 0, 0, tzinfo=tz)
    raise ValueError(f"invalid date window: {raw}")


def load_config_default_model(config_path: Path) -> str | None:
    if not config_path.exists():
        return None
    text = config_path.read_text(encoding="utf-8")
    try:
        import yaml
    except ImportError:
        return None
    cfg = yaml.safe_load(text)
    if not isinstance(cfg, dict):
        return None
    model = cfg.get("model")
    if isinstance(model, dict):
        val = model.get("default")
        if isinstance(val, str) and val.strip():
            return val.strip()
    return None


def resolve_model(cli_model: str | None, config_path: Path) -> str:
    if cli_model and cli_model.strip():
        return cli_model.strip()
    env_val = os.environ.get(ENV_MODEL)
    if env_val and env_val.strip():
        return env_val.strip()
    cfg_val = load_config_default_model(config_path)
    if cfg_val:
        return cfg_val
    raise ModelNotSetError("модель не задана")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Collect semantic cases from Hermes state.db")
    p.add_argument("--since", required=True, help="ISO-8601 window start")
    p.add_argument("--until", required=True, help="ISO-8601 window end (exclusive)")
    p.add_argument("--tz", default=DEFAULT_TZ_NAME, help="Timezone name")
    p.add_argument("--db", type=Path, default=None, help="Path to state.db")
    p.add_argument("--output", type=Path, default=None, help="Output xlsx path or directory")
    p.add_argument(
        "--exclude-sources",
        default=",".join(DEFAULT_EXCLUDE_SOURCES),
        help="Comma-separated sources to exclude",
    )
    p.add_argument("--include-sources", default=None, help="Comma-separated sources whitelist")
    p.add_argument("--user-map", type=Path, default=None, dest="user_map")
    p.add_argument("--model", default=None, help="LLM model slug")
    p.add_argument(
        "--llm-backend",
        default="auto",
        choices=("hermes", "openai-compat", "auto"),
    )
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--limit", type=int, default=None)
    p.add_argument("--max-input-chars", type=int, default=DEFAULT_MAX_INPUT_CHARS)
    p.add_argument("--include-assistant-stubs", action="store_true")
    p.add_argument("--concurrency", type=int, default=DEFAULT_CONCURRENCY)
    p.add_argument("--prefer-origin-user-name", action="store_true")
    p.add_argument("--config", type=Path, default=None, help="Hermes config.yaml path")
    return p.parse_args(argv)


def build_config(ns: argparse.Namespace) -> RunConfig:
    tz = ZoneInfo(ns.tz)
    since = parse_window(ns.since, tz)
    until = parse_window(ns.until, tz)
    if since >= until:
        raise SystemExit("invalid window: --since must be before --until")
    db_path = ns.db if ns.db is not None else default_db_path()
    config_path = ns.config if ns.config is not None else default_config_path()
    output = ns.output if ns.output is not None else default_output_path(since, until)
    if output.is_dir():
        output = output / f"case-collector_{since:%Y-%m-%d}_{until:%Y-%m-%d}.xlsx"
    exclude = [s.strip() for s in ns.exclude_sources.split(",") if s.strip()]
    include = None
    if ns.include_sources:
        include = [s.strip() for s in ns.include_sources.split(",") if s.strip()]
    concurrency = ns.concurrency
    if concurrency < 1 or concurrency > MAX_CONCURRENCY:
        raise SystemExit(f"concurrency must be 1..{MAX_CONCURRENCY}")
    model = ""
    if not ns.dry_run:
        model = resolve_model(ns.model, config_path)
    elif ns.model:
        model = resolve_model(ns.model, config_path)
    return RunConfig(
        since=since,
        until=until,
        db_path=db_path,
        output=output,
        exclude_sources=exclude,
        include_sources=include,
        user_map_path=ns.user_map,
        model=model,
        llm_backend=ns.llm_backend,
        dry_run=ns.dry_run,
        limit=ns.limit,
        max_input_chars=ns.max_input_chars,
        include_assistant_stubs=ns.include_assistant_stubs,
        concurrency=concurrency,
        tz_name=ns.tz,
        prefer_origin_user_name=ns.prefer_origin_user_name,
        config_path=config_path,
    )


def format_chat_report(cfg: RunConfig, stats: RunStats, out: RunOutput) -> str:
    lines = [
        f"Период: {cfg.since.isoformat()} — {cfg.until.isoformat()}",
        f"БД: {cfg.db_path}",
        f"Отобрано: {stats.selected}, пропущено: {stats.skipped}, LLM: {stats.llm_ran}",
        f"Кейсов: {stats.cases}",
        f"Файл ({out.output_kind}): {out.output_path}",
        f"Tokens prompt/completion: {stats.usage_prompt_tokens}/{stats.usage_completion_tokens}",
    ]
    if stats.started_outside_count:
        lines.append(f"Сессий с активностью в окне, но started вне окна: {stats.started_outside_count}")
    if stats.llm_error_ids:
        lines.append(f"llm_error: {', '.join(stats.llm_error_ids)}")
    if out.warned_volume:
        lines.append(f"Предупреждение: отобрано > {VOLUME_WARN_THRESHOLD} сессий без --limit")
    return "\n".join(lines)


def _session_started_iso(row: SessionRow, tz: ZoneInfo) -> str:
    return datetime.fromtimestamp(row.started_at, tz=tz).isoformat()


def process_one_session(
    session: SessionRow,
    messages: list,
    *,
    adapter: LlmAdapter | None,
    model: str,
    user_map: UserMap | None,
    cfg: RunConfig,
) -> tuple[list[CaseRow], SessionInventoryRow]:
    tz = ZoneInfo(cfg.tz_name)
    turns = build_compact_transcript(
        messages,
        tz=tz,
        include_assistant_stubs=cfg.include_assistant_stubs,
    )
    user = resolve_display_name(
        session,
        user_map,
        prefer_origin_user_name=cfg.prefer_origin_user_name,
    )
    u_msgs = sum(1 for t in turns if t.role == "user")
    u_chars = user_char_count(turns)
    inv_base = SessionInventoryRow(
        session_id=session.id,
        user=user,
        source=session.source,
        started_at=_session_started_iso(session, tz),
        message_count=session.message_count or len(messages),
        user_msgs=u_msgs,
        user_chars=u_chars,
        status="ok",
    )
    if not turns:
        inv_base.status = "skipped_empty"
        return [], inv_base

    if cfg.dry_run or adapter is None:
        inv_base.status = "ok" if u_msgs else "skipped_empty"
        return [], inv_base

    split: SplitResult = split_session(
        adapter,
        session_id=session.id,
        turns=turns,
        tz_name=cfg.tz_name,
        max_input_chars=cfg.max_input_chars,
    )
    inv_base.status = split.status
    case_rows: list[CaseRow] = []
    if split.status == "ok":
        for draft in split.cases:
            start_iso, end_iso = compute_bounds(
                turns, draft.start_msg_id, draft.end_msg_id
            )
            case_rows.append(
                CaseRow(
                    user=user,
                    topic=draft.topic,
                    start=start_iso,
                    end=end_iso,
                    session_id=session.id,
                    resolution=draft.resolution,
                    resolution_reason=draft.resolution_reason,
                    source=session.source or "",
                    chat_id=session.chat_id or "",
                    thread_id=session.thread_id or "",
                    session_title=session.title or "",
                    confidence=draft.confidence,
                    flags=",".join(draft.flags),
                    start_msg_id=draft.start_msg_id,
                    end_msg_id=draft.end_msg_id,
                )
            )
    return case_rows, inv_base


def run(cfg: RunConfig) -> tuple[RunStats, RunOutput]:
    warned_volume = False
    conn = connect_ro(cfg.db_path)
    from db import assert_required_schema

    assert_required_schema(conn)
    tz = ZoneInfo(cfg.tz_name)
    since_e = cfg.since.timestamp()
    until_e = cfg.until.timestamp()

    all_matching = select_sessions(
        conn,
        since_epoch=since_e,
        until_epoch=until_e,
        exclude_sources=cfg.exclude_sources,
        include_sources=cfg.include_sources,
        limit=None,
    )
    started_outside = count_sessions_with_activity_in_window_started_outside(
        conn,
        since_epoch=since_e,
        until_epoch=until_e,
        exclude_sources=cfg.exclude_sources,
        include_sources=cfg.include_sources,
    )
    over_limit = 0
    selected = all_matching
    if cfg.limit is not None and len(selected) > cfg.limit:
        over_limit = len(selected) - cfg.limit
        selected = selected[: cfg.limit]
    if len(all_matching) > VOLUME_WARN_THRESHOLD and cfg.limit is None:
        warned_volume = True
        print(
            f"Warning: {len(all_matching)} sessions selected (>{VOLUME_WARN_THRESHOLD}), "
            "consider --limit",
            file=sys.stderr,
        )

    user_map: UserMap | None = None
    if cfg.user_map_path:
        user_map = load_user_map(cfg.user_map_path)

    adapter: LlmAdapter | None = None
    if not cfg.dry_run:
        adapter = resolve_backend(
            cfg.llm_backend, model=cfg.model, config_path=cfg.config_path
        )

    session_data: list[tuple[SessionRow, list]] = []
    for sess in selected:
        session_data.append((sess, fetch_messages(conn, sess.id)))
    conn.close()

    all_cases: list[CaseRow] = []
    inventory: list[SessionInventoryRow] = []
    llm_error_ids: list[str] = []
    llm_ran = 0
    usage_prompt = 0
    usage_completion = 0
    skipped = 0

    def work(item: tuple[SessionRow, list]) -> tuple[list[CaseRow], SessionInventoryRow]:
        sess, msgs = item
        return process_one_session(
            sess,
            msgs,
            adapter=adapter,
            model=cfg.model,
            user_map=user_map,
            cfg=cfg,
        )

    if cfg.concurrency <= 1 or cfg.dry_run:
        for item in session_data:
            cases, inv = work(item)
            inventory.append(inv)
            all_cases.extend(cases)
            if not cfg.dry_run and inv.status not in ("skipped_empty",):
                llm_ran += 1
            if inv.status == "llm_error":
                llm_error_ids.append(inv.session_id)
            if inv.status == "skipped_empty":
                skipped += 1
    else:
        with ThreadPoolExecutor(max_workers=cfg.concurrency) as pool:
            futures = {pool.submit(work, item): item for item in session_data}
            for fut in as_completed(futures):
                cases, inv = fut.result()
                inventory.append(inv)
                all_cases.extend(cases)
                llm_ran += 1
                if inv.status == "llm_error":
                    llm_error_ids.append(inv.session_id)
                if inv.status == "skipped_empty":
                    skipped += 1

    out_path, kind = write_deliverable(cfg.output, all_cases, inventory)
    stats = RunStats(
        selected=len(selected),
        skipped=skipped,
        llm_ran=llm_ran if not cfg.dry_run else 0,
        cases=len(all_cases),
        llm_error_ids=llm_error_ids,
        over_limit=over_limit,
        started_outside_count=started_outside,
        usage_prompt_tokens=usage_prompt,
        usage_completion_tokens=usage_completion,
    )
    out = RunOutput(output_path=out_path, output_kind=kind, warned_volume=warned_volume)
    return stats, out


def main(argv: list[str] | None = None) -> int:
    try:
        ns = parse_args(argv)
        cfg = build_config(ns)
        stats, out = run(cfg)
        print(format_chat_report(cfg, stats, out))
        return 0
    except ModelNotSetError as e:
        print(str(e), file=sys.stderr)
        return 2
    except DbNotFoundError as e:
        print(str(e), file=sys.stderr)
        return 2
    except SchemaMismatchError as e:
        print(str(e), file=sys.stderr)
        return 2
    except SystemExit as e:
        if isinstance(e.code, int):
            return e.code
        print(str(e), file=sys.stderr)
        return 2
    except Exception as e:
        print(str(e), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
