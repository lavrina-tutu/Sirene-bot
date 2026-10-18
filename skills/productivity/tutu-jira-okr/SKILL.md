---
name: tutu-jira-okr
description: "OKR: итоги и решения из стенограммы"
version: 2.3.2
author: agent
license: MIT
platforms: [linux]
metadata:
  hermes:
    tags: [TUTU, JIRA, OKR, OKRS, OKRAID, WorkVault, Obsidian, чекин]
    related_skills: [tutu-confluence-jira, obsidian, pm-briefing, tutu-jira-sr]
---

# TUTU Jira OKR

Objective (issuetype 6) + KR (UserStory 12809), связь **Contains** через `issuelinks` (не `parent`). Период — `fixVersion`, не текст названия. Авторизация JIRA — см. `tutu-confluence-jira`.

## Env

Инструмент грузит env сам. Канон: `~/.hermes/profiles/default/.env`; fallback: `anthropic/.env`. **Не** `source` вручную в сессии агента.

## Маршрутизатор CLI (OKRTool)

Любая операция с чекин-полями — **только через OKRTool**, не curl (кроме `OKR_BYPASS`).

| Намерение | Команда (`cd ~/USERTOOLS/OKRTool`) |
|---|---|
| Прочитать чекин | `python3 -m okrtool.cli checkin show --keys …` |
| Подтянуть из Jira | `python3 -m okrtool.cli checkin pull --keys … --force` (только после «обнови») |
| Предложить по SR | `python3 -m okrtool.cli checkin propose --period …` |
| Записать поля | `apply` → `push --keys … --confirm` |
| Родители / годовые KR | `python3 -m okrtool.cli checkin parents --keys …` |

Запрещено: `curl POST /search`, `curl PUT /issue` на чекин-поля.

## Правило №0: локальный MD первым

Перед Jira: glob `**/OKRS-*_*.md` / `**/OKRAID-*_*.md` по всему `WorkVault/Projects/okr-tool/`. MD есть → работать с диска; Jira только по явному «обнови». Детали: `references/flow-checkin.md`.

## Направление связи Contains (канон OKRS)

Со стороны **KR (UserStory)** к Objective (Большая задача) связь читается как **«is contained in»** — у KR физически записано `inwardIssue = <родитель-Objective>`, outward пуст. У Objective (родителя) те же связи видны как `outwardIssue = <KR>`; у самой Objective связь к её родителю — `inwardIssue`.

**Питфолл направления:** при создании связи из Objective-родителя `POST /issueLink` указывать `outwardIssue` = родитель-Objective, `inwardIssue` = KR (UserStory). Иначе у KR получится зеркальное `outwardIssue` вместо `inwardIssue`, и связь будет читаться в обратную сторону. Проверять с трёх сторон: родитель `out=<KR>`, KR `in=<parent>`, родитель `in=<его родитель>`.

Между задачами проекта OKRS всегда используем связь **Contains** (KR→Objective = is contained in; Objective уровнем выше = Contains).

## Карта полей чекина (compact)

| Поле | ID |
|---|---|
| Тип OKR | `43701` |
| Подразделение | `43743` |
| Уверенность | `43706` |
| Что было сделано | `43822` |
| Риск/проблема | `43717` |
| Текущее значение метрики | `43713` |
| Плановое значение метрики | `43711` |
| % выполнения | `43782` |
| Дата обновления % | `43715` |
| Метрика | `43739` |
| Вышестоящая задача | `44600` |
| Вложенные задачи | `44601` |

Полная карта + иерархия: `references/okr-jira-field-mapping.md`.

## OKRS vs OKRAID

| Параметр | OKRS | OKRAID |
|---|---|---|
| Link Objective→KR | Contains (`11400`) | Link (`10003`) |
| Objective create | стандарт | + `customfield_10007` (Epic Name) |
| Тип OKR у KR | обычно пусто | всегда пусто |

Код: `okrtool.okr_task.LINK_TYPE_BY_PROJECT`.

## Ключевые правила

- **Фильтр АИД по умолчанию:** `cf[43743] = "АИД"` во всех выборках (OKRS и OKRAID), пока пользователь явно не снял.
- **Писать чекин** только на assignee = Саша (`tkachenkoav`); чужих parent — логировать `STALE_PARENT`, не каскадировать.
- **Склейка с SR:** ключи из SR-плана (`srtool preview`); `checkin propose --period "Q3 2026"`.
- **OKR_BYPASS:** curl только если OKRTool недоступен / read-only поле; строка `OKR_BYPASS: …` в ответе.
- **skill_view один раз за сессию**; детали флоу — `read_file references/<flow>.md` по триггеру, не грузить все references сразу.
- **Вывод:** не сырой GET в чат; CLI `--compact`; правки плана — diff.

## Питфоллы (кратко)

- **Pitfall (A11):** field-ID map (`43782`/`43822`/`43717`/`43706`/`43715`) is REFERENCE ONLY — NOT a license to write via direct `curl PUT /issue`. All checkin-field writes → `okrtool checkin apply → push --confirm`; direct PUT only with `OKR_BYPASS` marker. Older note/MEMORY/past session saying «прямой PUT» = STALE (canon v2.3.0+): do not restore — remove from source.
- SR в Contains-цепочке — фильтровать KR по `issuetype == UserStory`.
- `parent` в JQL для OKR не работает — только `issuelinks`.
- Q1–Q4 в названии ≠ период — смотреть `fixVersion`.
- Пометка «Удалить» → риск реального удаления: `references/marking-for-deletion-incident.md`.
- Статус в мульти-проектном JQL может дать `400` — фильтровать в Python после выгрузки.

## References

| Файл | Когда читать | Триггер |
|---|---|---|
| `references/flow-checkin.md` | show/pull/apply/push, --fields, --grep, пакетный get | чекин, обнови, залей |
| `references/jql-and-view.md` | JQL, «мои OKR на месяц», statusCategory | выборка, что не закрыто |
| `references/clone-create.md` | клонирование KR, POST/transition/PUT | новый квартал, клон |
| `references/obsidian-export.md` | wiki-ссылки, GS, xlsx | выгрузка, Obsidian, таблица |
| `references/okr-jira-field-mapping.md` | полная карта полей, иерархия | неясный customfield |
| `references/marking-for-deletion-incident.md` | инцидент «Удалить» | пометка на удаление |
| `references/verification.md` | полный чеклист | перед отправкой отчёта |

## Verification Checklist (краткий)

- [ ] Чекин через okrtool; curl только с `OKR_BYPASS`
- [ ] Правило №0: glob MD по `okr-tool/` до Jira
- [ ] Фильтр `cf[43743] = "АИД"`; KR = UserStory; период из `fixVersion`
- [ ] Иерархия через `issuelinks` Contains, не `parent`
- [ ] Сверка % верхнего уровня со средним нижнего; расхождения — в отчёт, не править самому
- [ ] Wiki-ссылки с `\|`; столбцы таблиц совпадают
- [ ] Клонирование: постановка подтверждена; числа JSON-числом; Contains после create
- [ ] rclone sync после записи в WorkVault
- [ ] Полный чеклист: `references/verification.md`
