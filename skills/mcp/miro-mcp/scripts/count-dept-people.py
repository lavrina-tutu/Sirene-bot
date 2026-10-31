#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Подсчёт уникальных людей по каждому отделу Miro-оргструктуры через коннекторное дерево.

Использование (patterns из сессии 15.09.2026, доска uXjVMfOqP7M=):
- Сохранить полные SVG квадрантов фрейма (canvas_read_as_svg по scope) в файлы.
- element id в SVG имеют вид id="m<число>" (m-префикс); коннекторы: data-start="m..." data-end="m...".
- Файлы, которые я вручную пересобрал без m-префикса в line (id="l1"), НЕ сматчатся — их коннекторы надо либо восстановить, либо обрабатывать вручную.
КЛЮЧЕВЫЕ ПРАВИЛА (подчеркнуто сессией):
- ВАЖНО: элемент с data-content=None (пустая роль/узел) в items НЕ попадает — обход не должен на нём обрываться.
- sticky (data-type="sticky") = терминальный человек. Всё прочее (роли, группы, пустые узлы) = транзитно, спускаться.
- Отсекать «Вакансия», «+N», «-N».
- Дедуп имён (см. count-and-dedup-people.md).
- ПРОВЕРКА ПРАВДОПОДОБИЯ: если число отдела абсурдно велико (≈ департамент или много больше соседних) — отдел имеет перекрёстные коннекторы, числу НЕ верить, сверять с пользователем.
"""
import json, re
from collections import defaultdict

def parse_file(path):
    raw = open(path, encoding="utf-8").read()
    try:
        d = json.loads(raw); obj = json.loads(d["result"]) if isinstance(d, dict) and "result" in d else d
        svg = obj.get("svg", "")
    except Exception:
        svg = raw
    items = {}
    for m in re.finditer(r'<(rect|textArea)\s+id="(m)?(\d+)"([^>]*?)(?:/>|>)', svg):
        pref, gid, attrs = m.group(2), m.group(3), m.group(4)
        def ga(n):
            mm = re.search(n + r'="(.*?)"', attrs); return mm.group(1) if mm else None
        content = ga("data-content")
        key = (pref or '') + gid
        if content is not None:
            c = content.replace('&lt;','<').replace('&gt;','>'); c = re.sub(r'<[^>]+>', ' ', c).strip()
            items[key] = {"text": c, "type": ga("data-type") or "shape"}
    conns = set()
    for m in re.finditer(r'<line[^>]*?data-start="(m?\d+)"[^>]*?data-end="(m?\d+)"[^>]*?/?>', svg):
        conns.add((m.group(1), m.group(2)))
    return items, conns

def main(svg_files, dept_map):
    all_items, all_conns = {}, set()
    for path in svg_files:
        it, cn = parse_file(path)
        all_items.update(it); all_conns.update(cn)
    adj = defaultdict(list)
    for s, e in all_conns:
        if s.startswith('m') and e.startswith('m'):
            adj[s].append(e)
    def collect(root):
        people=set(); seen=set(); stack=[root]
        while stack:
            n=stack.pop()
            if n in seen: continue
            seen.add(n)
            it=all_items.get(n)
            if it is not None and it["type"]=="sticky":
                people.add(n); continue
            for x in adj.get(n,[]): stack.append(x)
        return people
    for did, label in dept_map.items():
        p = collect(did)
        names = sorted(set(all_items[x]['text'] for x in p
                          if not re.match(r'^(вакансия|[+-]\d+)$', all_items[x]['text'].strip().lower())))
        print(f"\n{did} {label}\n  ({len(names)}): {names}")

if __name__ == "__main__":
    FILES = ["/tmp/q1.svg", "/tmp/q2_full.svg", "/tmp/q3_full.svg"]
    DEPTS = {
        "m3458764683673438549": "Отдел аналитики клиентского сервиса",
        "m3458764683673438551": "DataKIT",
        "m3458764683673438542": "Отдел маркетинговой и HR (предп.7)",
        "m3458764683673438547": "Отдел клиентской аналитики (6+3)",
        "m3458764683673438851": "Отдел машинного обучения (8) — вероятен перекрёст",
        "m3458764683673438642": "Группа BI-аналитики (1)",
    }
    main(FILES, DEPTS)