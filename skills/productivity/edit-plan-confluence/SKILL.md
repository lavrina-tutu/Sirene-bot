---
name: edit-plan-confluence
description: "Заливка плана MS Project (.mpp/.zip) на страницу Confluence с макросом gantt-chart-planner: полная замена JSON-вложения, календарь MPP, блок «Итого», создание дочерней страницы. Триггеры: «поправь план», «обнови план на страничке», «помести план на страничку», «скорректируй план», «добавь задачу в план», «создай страницу с планом», «поставь гант на страницу» + файл .mpp/.zip. Гейт: дифф + «лей»/«пиши»/«да». Без pageId — спросить. Живая AB 519492935 — только с --allow-live-ab."
version: "0.3.0"
platforms: [linux]
tools: [terminal, read_file, write_file]
metadata:
  hermes:
    tags: [confluence, gantt, plan, mpp, ms-project, gantt-chart-planner]
    related_skills: [tutu-confluence-jira, read-mpp]
---

# Edit Plan Confluence — MPP → gantt-chart-planner

Скилл `productivity/edit-plan-confluence`: залить план MS Project на страницу Confluence с макросом **gantt-chart-planner**. v1 = только полная заливка MPP (не поштучные правки).

## Триггеры

- «поправь план», «обнови план на страничке», «помести план на страничку»
- «скорректируй план», «добавь задачу в план» (без .mpp → отказ: v1 только заливка файла)
- «создай страницу с планом», «поставь гант на страницу»
- файл `.mpp` или `.zip` с `.mpp` внутри (как `read-mpp`)

## Авторизация

Токен Confluence — только `CONFLUENCE_TOKEN` из `~/USERTOOLS/ConfluenceSync/.env`:

```bash
load_confluence_env() {
  while IFS='=' read -r _k _v; do
    case "$_k" in CONFLUENCE_TOKEN|WORKVAULT_PATH) [ -n "$_v" ] && export "$_k=$_v" ;; esac
  done < "$HOME/USERTOOLS/ConfluenceSync/.env"
}
```

База: `https://dom.tutu.ru`. Не использовать `web_extract` на dom.tutu.ru.

## CLI (скрипты скилла)

```bash
PY=~/hermes-agent/.venv/bin/python3
CLI=~/hermes-workspace/skills/productivity/edit-plan-confluence/scripts/cli.py

# preview (GET only)
$PY $CLI preview --page-id 519501810

# дифф перед записью
$PY $CLI diff --page-id 519501810 --mpp /path/plan.mpp

# заливка после «лей»
$PY $CLI apply --page-id 519501810 --mpp /path/plan.mpp --confirm лей

# дочка от родителя
$PY $CLI diff --page-id 519501810 --child --mpp /path/plan.mpp
$PY $CLI apply --page-id 519501810 --child --mpp /path/plan.mpp --confirm лей

# оффлайн конвертер
$PY $CLI convert --mpp /path/plan.mpp --out /tmp/out.json

# исключить связь FROM→TO (когда плагин завышает срок из-за лишней зависимости)
$PY $CLI diff --page-id 519501810 --mpp /path/plan.mpp --drop-dep 28:19
$PY $CLI apply --page-id 519501810 --mpp /path/plan.mpp --confirm лей --drop-dep 28:19
```

## Прогон в чате

1. Резолв `pageId` из сообщения / сессии; нет → спросить (не угадывать 519492935).
2. Файл `.mpp`/`.zip` → `read_mpp.py` → CSV → конвертер + календарь MPP.
3. Собрать JSON: MPP / копия с родителя / пустой шаблон (правило C для дочки).
4. Патч «Итого» (одна строка `Итого: с DD.MM.YY по DD.MM.YY - N рабочих дней` над макросом; «Трудозатраты» не создавать и удалять из storage, если есть; третью про 70% не создавать).
5. **Гейт:** показать дифф, ждать «лей»/«пиши»/«да».
6. Запись: POST `/data?conflictPolicy=override` (не PUT!) → PUT storage.
7. Отчёт: URL, версия вложения, «Итого»; если в диффе есть предупреждение про срок плагина — привести вариант `--drop-dep` и дать Саше решить.

> **Важно про срок проекта:** плагин gantt-chart-planner **сам пересчитывает срок проекта как критический путь** (сумма длительностей по самой длинной цепочке зависимостей), игнорируя готовые start/end, записанные в JSON. `Итого: ... N рабочих дней` и `duration` корня = из MPP, а вот что покажет диаграмма — считается плагином. Расхождение (`⚠ плагин покажет X дней, а не N из MPP`) почти всегда не календарь и не баг — это лишняя/доморощенная зависимость, сериализующая параллельные ветки. Исключи её `--drop-dep FROM:TO` (см. кейс «42 вместо 37»).

## Питфоллы

- **MPP ↔ Confluence gantt reconciliation:** source of truth is the MPP file («mpp главнее»). Applies ONLY to Confluence-gantt comparison — Jira reconciliation (`plan-reconciliation-mpp-jira`) has a different SoT; do not copy this rule there.
- `idCounter` = max(все id)+1, **не** 300000.
- Активные ресурсы = max id на имя; мёртвые копии не включать.
- На существующем макросе `macro-id`/`id`/`hash` не менять.
- PUT страницы плана уходит с `version+1` (re-read версии перед PUT + инкремент, optimistic lock Confluence): не слать текущую версию as-is — иначе HTTP 409 `Version must be incremented`. `conflictPolicy=override` для страницы НЕ использовать (потеряет защиту от перезаписи чужой правки).
- Календарь MPP: обед 12–13, ночь 18–09, сб/вс; исключения `endDate = toDate+1`.
- M (чел-ч) в **тексте гейта** = ceil(sum work назначений), не summary-задачи; в storage страницы не пишется — только одна строка «Итого» с датами и N рабочих дней.
- Живая AB `519492935` — только `--allow-live-ab` + явный pageId.
- **Срок проекта в плагине ≠ корневому duration MPP:** плагин пересчитывает срок как критический путь по связям. Расхождение (напр. 42 vs 37) — лишняя зависимость, сериализующая ветки. Верифицировать через `critical_path_days()`, исключать `--drop-dep FROM:TO`. Это не календарь — правки календаря здесь не помогут.

## Тестовые страницы

| pageId | Назначение |
|--------|------------|
| 519501810 | Тестовая (приёмка v1) |
| 519492935 | Живая AB — не трогать без явной команды |

## Файлы

- `references/empty-gantt-template.json` — пустой шаблон
- `references/mpp-to-gantt.md` — рецепт конвертера
- `scripts/` — env, conf_client, mpp_convert, mpp_calendar, itogo, macro, gantt_attachment, child_page, gate_diff, pipeline, cli

## Связанные скиллы

- `read-mpp` — тот же вход `.zip`; другой выход (GS). Вызывать только `read_mpp.py` для CSV.
- `tutu-confluence-jira` — паттерн `load_confluence_env`.
- `confluence-gantt-plan` — **deprecated**, см. `edit-plan-confluence`.
