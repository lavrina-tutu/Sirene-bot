"""MoveFromFF v2.0 CLI + оркестрация.

ТЗ §3 (полный алгоритм):
  0. Preflight (lock, env, dirs)
  1. Ping Fireflies
  2. Window (test/cron/manual)
  3. Скачивание (skip если в реестре, иначе fetch+write)
  4. Финализация (log.md, registry.md, TG если manual)

Exit codes (ТЗ §9):
  0 — success
  1 — partial success (часть встреч упала)
  2 — lock busy / preflight failed
  3 — FF unavailable / auth-ошибка
  4 — fatal
"""
from __future__ import annotations

import argparse
import sys
import time
import traceback
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import List, Optional, Tuple

from . import __version__
from .config import Settings, load_settings
from .ff_client import FFAuthError, FFClient, FFTransientError
from .ff_schema import FFMeeting
from .filename import utc_iso, utc_now, utc_now_iso
from .lock import LockBusy, acquire_lock
from .logger import append_log_md, get_logger, log_event, setup_logging
from .registry import (
    SCHEMA_VERSION,
    MeetingRecord,
    Registry,
    load_registry,
    save_registry,
)
from .renderer import render_registry_md
from .tg_notifier import send_message
from .writer import atomic_write_text, write_meeting_files

CRON_LOOKBACK = timedelta(hours=4, minutes=30)
TEST_LOOKBACK = timedelta(days=5)


@dataclass
class RunSummary:
    mode: str
    downloaded: int = 0
    skipped: int = 0
    errors: List[Tuple[str, str]] = field(default_factory=list)  # (meeting_id, message)
    fatal: Optional[str] = None
    duration_sec: float = 0.0
    started_at: str = ""

    @property
    def exit_code(self) -> int:
        if self.fatal:
            return 4
        if self.errors:
            return 1
        return 0


# ----------------------------------------------------------------------
# Argparse
# ----------------------------------------------------------------------


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="movefromff",
        description="Fireflies → WorkVault NewMeetings sync (v2.0 minimal).",
    )
    p.add_argument(
        "--mode",
        choices=["test", "cron", "manual"],
        required=True,
        help="Run mode.",
    )
    p.add_argument("--from-date", type=str, default=None, help="manual: YYYY-MM-DD UTC")
    p.add_argument("--to-date", type=str, default=None, help="manual: YYYY-MM-DD UTC")
    p.add_argument("--dry-run", action="store_true", help="Не записывать на диск")
    p.add_argument("--verbose", action="store_true", help="DEBUG-логи")
    p.add_argument("--no-tg", action="store_true", help="Отключить TG в ручном режиме")
    p.add_argument("--version", action="version", version=f"MoveFromFF {__version__}")
    return p


def _parse_date_arg(s: str) -> datetime:
    return datetime.strptime(s, "%Y-%m-%d").replace(tzinfo=timezone.utc)


def _window_for_mode(mode: str, args: argparse.Namespace) -> Tuple[datetime, datetime]:
    now = utc_now()
    if mode == "test":
        return now - TEST_LOOKBACK, now
    if mode == "cron":
        return now - CRON_LOOKBACK, now
    if mode == "manual":
        if not args.from_date or not args.to_date:
            raise ValueError("--mode manual требует --from-date и --to-date")
        f = _parse_date_arg(args.from_date)
        t = _parse_date_arg(args.to_date) + timedelta(days=1) - timedelta(seconds=1)
        if f > t:
            raise ValueError("--from-date должен быть ≤ --to-date")
        return f, t
    raise ValueError(f"Unknown mode: {mode}")


# ----------------------------------------------------------------------
# Per-meeting processing
# ----------------------------------------------------------------------


def _record_from_meeting(meeting: FFMeeting) -> MeetingRecord:
    rec = MeetingRecord()
    rec.title = meeting.display_title
    rec.meeting_date = utc_iso(meeting.meeting_datetime) if meeting.date is not None else None
    rec.duration_minutes = float(meeting.duration) if meeting.duration is not None else None
    rec.participants = list(meeting.participants)
    return rec


def process_meeting(
    meeting: FFMeeting,
    reg: Registry,
    new_dir,
    dry_run: bool,
    summary: RunSummary,
    ff: Optional[FFClient] = None,
) -> None:
    """Обработать одну встречу: skip / download.

    ТЗ §3, шаг 3:
      - meeting_id уже в реестре → skip
      - иначе → fetch full, render, write, добавить запись в реестр (completed)
      - на ошибке: подчистить файлы, в реестр НИЧЕГО не пишем, лог в jsonl
    """
    logger = get_logger()
    mid = meeting.id

    if mid in reg.meetings:
        logger.info(f"SKIP: {mid} '{meeting.display_title}'")
        log_event("skipped", meeting_id=mid, title=meeting.display_title)
        summary.skipped += 1
        return

    if dry_run:
        logger.info(f"PLAN DOWNLOAD: {mid} '{meeting.display_title}'")
        log_event("plan_download", meeting_id=mid, title=meeting.display_title)
        return

    # Подтянуть полную полезную нагрузку (sentences + summary), если у нас лёгкий list-объект.
    full_meeting = meeting
    if ff is not None and not meeting.sentences:
        try:
            fetched = ff.fetch_meeting(mid)
            if fetched is not None:
                full_meeting = fetched
        except Exception as exc:
            logger.warning(f"full fetch failed for {mid}: {exc}; using list payload")

    try:
        files = write_meeting_files(full_meeting, new_dir)
    except Exception as exc:
        logger.exception(f"FAIL write: {mid}: {exc}")
        log_event(
            "download_error",
            meeting_id=mid,
            title=full_meeting.display_title,
            error=f"{type(exc).__name__}: {exc}",
        )
        # ВАЖНО: в реестр НИЧЕГО не пишем. Попадёт в следующее окно.
        summary.errors.append((mid, str(exc)))
        return

    rec = _record_from_meeting(full_meeting)
    rec.files = files
    rec.status = "completed"
    rec.fetched_at = utc_now_iso()
    reg.meetings[mid] = rec

    summary.downloaded += 1
    logger.info(f"WROTE: {mid} '{meeting.display_title}'")
    log_event("download_ok", meeting_id=mid, title=full_meeting.display_title)


# ----------------------------------------------------------------------
# Finalization
# ----------------------------------------------------------------------


def _write_registry_md(settings: Settings, reg: Registry) -> None:
    md = render_registry_md(reg)
    atomic_write_text(settings.registry_md, md)


def _format_tg(summary: RunSummary) -> str:
    if summary.fatal:
        return (
            f"❌ <b>MoveFromFF FATAL</b> ({summary.mode})\n"
            f"<pre>{summary.fatal[:1500]}</pre>"
        )
    head = "✅" if not summary.errors else "⚠️"
    txt = (
        f"{head} <b>MoveFromFF</b> ({summary.mode})\n"
        f"Скачано: {summary.downloaded}\n"
        f"Пропущено: {summary.skipped}\n"
        f"Ошибок: {len(summary.errors)}\n"
        f"⏱ {summary.duration_sec:.1f}s"
    )
    if summary.errors:
        lst = "\n".join(f"• <code>{mid}</code>: {msg[:120]}" for mid, msg in summary.errors[:10])
        txt += f"\n\n<b>Ошибки:</b>\n{lst}"
    return txt


def _tg_should_send(args: argparse.Namespace) -> bool:
    """ТЗ §7: TG шлёт ТОЛЬКО ручной запуск (и только если не --no-tg)."""
    if args.no_tg:
        return False
    return args.mode == "manual"


def _do_preflight(settings: Settings) -> None:
    settings.new_meetings_dir.mkdir(parents=True, exist_ok=True)
    settings.locks_dir.mkdir(parents=True, exist_ok=True)
    settings.logs_dir.mkdir(parents=True, exist_ok=True)


# ----------------------------------------------------------------------
# Entrypoint
# ----------------------------------------------------------------------


def main(argv: Optional[List[str]] = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    try:
        settings = load_settings()
    except Exception as exc:
        sys.stderr.write(f"Config error: {exc}\n")
        return 2

    setup_logging(settings.jsonl_log, verbose=args.verbose)
    logger = get_logger()
    summary = RunSummary(mode=args.mode)
    summary.started_at = utc_now_iso()

    try:
        _do_preflight(settings)
    except Exception as exc:
        logger.error(f"Preflight failed: {exc}")
        return 2

    t0 = time.monotonic()
    try:
        with acquire_lock(settings.lock_file):
            logger.info(
                f"START mode={summary.mode} dry_run={args.dry_run} "
                f"new_meetings_dir={settings.new_meetings_dir}"
            )

            reg = load_registry(settings.registry_json, settings.new_meetings_dir)
            reg.schema_version = SCHEMA_VERSION

            ff = FFClient(settings.fireflies_api_key)
            try:
                ff.ping()
            except (FFAuthError, FFTransientError) as exc:
                logger.error(f"FF unavailable: {exc}")
                summary.fatal = f"FF unavailable: {exc}"
                summary.duration_sec = time.monotonic() - t0
                log_event("ff_unavailable", error=str(exc), mode=summary.mode)
                if not args.dry_run:
                    try:
                        append_log_md(
                            settings.log_md,
                            summary.mode,
                            summary.downloaded,
                            summary.skipped,
                            len(summary.errors),
                            summary.duration_sec,
                        )
                    except Exception:
                        pass
                if _tg_should_send(args):
                    send_message(
                        settings.telegram_bot_token,
                        settings.telegram_chat_id,
                        _format_tg(summary),
                    )
                return 3

            try:
                from_dt, to_dt = _window_for_mode(args.mode, args)
            except ValueError as exc:
                logger.error(f"Bad window: {exc}")
                return 2

            logger.info(f"window UTC: {utc_iso(from_dt)} → {utc_iso(to_dt)}")
            try:
                meetings = ff.fetch_range(from_dt, to_dt)
            except (FFAuthError, FFTransientError) as exc:
                logger.error(f"FF fetch failed: {exc}")
                summary.fatal = f"FF fetch: {exc}"
                summary.duration_sec = time.monotonic() - t0
                log_event("ff_fetch_error", error=str(exc), mode=summary.mode)
                if _tg_should_send(args):
                    send_message(
                        settings.telegram_bot_token,
                        settings.telegram_chat_id,
                        _format_tg(summary),
                    )
                return 3

            logger.info(f"fetched {len(meetings)} meeting(s) from FF")

            for m in meetings:
                try:
                    process_meeting(m, reg, settings.new_meetings_dir, args.dry_run, summary, ff=ff)
                except Exception as exc:
                    logger.exception(f"unexpected per-meeting error {m.id}: {exc}")
                    log_event(
                        "download_error",
                        meeting_id=m.id,
                        error=f"{type(exc).__name__}: {exc}",
                    )
                    summary.errors.append((m.id, str(exc)))

            # Persist (unless dry-run)
            summary.duration_sec = time.monotonic() - t0
            if not args.dry_run:
                save_registry(reg, settings.registry_json)
                _write_registry_md(settings, reg)
                append_log_md(
                    settings.log_md,
                    summary.mode,
                    summary.downloaded,
                    summary.skipped,
                    len(summary.errors),
                    summary.duration_sec,
                )
            else:
                logger.info("DRY-RUN: skipping registry/log writes")

            log_event(
                "run_summary",
                mode=summary.mode,
                downloaded=summary.downloaded,
                skipped=summary.skipped,
                errors=len(summary.errors),
                duration_sec=round(summary.duration_sec, 2),
            )

    except LockBusy as exc:
        sys.stderr.write(f"Lock busy: {exc}\n")
        return 2
    except Exception as exc:
        tb = traceback.format_exc()
        try:
            logger.error(f"FATAL: {exc}\n{tb}")
        except Exception:
            sys.stderr.write(f"FATAL: {exc}\n{tb}\n")
        summary.fatal = f"{type(exc).__name__}: {exc}"
        summary.duration_sec = time.monotonic() - t0
        try:
            if not args.dry_run:
                append_log_md(
                    settings.log_md,
                    summary.mode,
                    summary.downloaded,
                    summary.skipped,
                    len(summary.errors),
                    summary.duration_sec,
                )
        except Exception:
            pass
        if _tg_should_send(args):
            send_message(
                settings.telegram_bot_token,
                settings.telegram_chat_id,
                _format_tg(summary),
            )
        return 4

    # Финальный TG (только manual)
    if _tg_should_send(args):
        send_message(
            settings.telegram_bot_token,
            settings.telegram_chat_id,
            _format_tg(summary),
        )

    return summary.exit_code


if __name__ == "__main__":
    sys.exit(main())
