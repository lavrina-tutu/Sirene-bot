"""Create child Confluence page with gantt macro."""
from __future__ import annotations

from datetime import datetime

from conf_client import ConfluenceClient
from macro import build_macro_html, new_macro_ids


def default_child_title(parent_title: str) -> str:
    today = datetime.now().strftime("%d.%m.%y")
    return f"{parent_title}. План {today}"


def build_child_storage(itogo_html: str, macro_html: str) -> str:
    return itogo_html + macro_html


def create_child_page(
    client: ConfluenceClient,
    parent_id: str | int,
    title: str,
    itogo_html: str,
) -> tuple[dict, str, str, str]:
    parent = client.get_page(parent_id)
    space_key = parent["space"]["key"]
    macro_id, param_id, param_hash = new_macro_ids()
    macro_html = build_macro_html(macro_id, param_id, param_hash)
    storage = build_child_storage(itogo_html, macro_html)
    page = client.create_page(title, space_key, storage, parent_id)
    return page, macro_id, param_id, param_hash
