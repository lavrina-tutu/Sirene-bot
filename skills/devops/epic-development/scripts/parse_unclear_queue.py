#!/usr/bin/env python3
"""
Парсинг unclear_queue.md и построение реестра для брифа.
Использование:
    python parse_unclear_queue.py <path_to_unclear_queue.md> [output.md]

По умолчанию выводит сводку в stdout; при указании output.md — пишет полный реестр.
"""
import re, sys
from pathlib import Path


def parse_entries(content: str) -> list[dict]:
    entries = []
    current = {}
    for line in content.split('\n'):
        if line.startswith('- ****'):
            if current:
                entries.append(current)
            title_match = re.search(r'Саммари: (.+)|Action items: (.+)', line)
            t = ''
            if title_match:
                t = (title_match.group(1) or title_match.group(2)).strip()
            else:
                t = line.replace('- ****', '').replace('—', '').strip()
            etype = 'summary' if 'Саммари' in line else ('actions' if 'Action items' in line else 'other')
            current = {'title': t, 'type': etype}
        elif 'file:' in line:
            fm = re.search(r'`(.+)`', line)
            if fm:
                current['file'] = fm.group(1)
        elif 'reason:' in line:
            current['reason'] = line.strip()
    if current:
        entries.append(current)
    return entries


def get_date(e: dict) -> str:
    m = re.match(r'^(\d{4}-\d{2}-\d{2})', e.get('file', ''))
    return m.group(1) if m else '—'


def classify(e: dict) -> tuple[str, str]:
    """Возвращает (категория, hint/slug/login)."""
    t = e.get('title', '').lower()
    f = e.get('file', '').lower()

    # Служебные
    if f in ['_log_meet.md', '_registry_meet.md']:
        return ('skip', 'служебный файл реестра')

    # Daily стендапы
    if re.search(r'daily.*кирилл|daily.*саша.*кирилл|кирилл.*daily|daily fr кирилл', t):
        return ('skip', 'daily-стендап')
    if t == 'daily':
        return ('skip', 'daily без имени')

    # 1on1 с известными
    if re.search(r'кирилл.*1-1|1-1.*кирилл|кирилл 1-1|кирилл передача|1-1 середа|середа.*1-1', t):
        return ('1on1', 'ksereda')
    if re.search(r'илья 1-1|1-1.*илья|статус по вопросам саша т.*илья', t):
        return ('1on1', '??? Илья')
    if 'олег 1-1' in t:
        return ('1on1', '??? Олег')
    if 'даяна' in t:
        return ('1on1', '??? Даяна')
    if re.search(r'саша а 1-1|саша а:.*okr|custom agent.*aralov', t):
        return ('1on1', 'aralov')
    if re.search(r'саша саша 1-1|1-1 саша саша|1-1 ткаченко', t):
        return ('1on1', 'tkachenkoav + ???')
    if re.search(r'pr ткаченко|sr.*ткаченко|zoom meeting ткаченко|ипр криворотова|okr с ерошкина', t):
        return ('1on1', 'tkachenkoav')

    # Проекты — расширяемый список, добавлять по мере появления новых slug
    if re.search(r'ml.платформ|mlops|neoflex|внедрение.*платф|feast|kolnogorov|kolmogorov|выбор вендора', t):
        return ('project', 'ml-platforma')
    if re.search(r'парсинг|парсер|аутсорс парсинг|мониторинг.*конкурент|доработки.*мониторинга цен', t):
        return ('project', 'parsery')
    if 'метротека' in t or 'kpi-навигатор' in t or re.search(r'реестр отчет|дашборд с процметрик|валидация реестра отчет', t):
        return ('project', 'metroteka')
    if re.search(r'ai.ready|ai-ready трансформ', t):
        return ('project', 'ai-transformaciya')
    if re.search(r'ai.mas|ai.мультиагент|ai.зации стримов|управление проектами и рисками', t):
        return ('project', 'ai-transformaciya')
    if re.search(r'ai.*трансформ|трансформ.*ai|про ии.зацию|ai.зация деятельн|вм для ai.*аналитик', t):
        return ('project', 'ai-transformaciya')
    if re.search(r'trisigma|tisigma', t):
        return ('project', 'trisigma')
    if re.search(r'цу.?туту|цу\.|центральн.*университет|подключение студент|vpn access|ssh key|оптимизация доступа', t):
        return ('project', 'cu')
    if re.search(r'чат.бот|rag.*confluence|бот.*ии|бот.*покровский|бриф.*инициация чата', t):
        return ('project', '??? чат-бот (нет slug)')
    if re.search(r'антибот', t):
        return ('project', 'antibot')
    if re.search(r'альфа', t):
        return ('project', '??? Альфа (нет slug)')
    if re.search(r'улучшение.*аб|стендап аб|статус.*аб|развитие аб.платформ|аб тесты|атрибуц', t):
        return ('project', '??? АБ-платформа (нет slug)')
    if re.search(r'про bi|bi.направлени|ds.as.a.service|сегментирование офферов', t):
        return ('project', '??? BI/DS (нет slug)')

    # Skip-кандидаты
    if re.search(r'планирование q|планы q|план q|смотрим q|собираем q|квартальный обзор|проверяем okr|заполняем jira', t):
        return ('skip', 'квартальное планирование АИД')
    if re.search(r'аид 2026|аид.2026|выравнивание по целям аид|смотрим цели аид|смотрим приоритеты.*аид', t):
        return ('skip', 'планирование команды АИД')
    if re.search(r'fireflies demo|тренинг ии|лекция по ии|2025-\d{2}-\d{2}.*mp4|gantt|новые правила.*sr', t):
        return ('skip', 'не релевантно')
    if re.search(r'untitled|jun \d+|apr \d+|зал персональн|тестирую бота для митинг', t):
        return ('skip', 'безымянная встреча')
    if re.search(r'discovery.*delivery|дискавери.?деливери|d.d будущего|devrel|подкаст|dattalk|цифровой управленец', t):
        return ('skip', 'внешний митап / общее')
    if re.search(r'ai.?агент.*агрегац', t):
        return ('skip', 'наш инструмент AggregateFrom')

    return ('unclear', '???')


def build_registry_md(entries: list[dict], source_path: str = '') -> str:
    groups: dict[tuple, list] = {}
    for e in entries:
        cat, hint = classify(e)
        # дедуплицируем -actions.md если есть -summary.md
        groups.setdefault((cat, hint), []).append(e)

    total = {c: 0 for c in ['1on1', 'project', 'skip', 'unclear']}
    for (cat, _), v in groups.items():
        total[cat] = total.get(cat, 0) + len(v)

    lines = [
        '---',
        'tool: AggregateFromMeetings',
        'type: pm-checklist',
        f'source: {source_path or "unclear_queue.md"}',
        '---',
        '',
        '# 📋 Реестр unclear-встреч',
        '',
        f'> **{sum(total.values())} записей** · 1-1: **{total["1on1"]}** · проекты: **{total["project"]}** · skip: **{total["skip"]}** · требуют разбора: **{total["unclear"]}**',
        '',
        '---',
        '',
    ]

    n = 1

    # 1on1
    lines.append('## 👤 1-1 встречи')
    lines.append('')
    lines.append('| # | Дата | Название | Предлагаемый логин | ✅ Маршрут |')
    lines.append('|---|------|---------|-------------------|-----------|')
    seen = set()
    for (cat, hint), v in sorted(groups.items()):
        if cat != '1on1':
            continue
        for e in sorted(v, key=lambda x: x.get('file', '')):
            base = re.sub(r'\s*(ч\d+|часть\s*\d+)$', '', e['title'].lower().strip())
            if e.get('type') == 'actions' and base in seen:
                continue
            seen.add(base)
            lines.append(f'| {n} | {get_date(e)} | {e["title"]} | `{hint}` | |')
            n += 1
    lines.append('')

    # Проекты
    lines.append('## 📁 Встречи по проектам')
    lines.append('')
    proj_groups: dict[str, list] = {}
    for (cat, hint), v in groups.items():
        if cat != 'project':
            continue
        proj_groups.setdefault(hint, []).extend(v)

    for slug in sorted(proj_groups.keys()):
        v = proj_groups[slug]
        lines.append(f'### `{slug}` ({len(v)} встреч)')
        lines.append('')
        lines.append('| # | Дата | Название | ✅ Маршрут |')
        lines.append('|---|------|---------|-----------|')
        seen2 = set()
        for e in sorted(v, key=lambda x: x.get('file', '')):
            base = e['title'].lower().strip()
            if e.get('type') == 'actions' and base in seen2:
                continue
            seen2.add(base)
            lines.append(f'| {n} | {get_date(e)} | {e["title"]} | |')
            n += 1
        lines.append('')

    # Unclear
    lines.append('## ❓ Не распознаны — нужен вердикт PM')
    lines.append('')
    lines.append('| # | Дата | Название | ✅ Маршрут |')
    lines.append('|---|------|---------|-----------|')
    for (cat, hint), v in sorted(groups.items()):
        if cat != 'unclear':
            continue
        for e in v:
            lines.append(f'| {n} | {get_date(e)} | {e["title"]} | |')
            n += 1
    lines.append('')

    # Skip
    lines.append('## 🗑 Skip-кандидаты (уточнить)')
    lines.append('')
    lines.append('| # | Дата | Название | Причина | ✅ Маршрут |')
    lines.append('|---|------|---------|---------|-----------|')
    skip_groups: dict[str, list] = {}
    for (cat, hint), v in groups.items():
        if cat != 'skip':
            continue
        skip_groups.setdefault(hint, []).extend(v)
    for reason in sorted(skip_groups.keys()):
        v = skip_groups[reason]
        seen3 = set()
        for e in sorted(v, key=lambda x: x.get('file', '')):
            base = e['title'].lower().strip()
            if e.get('type') == 'actions' and base in seen3:
                continue
            seen3.add(base)
            lines.append(f'| {n} | {get_date(e)} | {e["title"]} | {reason} | |')
            n += 1
    lines.append('')

    lines.extend([
        '---',
        '',
        '## 📌 Команды TG',
        '',
        '| Команда | Действие |',
        '|---------|---------|',
        '| `unclear <file> → project <slug>` | Встреча → проект |',
        '| `unclear <file> → 1on1 <login>` | Встреча → 1-1 |',
        '| `unclear <file> → skip` | Пропустить |',
        '',
    ])

    return '\n'.join(lines)


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print(f'Usage: {sys.argv[0]} <unclear_queue.md> [output.md]')
        sys.exit(1)

    src = Path(sys.argv[1])
    content = src.read_text()
    entries = parse_entries(content)

    if len(sys.argv) >= 3:
        out = Path(sys.argv[2])
        result = build_registry_md(entries, str(src))
        out.write_text(result)
        print(f'Реестр записан в {out} ({len(entries)} записей)')
    else:
        # Краткая сводка
        groups: dict[tuple, list] = {}
        for e in entries:
            cat, hint = classify(e)
            groups.setdefault((cat, hint), []).append(e)
        total = {c: 0 for c in ['1on1', 'project', 'skip', 'unclear']}
        for (cat, _), v in groups.items():
            total[cat] = total.get(cat, 0) + len(v)
        print(f'Всего: {len(entries)} записей')
        print(f'  1on1:    {total["1on1"]}')
        print(f'  project: {total["project"]}')
        print(f'  skip:    {total["skip"]}')
        print(f'  unclear: {total["unclear"]}')
        print()
        if total['unclear']:
            print('Unclear (требуют вердикта PM):')
            for (cat, hint), v in sorted(groups.items()):
                if cat == 'unclear':
                    for e in v:
                        print(f'  - {e["title"]}')
