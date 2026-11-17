#!/usr/bin/env python3
"""Консенсус нескольких прогонов матрицы (воспроизводимость / тройная итерация).

LLM вероятностен: один и тот же процесс на разных прогонах может дать слегка
разные матрицы (особенно формулировки клеток и тип AI в спорных клетках).
Этот скрипт берёт N независимых прогонов одного процесса (run1.json, run2.json,
run3.json), строит ОДНУ консенсусную матрицу мажоритарным голосованием по типу
AI в каждой клетке, считает метрики воспроизводимости (stability score) и пишет
divergence-отчёт по клеткам, где прогоны разошлись.

Зависимости: только стандартная библиотека.

Usage:
    python consensus_matrix.py --inputs run1.json run2.json run3.json \
        --output consensus.spec.json --report divergence.md
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

CAT_LABEL = {
    "assist": "Ассистентский AI",
    "agent": "Агентный AI",
    "human_collab": "Сотрудничество с человеком",
    "no": "Нет / не применимо",
    "unknown": "Не классифицировано",
}


def classify(cell: str | None) -> str:
    if not cell:
        return "no"
    c = cell.strip().lower()
    if c in {"нет", "—", "-", ""}:
        return "no"
    if "ассистентский" in c:
        return "assist"
    if "агентный" in c:
        return "agent"
    if "сотрудничеств" in c:
        return "human_collab"
    return "unknown"


def load(paths: list[str]) -> list[dict]:
    return [json.loads(Path(p).read_text(encoding="utf-8")) for p in paths]


def canonical_axes(specs: list[dict]):
    """Оси первого прогона = эталон. Расхождения по осям фиксируем как issues."""
    base = specs[0]
    stages = [s["name"] for s in base["stages"]]
    activities = list(base["activities"])
    issues: list[str] = []
    for i, sp in enumerate(specs[1:], start=2):
        st = [s["name"] for s in sp["stages"]]
        ac = list(sp["activities"])
        if st != stages:
            issues.append(
                f"Прогон {i}: набор/порядок стадий отличается от прогона 1 "
                f"(прогон1={len(stages)} стадий, прогон{i}={len(st)})."
            )
        if set(ac) != set(activities):
            only1 = set(activities) - set(ac)
            onlyn = set(ac) - set(activities)
            issues.append(
                f"Прогон {i}: набор активностей отличается. "
                f"Только в прогоне 1: {sorted(only1) or '—'}; "
                f"только в прогоне {i}: {sorted(onlyn) or '—'}."
            )
    return stages, activities, issues


def majority(items: list[str]):
    cnt = Counter(items)
    top, n = cnt.most_common(1)[0]
    return top, n, cnt


def build_consensus_matrix(specs: list[dict], kind: str, stages, activities):
    consensus: dict[str, dict[str, str]] = {}
    records = []
    for act in activities:
        consensus[act] = {}
        for stage in stages:
            texts = [sp.get(kind, {}).get(act, {}).get(stage, "Нет") for sp in specs]
            cats = [classify(t) for t in texts]
            top_cat, n, cnt = majority(cats)
            cand = [t for t, c in zip(texts, cats) if c == top_cat]
            rep = max(cand, key=lambda s: len(s or "")) if cand else "Нет"
            consensus[act][stage] = rep
            records.append(
                {
                    "activity": act,
                    "stage": stage,
                    "consensus_cat": top_cat,
                    "agreement": n / len(specs),
                    "counts": dict(cnt),
                    "texts": texts,
                }
            )
    return consensus, records


def consensus_stages(specs: list[dict], stages_order):
    n = len(specs)
    thresh = (n // 2) + 1
    base_stages = {s["name"]: s for s in specs[0]["stages"]}
    out = []
    for name in stages_order:
        votes = sum(
            1
            for sp in specs
            if any(s["name"] == name and s.get("critical") for s in sp["stages"])
        )
        base = dict(base_stages.get(name, {"name": name}))
        base["critical"] = votes >= thresh
        base["critical_votes"] = f"{votes}/{n}"
        out.append(base)
    return out


def consensus_stage_summary(specs: list[dict], stages_order):
    out = []
    for name in stages_order:
        resp = []
        comments = []
        for sp in specs:
            for item in sp.get("stage_summary", []) or []:
                if item.get("stage") == name:
                    resp.append((item.get("responsible") or "").strip())
                    if item.get("comment"):
                        comments.append(item["comment"])
        if not resp:
            continue
        top, _, _ = majority([r for r in resp if r])
        out.append(
            {
                "stage": name,
                "responsible": top,
                "comment": max(comments, key=len) if comments else "",
            }
        )
    return out


def consensus_human_only(specs: list[dict]):
    n = len(specs)
    thresh = (n // 2) + 1
    by_stage: dict[str, list[dict]] = {}
    for sp in specs:
        for item in sp.get("human_only", []) or []:
            stage = item.get("stage") or item.get("where", "")
            by_stage.setdefault(stage, []).append(item)
    out = []
    for stage, items in by_stage.items():
        if len(items) < thresh:
            continue
        whats = [it.get("what") or it.get("decision", "") for it in items]
        whys = [it.get("why", "") for it in items]
        out.append(
            {
                "stage": stage,
                "what": max(whats, key=len) if whats else "",
                "why": max(whys, key=len) if whys else "",
            }
        )
    return out


def stability(records) -> float:
    if not records:
        return 1.0
    unanimous = sum(1 for r in records if r["agreement"] >= 0.999)
    return round(unanimous / len(records), 3)


def write_report(path, process, n, axis_issues, as_rec, to_rec, stab_as, stab_to):
    lines = []
    lines.append(f"# Отчёт воспроизводимости — {process}")
    lines.append("")
    lines.append(f"- Прогонов: **{n}**")
    lines.append(f"- Метод консенсуса: мажоритарное голосование по типу AI в каждой клетке.")
    lines.append(f"- Стабильность AS IS (доля единогласных клеток): **{stab_as}**")
    lines.append(f"- Стабильность TO BE (доля единогласных клеток): **{stab_to}**")
    lines.append("")
    if axis_issues:
        lines.append("## Расхождения по осям (стадии / активности)")
        lines.append("")
        for it in axis_issues:
            lines.append(f"- ⚠️ {it}")
        lines.append("")
    else:
        lines.append("## Оси (стадии / активности)")
        lines.append("")
        lines.append("- ✅ Все прогоны согласованы по осям.")
        lines.append("")

    def split_table(title, records):
        rows = [r for r in records if r["agreement"] < 0.999]
        lines.append(f"## {title}: спорные клетки ({len(rows)} из {len(records)})")
        lines.append("")
        if not rows:
            lines.append("- ✅ Все клетки единогласны.")
            lines.append("")
            return
        lines.append("| Активность | Стадия | Консенсус | Согласие | Голоса |")
        lines.append("|---|---|---|---|---|")
        for r in sorted(rows, key=lambda x: x["agreement"]):
            votes = ", ".join(
                f"{CAT_LABEL.get(k, k)}×{v}" for k, v in r["counts"].items()
            )
            lines.append(
                f"| {r['activity']} | {r['stage']} | "
                f"{CAT_LABEL.get(r['consensus_cat'], r['consensus_cat'])} | "
                f"{int(r['agreement'] * 100)}% | {votes} |"
            )
        lines.append("")

    split_table("AS IS", as_rec)
    split_table("TO BE", to_rec)
    Path(path).write_text("\n".join(lines), encoding="utf-8")
    print(f"[report] wrote {path}")


def main() -> None:
    p = argparse.ArgumentParser(description="Консенсус N прогонов матрицы (воспроизводимость)")
    p.add_argument("--inputs", nargs="+", required=True, help="2+ spec.json одного процесса")
    p.add_argument("--output", required=True, help="Выходной консенсусный spec.json")
    p.add_argument("--report", help="Markdown-отчёт по расхождениям (опционально)")
    args = p.parse_args()

    if len(args.inputs) < 2:
        raise SystemExit("Нужно минимум 2 прогона для консенсуса.")

    specs = load(args.inputs)
    n = len(specs)
    stages_order, activities, axis_issues = canonical_axes(specs)

    as_is, as_rec = build_consensus_matrix(specs, "as_is", stages_order, activities)
    to_be, to_rec = build_consensus_matrix(specs, "to_be", stages_order, activities)
    stages = consensus_stages(specs, stages_order)
    stage_summary = consensus_stage_summary(specs, stages_order)
    human_only = consensus_human_only(specs)

    stab_as = stability(as_rec)
    stab_to = stability(to_rec)

    base = specs[0]
    process = base.get("process_name", "matrix")
    consensus_spec = {
        "process_name": process,
        "owner": base.get("owner", ""),
        "purpose": base.get("purpose", ""),
        "frequency": base.get("frequency", ""),
        "kpi": base.get("kpi", ""),
        "date": base.get("date", ""),
        "version": (base.get("version", "v1") + "-consensus"),
        "status": base.get("status")
        or (
            "Рекомендация — итоговые назначения «человек / AI-агент / AI + ревью» "
            "требуют обсуждения с владельцем процесса и стейкхолдерами перед запуском работ."
        ),
        "reproducibility": {
            "runs": n,
            "method": "majority-vote по типу AI в каждой клетке",
            "stability_as_is": stab_as,
            "stability_to_be": stab_to,
        },
        "stages": stages,
        "activities": activities,
        "as_is": as_is,
        "to_be": to_be,
        "stage_summary": stage_summary,
        "human_only": human_only,
    }

    Path(args.output).write_text(
        json.dumps(consensus_spec, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"[consensus] wrote {args.output}")
    print(f"[consensus] прогонов={n}  стабильность AS IS={stab_as}  TO BE={stab_to}")
    if axis_issues:
        print(f"[consensus] ⚠️ расхождения по осям: {len(axis_issues)} (см. отчёт)")

    if args.report:
        write_report(args.report, process, n, axis_issues, as_rec, to_rec, stab_as, stab_to)


if __name__ == "__main__":
    main()
