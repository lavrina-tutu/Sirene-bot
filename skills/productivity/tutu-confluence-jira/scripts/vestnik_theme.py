#!/usr/bin/env python3
"""VestnikTheme CLI: add theme row to «Вестник Аналитики и Данных»."""
from __future__ import annotations

import argparse
import json
import sys
from typing import Any, Callable

from userkey_resolve import ConfluenceUserClient
from vestnik_theme_author import confirm_userkey, material_from_page
from vestnik_theme_block import lookup_or_gal, walk_aid_unit
from vestnik_theme_confluence import (
  VESTNIK_PAGE_ID,
  VESTNIK_TITLE,
  fetch_material,
  get_page,
  load_token,
  put_storage,
  resolve_ref,
)
from vestnik_theme_errors import HitlStop, VestnikError, report_technical
from vestnik_theme_ews import resolve_names
from vestnik_theme_intent import (
  MONTH_NAMES,
  extract_tab_month,
  neighbor_month,
  parse_intent,
)
from vestnik_theme_patch import (
  compose_row_inner,
  dedup,
  first_nav_item_span,
  itogovy_table_span,
  patch_first_empty_tr,
)
from vestnik_theme_verify import verify_vestnik

__all__ = ["main", "run_add"]

MAX_PUT_RETRIES = 2


def _build_parser() -> argparse.ArgumentParser:
  parser = argparse.ArgumentParser(description="Add theme row to Vestnik page")
  sub = parser.add_subparsers(dest="command", required=True)
  add = sub.add_parser("add", help="Add material row to Vestnik")
  add.add_argument("--page-id", action="append", default=[], dest="page_ids")
  add.add_argument("--month", default=None)
  add.add_argument("--command-text", default=None)
  add.add_argument("--dry-run", action="store_true", default=False)
  add.add_argument("--apply", action="store_true", default=False)
  add.add_argument("--vestnik-page-id", default=VESTNIK_PAGE_ID)
  return parser


def _preview(
  *,
  month: str | None,
  block: str,
  block_source: str,
  warning: str,
  materials: list,
  author_login: str,
  author_userkey: str,
  tab_name: str,
  version: int,
  apply: bool,
  free_theme: str | None = None,
) -> dict[str, Any]:
  return {
    "dry_run_preview": {
      "month": month or "",
      "block": block,
      "block_source": block_source,
      "warning": warning,
      "theme": materials[0].title if materials else "",
      "free_theme": free_theme or "",
      "materials": [
        {"page_id": m.page_id, "space_key": m.space_key, "title": m.title}
        for m in materials
      ],
      "author_login": author_login,
      "author_userkey": author_userkey,
      "tab_name": tab_name,
      "version": version,
      "apply": apply,
    },
  }


def run_add(
  argv: list[str] | None = None,
  *,
  get_page_fn: Callable | None = None,
  put_fn: Callable | None = None,
  resolve_ref_fn: Callable | None = None,
  fetch_material_fn: Callable | None = None,
  lookup_fn: Callable | None = None,
  walk_fn: Callable | None = None,
  store: Any | None = None,
) -> int:
  parser = _build_parser()
  args = parser.parse_args(argv)

  if args.dry_run and args.apply:
    print("error: --dry-run and --apply are mutually exclusive", file=sys.stderr)
    return 2

  apply = bool(args.apply)
  month_override = args.month

  try:
    intent = parse_intent(
      page_ids=list(args.page_ids or []),
      command_text=args.command_text,
      apply=apply,
    )
  except VestnikError as exc:
    report_technical(exc.stage, exc.message)
    print(exc.message, file=sys.stderr)
    return exc.exit_code

  month = month_override or intent.month
  token = load_token()
  _get_page = get_page_fn or get_page
  _put = put_fn or put_storage
  _resolve = resolve_ref_fn or resolve_ref
  _fetch = fetch_material_fn or fetch_material

  all_ids = list(intent.page_ids)
  for raw in intent.raw_refs:
    try:
      all_ids.append(_resolve(raw, token=token))
    except VestnikError as exc:
      report_technical(exc.stage, exc.message)
      print(exc.message, file=sys.stderr)
      return exc.exit_code

  if not all_ids:
    report_technical("parse", "no page ids after resolve")
    return 1

  materials = []
  for pid in all_ids:
    try:
      if fetch_material_fn:
        materials.append(_fetch(pid, token=token))
      else:
        page = _get_page(pid, token=token)
        materials.append(material_from_page(page, pid))
    except VestnikError as exc:
      report_technical(exc.stage, exc.message)
      print(exc.message, file=sys.stderr)
      return exc.exit_code
    except RuntimeError as exc:
      msg = str(exc)
      if "HTTP 404" in msg:
        report_technical("fetch", msg)
        print(msg, file=sys.stderr)
        return 1
      report_technical("fetch", msg)
      print(msg, file=sys.stderr)
      return 1

  user_cache: dict[str, dict[str, str]] = {}
  client = ConfluenceUserClient(token)
  try:
    author = confirm_userkey(
      materials[0].created_by_userkey,
      client=client,
      cache=user_cache,
    )
  except VestnikError as exc:
    print(exc.message, file=sys.stderr)
    return exc.exit_code

  author_userkey = author["userkey"]
  author_login = materials[0].created_by_username

  block = ""
  block_source = "пусто"
  warning = ""
  gal_nodes: dict = {}

  if lookup_fn:
    try:
      node, block_source = lookup_fn(materials[0].created_by_username)
      block, warning = walk_fn(node) if walk_fn else ("", "")
    except HitlStop as exc:
      print(exc.message)
      return exc.exit_code
  elif store is not None:
    try:
      node, block_source = lookup_or_gal(
        materials[0].created_by_username,
        store=store,
        ews_resolve=resolve_names,
      )
      gal_nodes[node.login] = node
      block, warning = walk_aid_unit(node, store=store, gal_nodes=gal_nodes)
    except HitlStop as exc:
      print(exc.message)
      return exc.exit_code
    except VestnikError as exc:
      report_technical(exc.stage, exc.message)
      print(exc.message, file=sys.stderr)
      return exc.exit_code

  vestnik_id = args.vestnik_page_id
  retries = 0

  while True:
    try:
      vestnik_page = _get_page(vestnik_id, token=token)
    except VestnikError as exc:
      report_technical(exc.stage, exc.message)
      return exc.exit_code
    except RuntimeError as exc:
      report_technical("fetch", str(exc))
      return 1

    storage = vestnik_page["body"]["storage"]["value"]
    version = int(vestnik_page["version"]["number"])
    title = vestnik_page["title"]
    _, _, tab_name = first_nav_item_span(storage)

    import re
    nav_m = re.search(
      r'<ac:structured-macro\s+ac:name="horizontal-nav-item"[^>]*>(.*?)</ac:structured-macro>',
      storage,
      re.IGNORECASE | re.DOTALL,
    )
    table_html = ""
    if nav_m:
      _, _, table_html = itogovy_table_span(nav_m.group(1))

    # Месяц по приоритету: явный (CLI/фраза) > соседние темы > из названия вкладки.
    if not month:
      month = neighbor_month(table_html) or extract_tab_month(tab_name)

    try:
      dedup_result = dedup(table_html, materials, materials[0].title)
    except HitlStop as exc:
      print(exc.message)
      return exc.exit_code

    if dedup_result == "noop":
      preview = _preview(
        month=month,
        block=block,
        block_source=block_source,
        warning=warning,
        materials=materials,
        author_login=author_login,
        author_userkey=author_userkey,
        tab_name=tab_name,
        version=version,
        apply=apply,
        free_theme=intent.theme,
      )
      preview["dry_run_preview"]["noop"] = True
      print(json.dumps(preview, ensure_ascii=False, indent=2))
      return 0

    row_inner = compose_row_inner(
      month=month,
      block=block,
      materials=materials,
      author_userkey=author_userkey,
    )

    if not apply:
      preview = _preview(
        month=month,
        block=block,
        block_source=block_source,
        warning=warning,
        materials=materials,
        author_login=author_login,
        author_userkey=author_userkey,
        tab_name=tab_name,
        version=version,
        apply=False,
        free_theme=intent.theme,
      )
      preview["dry_run_preview"]["row_inner"] = row_inner
      if warning:
        preview["dry_run_preview"]["warning"] = warning
      print(json.dumps(preview, ensure_ascii=False, indent=2))
      return 0

    try:
      new_storage = patch_first_empty_tr(storage, row_inner)
    except VestnikError as exc:
      report_technical(exc.stage, exc.message)
      return exc.exit_code

    try:
      _put(
        vestnik_id,
        title=title,
        current_version=version,
        storage=new_storage,
        token=token,
      )
    except VestnikError as exc:
      if exc.stage == "put" and retries < MAX_PUT_RETRIES:
        retries += 1
        continue
      report_technical(exc.stage, exc.message)
      return exc.exit_code

    after_page = _get_page(vestnik_id, token=token)
    after_storage = after_page["body"]["storage"]["value"]
    after_version = int(after_page["version"]["number"])
    verify = verify_vestnik(
      before_storage=storage,
      after_storage=after_storage,
      before_version=version,
      after_version=after_version,
      expected_min_version=version + 1,
      materials=materials,
      author_userkey=author_userkey,
      first_tab_name=tab_name,
    )
    if not verify.ok:
      report_technical("verify", "; ".join(verify.messages))
      return 1

    preview = _preview(
      month=month,
      block=block,
      block_source=block_source,
      warning=warning,
      materials=materials,
      author_login=author_login,
      author_userkey=author_userkey,
      tab_name=tab_name,
      version=after_version,
      apply=True,
      free_theme=intent.theme,
    )
    print(json.dumps(preview, ensure_ascii=False, indent=2))
    return 0


def main(argv: list[str] | None = None) -> int:
  try:
    return run_add(argv)
  except HitlStop as exc:
    print(exc.message)
    return exc.exit_code
  except VestnikError as exc:
    report_technical(exc.stage, exc.message)
    print(exc.message, file=sys.stderr)
    return exc.exit_code


if __name__ == "__main__":
  raise SystemExit(main())
