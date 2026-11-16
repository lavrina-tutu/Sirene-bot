#!/usr/bin/env python3
"""CLI for edit-plan-confluence skill."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Network/publication dependencies are imported only inside their handlers.
# save can be imported and run with conf_client/pipeline explicitly forbidden.
TEST_PAGE = "519501810"

SKILL_ROOT = Path(__file__).resolve().parents[1]


def _client():
    from conf_client import ConfluenceClient
    return ConfluenceClient()


def cmd_preview(args: argparse.Namespace) -> int:
    from pipeline import preview_page
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
    from pipeline import prepare_child_diff, prepare_apply_diff
    from mpp_input import resolve_mpp_path
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
    from gate_diff import is_confirmed
    from pipeline import apply_plan, create_child_with_plan
    if not is_confirmed(args.confirm or ""):
        print("error: --confirm must be лей|пиши|да", file=sys.stderr)
        return 2
    from mpp_input import resolve_mpp_path
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


def cmd_archive_history(args: argparse.Namespace) -> int:
    """P1.W1.10/11: GET-only импорт истории вложения, не публикация."""
    from plan_history import import_history

    client = _client()
    report = import_history(
        client, args.page_id, args.attachment_id,
        range(args.from_version, args.to_version + 1),
        project_slug=args.project_slug,
    )
    print(json.dumps({
        "page_id": report.page_id,
        "attachment_id": report.attachment_id,
        "event_count": report.event_count,
        "unique_hashes": sorted(report.unique_hashes),
        "outcomes": [
            {"version": o.version, "status": o.status, "sha256": o.sha256, "reason": o.reason}
            for o in report.outcomes
        ],
    }, ensure_ascii=False, indent=2))
    return 0


def cmd_save(args: argparse.Namespace) -> int:
    from plan_save import save_snapshot
    result = save_snapshot(args.mpp, page_id=args.page_id, project_slug=args.project_slug,
        lineage_id=args.lineage_id, timezone_hint=args.timezone_hint,
        source_version_date=args.source_version_date, db_path=args.db,
        workvault=args.workvault, cache_dir=args.cache_dir)
    print(json.dumps(result.to_dict(), ensure_ascii=False))
    return result.exit_code


def cmd_batch(args: argparse.Namespace) -> int:
    from plan_batch import create_batch, resume_batch, show_batch
    paths = dict(db_path=args.db, workvault=args.workvault, cache_dir=args.cache_dir)
    if args.batch_command == "save":
        result = create_batch(mpp=args.mpp, manifest=args.manifest, inbox=args.inbox,
            project_slug=args.project_slug, lineage_id=args.lineage_id, timezone_hint=args.timezone_hint,
            batch_id=args.batch_id, on_error=args.on_error, **paths)
    elif args.batch_command == "resume":
        result = resume_batch(args.batch_id, retry_failed=args.retry_failed, retry_decisions=args.retry_decisions, **paths)
    else:
        result = show_batch(args.batch_id, view=args.view, **paths)
    print(json.dumps(result, ensure_ascii=False))
    return result["exit_code"]


def cmd_operation(args):
    from plan_operation import show_operation
    result = show_operation(args.operation_id, db_path=args.db, workvault=args.workvault, cache_dir=args.cache_dir)
    print(json.dumps(result, ensure_ascii=False))
    return result['exit_code']


def cmd_resume(args):
    from plan_decision import register_decision
    result = register_decision(args.operation_id, args.accept_proposal, reason=args.reason,
        rule_scope=args.rule_scope, timezone_hint=args.timezone_hint, mapping_revision=args.mapping_revision,
        db_path=args.db, workvault=args.workvault, cache_dir=args.cache_dir)
    print(json.dumps(result, ensure_ascii=False))
    return result['exit_code']


def cmd_history(args):
    from plan_queries import query_history
    result = query_history(db_path=args.db, workvault=args.workvault, cache_dir=args.cache_dir,
        **{name: getattr(args, name) for name in ('project_slug', 'view', 'order', 'lineage_id',
                                                'since', 'until', 'time_field', 'limit', 'cursor')})
    print(json.dumps(result, ensure_ascii=False))
    return result['exit_code']


class JsonArgumentParser(argparse.ArgumentParser):
    def error(self, message):
        # Stable error; argument strings can contain secrets. Details go to stderr.
        print("Ошибка аргументов CLI", file=sys.stderr)
        action = getattr(self, 'result_action', None)
        if action:
            print(json.dumps({'schema_version': 1, 'action': action, 'exit_code': 2,
                'result': None, 'error': {'code': 'invalid_arguments', 'message': 'Некорректные аргументы CLI'}}, ensure_ascii=False))
            raise SystemExit(2)
        from plan_receipt import single_receipt, batch_receipt
        receipt = batch_receipt(argument_error=True) if getattr(self, "batch_parser", False) or "batch" in sys.argv[1:] else single_receipt()
        receipt.update(exit_code=2, error={"code": "invalid_arguments", "message": "Некорректные аргументы CLI",
                                          "retryable": False, "next_action": "Проверить --help"})
        print(json.dumps(receipt, ensure_ascii=False))
        raise SystemExit(2)


def cmd_convert(args: argparse.Namespace) -> int:
    from mpp_calendar import calendar_from_mpp
    from mpp_convert import convert_mpp_csv
    from mpp_input import export_csv

    from mpp_input import resolve_mpp_path
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
    p = JsonArgumentParser(
        prog="edit-plan-confluence",
        description="Upload MS Project plan to Confluence gantt-chart-planner macro",
    )
    p.add_argument("--db", type=Path, help="MofsIndex SQLite path for this save")
    p.add_argument("--workvault", type=Path, help="WorkVault root for this save")
    p.add_argument("--cache-dir", type=Path, help="Disposable cache root for this save")
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

    sh = sub.add_parser("archive-history", help="GET-only import of attachment version history (P1.W1.10)")
    sh.add_argument("--page-id", required=True)
    sh.add_argument("--attachment-id", required=True)
    sh.add_argument("--from-version", type=int, required=True)
    sh.add_argument("--to-version", type=int, required=True)
    sh.add_argument("--project-slug", default="zd")
    sh.set_defaults(func=cmd_archive_history)

    sv = sub.add_parser("save", help="Save-only MPP snapshot: NOT published, baseline unchanged (R-008/AC-144)")
    sv.add_argument("--mpp", required=True)
    sv.add_argument("--page-id", default=None, help="Привязка к существующей Confluence-линии (без сетевых вызовов)")
    sv.add_argument("--project-slug", default=None)
    sv.add_argument("--timezone-hint", default=None)
    sv.add_argument("--lineage-id", default=None, help="Existing local lineage of the same project")
    sv.add_argument("--source-version-date", default=None, help="Explicit source version date YYYY-MM-DD")
    sv.set_defaults(func=cmd_save)

    batch = sub.add_parser("batch", help="Sequential archive batch; no Confluence")
    batch.batch_parser = True
    commands = batch.add_subparsers(dest="batch_command", required=True)
    bs = commands.add_parser("save", help="Freeze all inputs, then save sequentially")
    bs.batch_parser = True
    inputs = bs.add_mutually_exclusive_group(required=True)
    inputs.add_argument("--mpp", action="append")
    inputs.add_argument("--manifest", type=Path)
    inputs.add_argument("--inbox", type=Path)
    bs.add_argument("--project-slug")
    bs.add_argument("--lineage-id")
    bs.add_argument("--timezone-hint")
    bs.add_argument("--batch-id")
    bs.add_argument("--on-error", choices=("continue", "stop"))
    bs.set_defaults(func=cmd_batch)
    br = commands.add_parser("resume", help="Continue frozen inputs and context")
    br.batch_parser = True
    br.add_argument("--batch-id", required=True)
    br.add_argument("--retry-failed", action="store_true")
    br.add_argument("--retry-decisions", action="store_true")
    br.set_defaults(func=cmd_batch)
    bv = commands.add_parser("show", help="Read current batch state")
    bv.batch_parser = True
    bv.add_argument("--batch-id", required=True)
    bv.add_argument("--view", choices=("all", "errors"), default="all")
    bv.set_defaults(func=cmd_batch)

    operation = sub.add_parser('operation', help='Read saved operation state')
    oc = operation.add_subparsers(dest='operation_command', required=True)
    show = oc.add_parser('show')
    show.result_action = 'show_operation'
    show.add_argument('--operation-id', required=True)
    show.set_defaults(func=cmd_operation)
    resume = sub.add_parser('resume', help='Register a batch-item decision without processing')
    resume.result_action = 'register_batch_decision'
    resume.add_argument('--operation-id', required=True)
    form = resume.add_mutually_exclusive_group()
    form.add_argument('--accept-proposal')
    form.add_argument('--timezone-hint')
    form.add_argument('--mapping-revision')
    resume.add_argument('--rule-scope', choices=('once', 'project'), default='once')
    resume.add_argument('--reason')
    resume.set_defaults(func=cmd_resume)
    history = sub.add_parser('history', help='Typed arrivals/snapshots/publications history')
    history.result_action = 'history'
    history.add_argument('--project-slug', required=True)
    history.add_argument('--view', choices=('files', 'snapshots', 'publications'), default='files')
    history.add_argument('--order', choices=('ingested', 'source'), default='ingested')
    history.add_argument('--lineage-id')
    history.add_argument('--since')
    history.add_argument('--until')
    history.add_argument('--time-field', choices=('received', 'recorded', 'source', 'published'))
    history.add_argument('--limit', type=int, default=100)
    history.add_argument('--cursor')
    history.set_defaults(func=cmd_history)

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
    if args.command not in ("save", "batch", "operation", "resume", "history") and any((args.db, args.workvault, args.cache_dir)):
        parser.error("path overrides are supported for save and batch")
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
