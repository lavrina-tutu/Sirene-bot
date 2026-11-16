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


def reconcile_created_child(client, parent_id, title, expected_storage):
    """An uncertain page POST is resolved by exact parent/title and owned IDs.

    An occupied title or an ambiguous result is a conflict, never permission to
    create another page. Failed lookup leaves the outcome unknown.
    """
    from plan_reconcile import PublishConflict
    from plan_verify import managed_state
    candidates = client.find_child_pages(parent_id, title)
    if not candidates:
        return None
    if len(candidates) != 1:
        raise PublishConflict('child_target_conflict')
    candidate = client.get_page(candidates[0]['id'],expand='body.storage,version,space,ancestors')
    ancestors=candidate.get('ancestors',[])
    if not ancestors or str(ancestors[-1]['id'])!=str(parent_id):
        raise PublishConflict('child_target_conflict')
    if candidate.get('title') != title or managed_state(candidate['body']['storage']['value']) != managed_state(expected_storage):
        raise PublishConflict('child_target_conflict')
    return candidate


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
    from plan_reconcile import PublishConflict
    from plan_verify import managed_state
    existing = read_receipt(attempt_id, "page_create") if attempt_id else None
    if existing:
        if existing.get('parent_id')!=str(parent_id) or existing.get('title')!=title or not existing.get('storage'):
            raise PublishConflict('child_context_incomplete')
        macro_id,param_id,param_hash=(existing[k] for k in ('macro_id','param_id','param_hash'))
        storage=build_child_storage(itogo_html,build_macro_html(macro_id,param_id,param_hash))
        if managed_state(storage)!=managed_state(existing['storage']):
            raise PublishConflict('child_target_conflict')
        page=(client.get_page(existing['page_id']) if existing.get('page_id') else
              reconcile_created_child(client,parent_id,title,storage))
        if page is not None:
            if str(page.get('id'))!=str(existing.get('page_id',page['id'])) or managed_state(page['body']['storage']['value'])!=managed_state(storage):
                raise PublishConflict('child_target_conflict')
            write_receipt(attempt_id,'page_create',{**existing,'page_id':str(page['id']),
                'page_version':page['version']['number'],'status':'confirmed'})
            return page,macro_id,param_id,param_hash
    else:
        macro_id,param_id,param_hash=new_macro_ids()
        storage=build_child_storage(itogo_html,build_macro_html(macro_id,param_id,param_hash))
    parent=client.get_page(parent_id)
    intent={'stage':'page_create','status':'prepared','parent_id':str(parent_id),'title':title,
        'macro_id':macro_id,'param_id':param_id,'param_hash':param_hash,'storage':storage}
    if attempt_id:
        write_receipt(attempt_id,'page_create',intent)
    page=client.create_page(title,parent['space']['key'],storage,parent_id)
    if attempt_id:
        write_receipt(attempt_id,'page_create',{**intent,'status':'confirmed','published':None,
            'external_effect':'storage_written','scope':'page_create_response','page_id':str(page['id']),
            'page_version':page.get('version',{}).get('number')})
    return page,macro_id,param_id,param_hash
