---
name: pfs-mff-troubleshooting
description: "Диагностика PFS/MFF: out_of_scope и Bullet points."
version: 1.0.0
author: agent
license: MIT
platforms: [linux]
metadata:
  hermes:
    tags: [PFS, MFF, Fireflies, out_of_scope, BulletPoints, route]
    related_skills: [protocolfromsummary]
---

# PFS + MFF Troubleshooting

Диагностика и исправление проблем когда встречи не публикуются в протоколы.

> **Полный текст всех питфоллов (дословно, без потери фактов) — в
> `references/pitfalls.md`.** Здесь — сжатые заголовки, суть, указатель.

## Диагностический алгоритм

### Шаг 1: Проверить формат summary-файла
```bash
grep -E "^## Bullet|^Участники:|^## Участники:" <путь к summary.md>
```
- `## Bullet points` + НЕТ `Участники:` → Custom AI Skill Fireflies не сработал (Питфолл A).
- Есть секции → к Шагу 2.

### Шаг 2: Проверить маршрутизацию
```bash
cd ~/USERTOOLS/ProtocolFromSummary && source .venv/bin/activate
python3 -c "
from protocolfromsummary.route import resolve_route
r = resolve_route('<название встречи>')
print(r.entity if r else 'None (out_of_scope)')
"
```
- `None` → баг маршрутизации (исправлен 11.08.2026, см. Питфолл B).
- `vstrechi_nerazobrannoe` → на страницу неразобранного (508804852).

### Шаг 3: Проверить ROUTES
```bash
python3 -c "
from protocolfromsummary.config import ROUTES
print(list(ROUTES.keys()))
"
```

## Питфоллы

### F. Зонтичные проекты (umbrella) + дубли `page_id` между РАЗНЫМИ slug — это НЕ баг (26.08.2026)
Несколько сущностей с одним `page_id`, разные `tag` — штатный паттерн. Два правила: зонтичный
проект (одна запись, широкие aliases, разделение нелегитимно) vs уникальность `(page_id, tag)`
(раздельные тех-сущности на одной странице, не ослабляется). `sr`/`adm` делят 519474318 — НЕ
сливать. Symptom: 8+ сущностей `pfs` без `tag` → `KeyError: 'tag'`; фикс `pfs.get("tag")`.
**Полный текст — см. references/pitfalls.md.**

### A. MFF Bullet points — Custom AI Skill не сработал
Summary содержит `## Bullet points`, нет `Участники:/Задачи:/Решения:`. MFF retry не работает
для встреч до настройки Custom Skill (кэш FF). Старые: пропустить / править вручную / пустая
строка. Перескачать (если скилл активен): `python -m movefromff --mode manual --meeting-id <id> --no-tg --verbose`.
Ключи `_registry_meet.json` — ULID, не дата-строка; рефетч асинхронен (pending_custom_skill).
**Полный текст — см. references/pitfalls.md.**

### B. Пустые участники → out_of_scope (исправлено 11.08.2026)
Было `route.py:171 return None`; стало `_route_from_entity("vstrechi_nerazobrannoe")`.
Тест `test_no_participants_no_name_match_goes_to_unsorted`. **Полный текст — см. references/pitfalls.md.**

### C. entity отсутствует в entities.json без pfs блока
Знакомое название ("ЦУ") без `pfs` → name_match не срабатывает → fallback. См. `protocolfromsummary`
Питфолл 11, 12. **Полный текст — см. references/pitfalls.md.**

### D. pfs_batch — агентный крон «молча» не публикует: пустой ответ вместо errors (17.08.2026)
`pfs_batch` — агентный LLM-крон; `(empty)` = LLM не выполнил команду (rate limit/сбой), тихий
успех. НЕ баг PFS-кода. Лечение: перевести в `no_agent` (bash-обёртка run-pending, как у
`pfs_notify`). **Полный текст — см. references/pitfalls.md.**

### E. Дедупликация падает с JSON-ошибками (18.08.2026)
`max_tokens=1024` при `reasoning:{effort:"high"}` → обрезанный/пустой JSON → `json.loads`
падает. Фикс: не задавать max_tokens + `timeout=DEDUP_LLM_TIMEOUT`; `dedup.py` —
`_parse_llm_json_array(raw)`. Диагностика: боевой промпт даёт `finish_reason: length`.
**Полный текст — см. references/pitfalls.md.**

### G. Дубль-строки синка АиД при публикации протокола (27.08.2026)
Нет date-de-dup: дедуп только по `meeting_id`, `insert_row_chronological` всегда создаёт новую
`<tr>` → дубль строки. Ожидаемое поведение (v1/v2/v3) на согласовании у Саши — фикс-код НЕ писать.
**Полный текст — см. references/pitfalls.md.**

## Link-n-Dedup: площадка 523032632 и promote (21.09.2026)
Проход 1 публикует параллельно: в минутки и на площадку 523032632 (4 колонки: дата+anchor |
контент | Цель-ссылка | Обработано-чекбокс). Проход 2 (`second_pass_all`) берёт строки с
`complete`+`promoted_at is None` и пишет их на страницу из «Цели». **Полный текст — см. references/pitfalls.md.**

### H. Гонка ручного `run-pending` с batch-кроном → 409 version conflict (21.09.2026)
Ручной прогон в час крона (~:10 будней) → `409` на общей странице; второй может УЖЕ записать.
Не доверяй `error: N`; перед прогоном `ps aux | grep run-pending`, после — сверка с реестром.
**Полный текст — см. references/pitfalls.md.**

### I. `run-pending` публикует только встречи, ОТСУТСТВУЮЩИЕ в реестре
Для перепрогона: удалить запись из `_registry.json` (бэкап) + удалить строку со страницы.
Реестр парсить через `data['entries']`, НЕ `data.values()`. **Полный текст — см. references/pitfalls.md.**

### J. «Цель» на площадке (ingest, v1.18.0) и резолв при promote (v1.15.0/v1.17.0)
Ingest: `hydrate_target_ref` строит `ac:link` (space+title, без content-id); 404 → пустая
ячейка, fail-soft. Promote-резолв: (а) content-id → (б) space+title → (в) title-only → (г)
invalid. Диагностика: `promote --meeting-id "<id>" --dry-run`. **Полный текст — см. references/pitfalls.md.**

### K. Встреча с нестандартным названием роутится в fallback, не на проект
«Страт. трек_ парсеры» не матчит alias «страт. трек: парсеры» → `vstrechi_nerazobrannoe`
(508804852). Жди fallback; Саша чинит сменой «Цели» на площадке. **Полный текст — см. references/pitfalls.md.**

### L. Пост-switch контур: флаг, границы дедупа, уведомления (v1.16.0/v1.17.0)
`PFS_POST_SWITCH` (env) включается только явной командой. Флаг on: проход 1 — только ingest на
площадку; дедуп ТОЛЬКО на проходе 2 (promote, 3 нед. target-страницы). Ingest-матчинг порог
0.80; ниже/конфликт → parking 508804852. **Полный текст — см. references/pitfalls.md.**

### M. Сброс встреч на перепрогон (post-switch): строки + реестр + верификационный крон
Удалить `<tr>` по `pfsrow-*` (клиент через `_make_confluence_client()`, модулей
`confluence`/`page_updater` НЕТ), сбросить `_registry.json`, разовый крон `export
PFS_POST_SWITCH=1 && run-pending`, сбросить first-pass снапшоты, `--dry-run` контроль,
`promote --meeting-id`. row_anchor детерминирован → дублей нет. **Полный текст — см. references/pitfalls.md.**

### N. Проверка физического размещения по якорю, не по реестру (24.09.2026)
`page_id` реестра — target-страница, не гарантия места строки (может лежать на площадке).
Факт — GET страницы и поиск `pfsrow-<anchor>` (Bearer из `ConfluenceSync/.env`). Пустой `td2`
+ полный summary = гонка (`delete+reingest`, не republish). Ручной уведомитель «съедает»
уведомление. **Полный текст — см. references/pitfalls.md.**

### O. Восстановление venv PFS после recreate + одноразовые кроны
После `rm -rf .venv`: `uv sync --extra dev`, проверить импорты `confluencesync`,
`entityregistrycli`, `mofs_index`, `bs4`. `uv.lock`/`.playground_backups` не коммитить.
Разовые PFS-кроны — с `--provider tutu`. **Полный текст — см. references/pitfalls.md.**

### P. Приёмочный тест конвейера (MFF→MOFS→PFS) на перепрогоне: cross-registry сдвиг + эталон
Сверка по meeting_id трёх источников (Obsidian-файлы, MOFS-реестр, PFS-реестр); бэкап перед
чисткой; план — архитектору на подтверждение; пауза ownCloud-синка на окне «убрать файлы →
MFF перекачает»; ручной `run-pending` обязан `export PFS_POST_SWITCH=1`. **Полный текст —
см. references/pitfalls.md.**

### Q. task_slug picker warning: две разные ветки, лечить раздельно
(1) `skipped (…empty closed list…)` — нет `task_slug`; backfill
`entity-registry backfill-task-slug -y`. (2) `LLM empty response` — сигнал в тексте задачи не
виден (смотрел только assignee); фикс §33: сигнал = assignee ∪ task.text. **Полный текст —
см. references/pitfalls.md.**

### T. Имена участников/исполнителей молча теряют тег при изменении формата самари
Смена формата имён (Фамилия Имя vs Имя Фамилия) → резолв не матчит → голый текст без тега
(fail-soft). Проверять формат имён, не роутинг. Слипшийся слаг (`AI-аналитик.Написать`) —
штатно §34. **Полный текст — см. references/pitfalls.md.**

### S. `summarize_error: LLM summary failed section validation` — валидатор/промпт рассинхрон (не таймаут, не модель)
Валидатор exact-match режет заголовок, который промпт-шаблон требует расширенным (пример:
`Риски (Кто…):` vs `Риски:`). Лечение: синхронно менять имена секций / приводить regex к
шаблону; таймаут/модель ни при чём. **Полный текст — см. references/pitfalls.md.**

## Связанные скиллы
- `protocolfrom-summary` — основной скилл PFS
- `hermes-feature` — процесс разработки через Cursor

## R. Слаг: где ставится, и целевой дизайн «в необработанных до переноса»
Слаг ставит ТОЛЬКО PFS (`apply_task_slugs` в `pipeline.py`, ~стр. 521); MOFS пишет лишь
`project_bind` (тень-гипотеза). Целевой дизайн: слаг виден до переноса. Правило 1:1 — слаг из
контекста задачи, не «главной темы»; bind на `one_on_one` (`kirill_1on1`) не источник
префикса — честная пустота AC-006. **Полный текст — см. references/pitfalls.md.**
