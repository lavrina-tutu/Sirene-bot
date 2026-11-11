"""MPP CSV → gantt-chart-planner JSON (no idCounter=300000)."""
from __future__ import annotations

import ast
import csv
import json
from copy import deepcopy
from pathlib import Path
from typing import Any

SKILL_ROOT = Path(__file__).resolve().parents[1]
EMPTY_TEMPLATE = SKILL_ROOT / "references" / "empty-gantt-template.json"


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    with open(path, encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def _parse_duration_days(raw: str, milestone: str) -> float:
    if milestone == "True":
        return 0.0
    val = raw.replace(" d", "").strip()
    if not val:
        return 0.0
    return float(val)


def _normalize_dt(raw: str | None) -> str | None:
    if not raw:
        return None
    s = raw.replace("T09:00", "T09:00:00").replace("T18:00", "T18:00:00")
    if "T" in s and s.count(":") == 1:
        s = s + ":00"
    return s


def _base_event(leaf_template: dict[str, Any]) -> dict[str, Any]:
    return {
        "baselines": [],
        "calendar": leaf_template.get("calendar"),
        "constraintType": leaf_template.get("constraintType", ""),
        "durationUnit": "day",
        "effort": None,
        "effortDriven": leaf_template.get("effortDriven", False),
        "effortUnit": "hour",
        "ignoreResourceCalendar": leaf_template.get("ignoreResourceCalendar"),
        "inactive": leaf_template.get("inactive"),
        "manuallyScheduled": False,
        "percentDone": 0,
        "segments": None,
        "schedulingMode": "FixedDuration",
        "unscheduled": False,
    }


def _leaf_template(tmpl: dict[str, Any]) -> dict[str, Any]:
    root = tmpl["eventsData"][0]
    if root.get("children"):
        return root["children"][0]
    return root


def _parse_outline_level(raw: str | None) -> int:
    """Пустое / мусор / нечисло → 0. '1.0' → 1. Не бросать ValueError."""
    s = str(raw).strip() if raw is not None else ""
    if not s:
        return 0
    try:
        return int(float(s))
    except (ValueError, TypeError):
        return 0


def build_event_tree(tasks: list[dict[str, str]], leaf_template: dict[str, Any]) -> tuple[dict[str, Any], list[dict[str, str]]]:
    rows = [
        r for r in tasks
        if r.get("id") and r["id"] != "0" and _parse_outline_level(r.get("outline_level")) > 0
    ]
    root: dict[str, Any] | None = None
    stack: list[tuple[int, dict[str, Any]]] = []
    for r in rows:
        lvl = _parse_outline_level(r.get("outline_level"))
        node = _base_event(leaf_template)
        node["name"] = r["name"]
        node["duration"] = _parse_duration_days(r.get("duration", ""), r.get("milestone", "False"))
        node["startDate"] = _normalize_dt(r.get("start"))
        node["endDate"] = _normalize_dt(r.get("finish"))
        node["rollup"] = r.get("summary") == "True"
        node["id"] = int(r["id"])
        node["children"] = []
        if r.get("percent_complete"):
            try:
                node["percentDone"] = int(float(r["percent_complete"]))
            except ValueError:
                node["percentDone"] = 0
        while stack and stack[-1][0] >= lvl:
            stack.pop()
        if stack:
            stack[-1][1]["children"].append(node)
        else:
            root = node
        stack.append((lvl, node))
    if root is None:
        raise ValueError("No root task (outline_level=1) in MPP CSV")
    return root, rows


def fill_parent_fields(node: dict[str, Any], parent_id: int | None = None, parent_index: int = 0) -> None:
    node["parentId"] = parent_id
    node["parentIndex"] = parent_index
    for i, child in enumerate(node.get("children", [])):
        fill_parent_fields(child, node["id"], i)


def flatten_events(root: dict[str, Any]) -> dict[int, dict[str, Any]]:
    out: dict[int, dict[str, Any]] = {}

    def walk(n: dict[str, Any]) -> None:
        out[n["id"]] = n
        for c in n.get("children", []):
            walk(c)

    walk(root)
    return out


def active_resources(resources_data: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_name: dict[str, dict[str, Any]] = {}
    for r in resources_data:
        nm = r["name"]
        if nm not in by_name or by_name[nm]["id"] < r["id"]:
            by_name[nm] = r
    return sorted(by_name.values(), key=lambda x: x["id"])


def build_resources(
    mpp_resources: list[dict[str, str]],
    existing_resources: list[dict[str, Any]] | None,
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    plugin_res = active_resources(existing_resources or [])
    name_to_id = {r["name"]: r["id"] for r in plugin_res}
    used_ids = {r["id"] for r in plugin_res}
    next_id = (max(used_ids) if used_ids else 0) + 1
    for r in mpp_resources:
        if not r.get("id") or r["id"] == "0":
            continue
        nm = r["name"]
        if nm and nm not in name_to_id:
            plugin_res.append(
                {
                    "id": next_id,
                    "parentId": None,
                    "name": nm,
                    "eventColor": "red",
                    "resourceType": "custom",
                }
            )
            name_to_id[nm] = next_id
            next_id += 1
    plugin_res.sort(key=lambda x: x["id"])
    return plugin_res, name_to_id


def build_dependencies(rows, flat, start_id, drop_links=None):
    deps: list[dict[str, Any]] = []
    warnings: list[str] = []
    dep_id = start_id
    dropped = set(drop_links or ())
    for r in rows:
        preds_raw = r.get("predecessors") or ""
        if not preds_raw or preds_raw == "[]":
            continue
        try:
            pids = ast.literal_eval(preds_raw)
        except (SyntaxError, ValueError):
            pids = []
        tid = int(r["id"])
        for p in pids:
            p = int(p)
            if (p, tid) in dropped:
                continue
            if p in flat and tid in flat and tid != p:
                deps.append(
                    {
                        "id": dep_id,
                        "from": p,
                        "to": tid,
                        "type": 2,
                        "lag": 0,
                        "lagUnit": "day",
                        "active": True,
                    }
                )
                dep_id += 1
    return deps, warnings


def critical_path_days(gantt: dict[str, Any]) -> float:
    """Срок проекта, как его пересчитает плагин: сумма длительностей
    по самой длинной цепочке зависимостей (FS, type==2). Плагин игнорирует
    готовые start/end в JSON и считает критический путь сам."""
    def walk(nodes):
        for n in nodes:
            yield n
            if n.get("children"):
                yield from walk(n["children"])

    nodes = {n["id"]: n for n in walk(gantt.get("eventsData", []))}
    if not nodes:
        return 0.0
    pred: dict[int, list[int]] = {nid: [] for nid in nodes}
    for d in gantt.get("dependenciesData", []):
        if d.get("active", True) is False:
            continue
        pred[d["to"]].append(d["from"])
    dur = {nid: (n.get("duration") or 0.0) for nid, n in nodes.items()}
    fin: dict[int, float] = {}

    def longest(nid: int) -> float:
        if nid in fin:
            return fin[nid]
        best = max((longest(p) for p in pred[nid]), default=0.0)
        fin[nid] = best + dur[nid]
        return fin[nid]

    return max(longest(nid) for nid in nodes)


def build_assignments(
    assignments: list[dict[str, str]],
    flat: dict[int, dict[str, Any]],
    name_to_id: dict[str, int],
    start_id: int,
) -> tuple[list[dict[str, Any]], dict[int, float]]:
    asn_out: list[dict[str, Any]] = []
    eff_acc: dict[int, float] = {}
    asn_id = start_id
    for a in assignments:
        if not a.get("resource_id") and not a.get("resource_name"):
            continue
        eid = int(a["task_id"])
        if eid not in flat:
            continue
        rnm = a.get("resource_name", "")
        pid = name_to_id.get(rnm)
        if pid is None:
            continue
        units = float(a.get("units") or 100)
        asn_out.append({"id": asn_id, "event": eid, "resource": pid, "units": units})
        asn_id += 1
        work_raw = (a.get("work") or "0").replace(" h", "").strip()
        try:
            work = float(work_raw)
        except ValueError:
            work = 0.0
        eff_acc[eid] = eff_acc.get(eid, 0.0) + work
    for eid, hrs in eff_acc.items():
        if eid in flat:
            flat[eid]["effort"] = round(hrs, 3)
    return asn_out, eff_acc


def compute_id_counter(data: dict[str, Any]) -> int:
    ids: list[int] = []

    def walk_event(n: dict[str, Any]) -> None:
        ids.append(int(n["id"]))
        for c in n.get("children", []):
            walk_event(c)

    for e in data.get("eventsData", []):
        walk_event(e)
    for r in data.get("resourcesData", []):
        ids.append(int(r["id"]))
    for d in data.get("dependenciesData", []):
        ids.append(int(d["id"]))
    for a in data.get("assignmentsData", []):
        ids.append(int(a["id"]))
    return max(ids) + 1 if ids else 1


def preserve_meta_keys(tmpl: dict[str, Any], out: dict[str, Any]) -> None:
    for key in (
        "macroConfig",
        "initialState",
        "baselineVersions",
        "customColumns",
        "linkedSites",
    ):
        if key in tmpl:
            out[key] = deepcopy(tmpl[key])


def convert_mpp_csv(
    tasks_csv: Path,
    resources_csv: Path,
    assignments_csv: Path,
    *,
    template_json: dict[str, Any] | None = None,
    calendars_data: list[dict[str, Any]] | None = None,
    drop_links: list[tuple[int, int]] | None = None,
) -> dict[str, Any]:
    tmpl = template_json or json.loads(EMPTY_TEMPLATE.read_text(encoding="utf-8"))
    leaf = _leaf_template(tmpl)
    tasks = read_csv_rows(tasks_csv)
    mpp_res = read_csv_rows(resources_csv)
    asns = read_csv_rows(assignments_csv)

    root, rows = build_event_tree(tasks, leaf)
    fill_parent_fields(root)

    flat = flatten_events(root)
    plugin_res, name_to_id = build_resources(mpp_res, tmpl.get("resourcesData"))
    max_used = max(
        [int(r["id"]) for r in rows]
        + [r["id"] for r in plugin_res]
        + ([int(x) for x in flat] if flat else [0]),
        default=0,
    )
    deps, _warn = build_dependencies(rows, flat, max_used + 1, drop_links=drop_links)
    max_used = max(max_used, max((d["id"] for d in deps), default=0))
    asn_out, _ = build_assignments(asns, flat, name_to_id, max_used + 1)

    out = deepcopy(tmpl)
    preserve_meta_keys(tmpl, out)
    out["eventsData"] = [root]
    out["resourcesData"] = plugin_res
    out["dependenciesData"] = deps
    out["assignmentsData"] = asn_out
    if root.get("startDate"):
        out["startDate"] = str(root["startDate"])[:10]
    if calendars_data is not None:
        out["calendarsData"] = calendars_data
    out["idCounter"] = compute_id_counter(out)
    return out


def empty_gantt(title: str | None = None, template_path: Path | None = None) -> dict[str, Any]:
    path = template_path or EMPTY_TEMPLATE
    out = json.loads(path.read_text(encoding="utf-8"))
    if title:
        out["eventsData"][0]["name"] = title
    out["dependenciesData"] = []
    out["assignmentsData"] = []
    out["eventsData"][0]["children"] = []
    out["idCounter"] = compute_id_counter(out)
    return out


def copy_parent_gantt(parent: dict[str, Any]) -> dict[str, Any]:
    out = deepcopy(parent)
    out["idCounter"] = compute_id_counter(out)
    return out


def count_tasks(root: dict[str, Any]) -> int:
    n = 0

    def walk(node: dict[str, Any]) -> None:
        nonlocal n
        n += 1
        for c in node.get("children", []):
            walk(c)

    walk(root)
    return n
