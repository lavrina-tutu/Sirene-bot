"""Create child Confluence page with gantt macro."""
from __future__ import annotations

from datetime import datetime

from conf_client import ConfluenceClient
from macro import build_macro_html, new_macro_ids
from plan_receipt import read_receipt, write_receipt


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
    *,
    attempt_id: str | None = None,
) -> tuple[dict, str, str, str]:
    """Создать дочернюю страницу с макросом (P1.W1.8).

    При ``attempt_id`` — обёрнуто preflight-квитанцией до/после
    ``client.create_page`` (R-009: первый удалённый эффект дочки). Если
    квитанция ``page_create`` для этого ``attempt_id`` уже содержит
    ``page_id`` (resume после сбоя между POST страницы и upload), созданная
    ранее страница переиспользуется — вторая дочка не создаётся (AC-109).
    """
    if attempt_id:
        existing = read_receipt(attempt_id, "page_create")
        if existing and existing.get("page_id"):
            page = client.get_page(existing["page_id"])
            return (
                page,
                existing["macro_id"],
                existing["param_id"],
                existing["param_hash"],
            )

    parent = client.get_page(parent_id)
    space_key = parent["space"]["key"]
    macro_id, param_id, param_hash = new_macro_ids()
    macro_html = build_macro_html(macro_id, param_id, param_hash)
    storage = build_child_storage(itogo_html, macro_html)

    if attempt_id:
        write_receipt(attempt_id, "page_create", {
            "stage": "page_create", "status": "prepared",
            "parent_id": str(parent_id), "title": title,
            "macro_id": macro_id, "param_id": param_id, "param_hash": param_hash,
        })

    page = client.create_page(title, space_key, storage, parent_id)

    if attempt_id:
        write_receipt(attempt_id, "page_create", {
            "stage": "page_create", "status": "confirmed",
            "parent_id": str(parent_id), "title": title,
            "page_id": str(page["id"]),
            "macro_id": macro_id, "param_id": param_id, "param_hash": param_hash,
        })

    return page, macro_id, param_id, param_hash
