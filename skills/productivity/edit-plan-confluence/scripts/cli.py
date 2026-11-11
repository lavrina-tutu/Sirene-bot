#!/usr/bin/env python3
"""CLI for edit-plan-confluence skill."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from conf_client import ConfluenceClient
from gate_diff import is_confirmed
from mpp_input import resolve_mpp_path
from pipeline import (
    TEST_PAGE,
    apply_plan,
    create_child_with_plan,
    prepare_apply_diff,
    prepare_child_diff,
    preview_page,
)

SKILL_ROOT = Path(__file__).resolve().parents[1]


def _client() -> ConfluenceClient:
    return ConfluenceClient()


def cmd_preview(args: argparse.Namespace) -> int:
    result = preview_page(_client(), args.page_id, allow_live_ab=args.allow_live_ab)
    print(f"title: {result.title}")
    print(f"macro-id: {result.macro_id}")
    print(f"attachment version: {result.attachment_version}")
    return 0


def _parse_drop_links(values: list[str] | None) -> list[tuple[int, int]] | None:
    """'28:19' / '28-19' → [(28,19)]. Возвращает None если не задано."""
    if not values:
        return None
    out = []
    for v in values:
        v = v.strip().replace("-", ":")
        parts = v.split(":")
        if len(parts) != 2:
            raise argparse.ArgumentTypeError(f"неверный формат --drop-dep '{v}', нужно FROM:TO")
        out.append((int(parts[0].strip()), int(parts[1].strip())))
    return out


def cmd_diff(args: argparse.Namespace) -> int:
    mpp = resolve_mpp_path(args.mpp) if args.mpp else None
    drop = _parse_drop_links(args.drop_dep)
    if args.child:
        title, _gantt, diff, _ = prepare_child_diff(
            _client(), args.page_id, args.title, mpp,
            allow_live_ab=args.allow_live_ab, drop_links=drop,
        )
        print(diff)
        return 0
    if not mpp:
        print("error: --mpp required for diff apply", file=sys.stderr)
        return 2
    _page, _gantt, diff, _ = prepare_apply_diff(
        _client(), args.page_id, mpp,
        allow_live_ab=args.allow_live_ab, drop_links=drop,
    )
    print(diff)
    return 0


def cmd_apply(args: argparse.Namespace) -> int:
    if not is_confirmed(args.confirm or ""):
        print("error: --confirm must be лей|пиши|да", file=sys.stderr)
        return 2
    mpp = resolve_mpp_path(args.mpp) if args.mpp else None
    drop = _parse_drop_links(args.drop_dep)
    if args.child:
        result = create_child_with_plan(
            _client(),
            args.page_id,
            args.confirm,
            title=args.title,
            mpp_path=mpp,
            allow_live_ab=args.allow_live_ab,
            drop_links=drop,
        )
    else:
        if not mpp:
            print("error: --mpp required for apply", file=sys.stderr)
            return 2
        result = apply_plan(
            _client(),
            args.page_id,
            mpp,
            args.confirm,
            allow_live_ab=args.allow_live_ab,
            drop_links=drop,
        )
    print(json.dumps({
        "page_id": result.page_id,
        "title": result.title,
        "page_url": result.page_url,
        "attachment_version": result.attachment_version,
        "itogo": result.itogo_html,
    }, ensure_ascii=False, indent=2))
    return 0


def cmd_convert(args: argparse.Namespace) -> int:
    from mpp_calendar import calendar_from_mpp
    from mpp_convert import convert_mpp_csv
    from mpp_input import export_csv

    mpp = resolve_mpp_path(args.mpp)
    csvs = export_csv(mpp, Path(args.out_dir) if args.out_dir else None)
    calendars = calendar_from_mpp(mpp)
    gantt = convert_mpp_csv(
        csvs.tasks_csv,
        csvs.resources_csv,
        csvs.assignments_csv,
        calendars_data=calendars,
    )
    out = Path(args.out) if args.out else Path("/tmp/gantt_out.json")
    out.write_text(json.dumps(gantt, ensure_ascii=False, indent=2), encoding="utf-8")
    print(out)
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="edit-plan-confluence",
        description="Upload MS Project plan to Confluence gantt-chart-planner macro",
    )
    p.add_argument("--allow-live-ab", action="store_true", help="Allow writes to live AB page 519492935")
    sub = p.add_subparsers(dest="command")

    sp = sub.add_parser("preview", help="Read-only page/macro/attachment info")
    sp.add_argument("--page-id", default=TEST_PAGE)
    sp.set_defaults(func=cmd_preview)

    sd = sub.add_parser("diff", help="Show gate diff before write")
    sd.add_argument("--page-id", required=True)
    sd.add_argument("--mpp")
    sd.add_argument("--child", action="store_true")
    sd.add_argument("--title")
    sd.add_argument("--drop-dep", action="append", metavar="FROM:TO",
                    help="исключить зависимость FROM→TO (можно повторять)")
    sd.set_defaults(func=cmd_diff)

    sa = sub.add_parser("apply", help="Apply plan after confirm")
    sa.add_argument("--page-id", required=True)
    sa.add_argument("--mpp")
    sa.add_argument("--confirm", required=True)
    sa.add_argument("--child", action="store_true")
    sa.add_argument("--title")
    sa.add_argument("--drop-dep", action="append", metavar="FROM:TO",
                    help="исключить зависимость FROM→TO (можно повторять)")
    sa.set_defaults(func=cmd_apply)

    sc = sub.add_parser("convert", help="Offline MPP→JSON convert")
    sc.add_argument("--mpp", required=True)
    sc.add_argument("--out")
    sc.add_argument("--out-dir")
    sc.set_defaults(func=cmd_convert)

    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if not args.command:
        parser.print_help()
        return 0
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
