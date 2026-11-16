"""Gate diff text before Confluence writes."""
from __future__ import annotations

from typing import Any

from env import page_url
from itogo import build_itogo_html, compute_itogo_from_gantt
from mpp_convert import count_tasks


CONFIRM_WORDS = frozenset({"лей", "пиши", "да"})


def is_confirmed(text: str) -> bool:
    return text.strip().lower() in CONFIRM_WORDS


def format_itogo_pair(d1: str, d2: str, n: int, m: int) -> str:
    return build_itogo_html(d1, d2, n, m).replace("<p><strong>", "").replace("</strong></p>", "\n")


def build_diff(
    *,
    page_id: str | int,
    title: str,
    operation: str,
    gantt: dict[str, Any] | None = None,
    had_existing_plan: bool = False,
    child_title: str | None = None,
    warnings: list[str] | None = None,
    empty_plan: bool = False,
    itogo_before: str | None = None,
    itogo_after: str | None = None,
    itogo_values: tuple[str, str, int, int] | None = None,
) -> str:
    lines = [
        f"pageId: {page_id}",
        f"title: {title}",
        f"URL: {page_url(page_id)}",
        f"операция: {operation}",
    ]
    if child_title:
        lines.append(f"дочка title: {child_title}")
    if gantt:
        root = gantt["eventsData"][0]
        if itogo_values:
            d1, d2, n, m = itogo_values
        else:
            d1, d2, n, m = compute_itogo_from_gantt(gantt)
        lines.append(f"задач: {count_tasks(root)}")
        lines.append(f"корень: {str(root.get('startDate', ''))[:10]} — {str(root.get('endDate', ''))[:10]}")
        lines.append(f"Итого: {d1} — {d2}, {n} р.д., {m} ч-ч")
    if empty_plan:
        lines.append("⚠ план пустой (шаблон без задач)")
    if had_existing_plan:
        lines.append("⚠ план будет заменён целиком; правки не из этого MPP сгорят")
    if itogo_before and itogo_after:
        lines.append(f"Итого было:\n{itogo_before}")
        lines.append(f"Итого станет:\n{itogo_after}")
    for w in warnings or []:
        lines.append(f"⚠ {w}")
    lines.append("")
    lines.append('Подтверди «лей» / «пиши» / «да» для записи.')
    return "\n".join(lines)


def representation_diagnostics(prepared, representation, *, model=None, observation=None):
    """Four independent value layers. A model is never a plugin observation."""
    from copy import deepcopy
    from itogo import field_value
    prepared.validate()
    data=prepared.normalized_data
    flat={}
    def walk(nodes):
        for node in nodes:
            flat[node['id']]=node
            walk(node.get('children',[]))
    walk(representation['gantt'].get('eventsData',[]))
    rows=[]
    model=model or {}
    observation=observation or {}
    for task in data['tasks']:
        if 'error' in task or task.get('id')==0:
            continue
        key=task['task_key']
        node=flat.get(representation['mappings']['tasks'].get(key),{})
        rows.append({'entity':key,'source':{'start':field_value(task.get('start')),'finish':field_value(task.get('finish')),'duration':deepcopy(task.get('duration'))},
                     'represented':{'start':node.get('startDate'),'finish':node.get('endDate'),'duration':node.get('duration'),'duration_unit':node.get('durationUnit')},
                     'model':deepcopy(model.get('tasks',{}).get(key)),
                     'observed':deepcopy(observation.get('tasks',{}).get(key))})
    groups = {}
    for source_group, plugin_group, key_field in [
        ('dependencies','dependenciesData','dependency_key'),('resources','resourcesData','resource_key'),
        ('assignments','assignmentsData','assignment_key'),('calendars','calendarsData','calendar_key')]:
        represented={row['id']:row for row in representation['gantt'][plugin_group]}
        groups[source_group]=[{'entity':row.get(key_field),'source':deepcopy(row),
            'represented':deepcopy(represented.get(representation['mappings'][source_group].get(row.get(key_field)))),
            'model':deepcopy(model.get(source_group,{}).get(row.get(key_field))),
            'observed':deepcopy(observation.get(source_group,{}).get(row.get(key_field)))} for row in data[source_group]]
    return {**groups,'source':{'normalized_sha256':prepared.semantic_hash},'tasks':rows,
            'losses':deepcopy(representation['diagnostics']), 'summary':deepcopy(representation['summary']),
            'model_status':model.get('status','not_verified'),'model_evidence':model.get('evidence'),
            'observed_status':observation.get('status','not_observed'),'observed_evidence':observation.get('evidence'),
            'schedule':'not_verified'}


def format_representation_diagnostics(diagnostics):
    from itogo import format_work_hours
    lines=['Исходные / представленные / модельные / наблюдаемые значения:']
    for task in diagnostics['tasks']:
        lines.append(f"{task['entity']}: MPP={task['source']}; представление={task['represented']}; модель={task['model']}; плагин={task['observed']}")
    work=diagnostics['summary']['work']
    lines.append(f"Работа: {format_work_hours(work['hours']) if work['hours'] is not None else 'неизвестна'} ч-ч; качество={work['quality']}")
    lines.append(f"Модель: {diagnostics['model_status']}; наблюдение: {diagnostics['observed_status']}; расписание: {diagnostics['schedule']}")
    lines.extend('⚠ '+loss['code']+': '+str(loss.get('entity')) for loss in diagnostics['losses'])
    return '\n'.join(lines)
