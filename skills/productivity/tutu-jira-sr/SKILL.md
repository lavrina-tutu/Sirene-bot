---
name: tutu-jira-sr
description: "Self-Review (SR) в Jira ТУТУ: план периода (plan), заполнение плана (fill), сверка чужого SR (check), итоги своего SR (selfcheck). Триггеры: self-review, SR, мой SR, заполнить SR, проверить SR, план на период, итоги периода, оценка по SR, перенести открытые пункты."
version: 1.13.0
author: agent
license: MIT
platforms: [linux]
metadata:
  hermes:
    tags: [TUTU, JIRA, SR, self-review, WorkVault, Obsidian]
    related_skills: [tutu-confluence-jira, tutu-jira-okr]
---

# TUTU Jira Self-Review (SR)

Задачи issuetype `SR` на `hq.tutu.ru` (напр. `SR-37535`). Архитектурное ТЗ: `WorkVault/Hermes-Backlog/TZ/SRTool/SRTool_TZ.md`. Авторизация JIRA — см. `tutu-confluence-jira`.

## Env

Инструмент грузит env сам. Канон: `~/.hermes/profiles/default/.env`; fallback: `anthropic/.env`. **Не** `source` вручную в сессии агента.

## Поля SR (always-on)

| Поле | ID | Когда |
|---|---|---|
| Результат (план) | `44401` | начало периода |
| Критерии (план) | `44402` | начало, автодерив из 44401 |
| OKR/KPI (план) | `44403` | начало, автодерив из 44401 |
| Итог: выполнено | `44404` | конец периода |
| Итог: сложности | `44405` | конец периода |
| Итог: развитие/пробелы | `44406` | конец периода |
| Поведение | `44414` | конец, часто `None` |

`44405` = «Итог: сложности» в Jira / «Каких знаний или навыков не хватило» в UI — **не** фильтр «только невыполненные».

## Transitions (always-on)

PUT на эти поля **не работает** — только transition.

| ID | Назначение |
|---|---|
| `61` | «Отредактировать SR» — **план** 44401–44403 |
| `271` | «Заполнить итоги» — **итоги** 44404–44406 |
| `11`/`281` | согласование — **только пользователь**, не агент |

⚠️ Итоги через `61` → `400`. Перед каждой заливкой — `GET /issue/{key}/transitions`, не кэшировать id из начала сессии.

## Маршрутизатор CLI (SRTool)

`cd ~/USERTOOLS/SRTool`. **PLAN/FILL только через команды srtool** — не ручной curl на поля SR.

| Намерение | Команда |
|---|---|
| Итоги (selfcheck) | `python3 -m srtool report SR-XXXXX [--from … --to …]` |
| Превью план/факт | `python3 -m srtool preview SR-XXXXX` |
| Заполнение плана (fill) | srtool fill-команды (см. SRTool_TZ.md) |

Запрещено: `curl PUT` на 44401–44406; transition без свежего GET transitions. Исключение: `SR_BYPASS` с явной причиной (инструмент недоступен).

## Ключевые правила

- **skill_view один раз за сессию**; детали — `read_file references/<flow>.md` по триггеру.
- **Вывод:** не сырой GET в чат; правки плана/итогов — diff; заливка только по явной команде.
- **CHECK** — чужой SR с заполненными итогами; **SELFCHECK** — свой, 44404–44406 пусты.
- **PLAN** — факт предыдущего SR (44404–44406) первым; см. `references/flow-plan.md`.
- **Оргструктура:** `contacts.enc` → `find_subordinates`, не по памяти.
- **Правки методики SR** — архитектору (Cursor), не default в чате.

## Питфоллы (кратко)

- `patch` на по-пунктовой MD — риск дублей; после patch — `read_file` целиком (`references/pitfalls.md`).
- Блок 5 — **все N целей**, включая выполненные; «Проблем не было» + «Итог:».
- % чекина OKR может противоречить тексту — открытый вопрос пользователю.
- Доп. факт без привязки к пункту — переспросить, к какому п. относится.

## References

| Файл | Когда читать | Триггер |
|---|---|---|
| `references/flow-plan.md` | план нового периода, 44401–44403 | план на период, перенос |
| `references/flow-selfcheck.md` | итоги 44404–44406, бриф блока 5 | selfcheck, итоги, report |
| `references/flow-check.md` | сверка чужого SR | проверить SR, check |
| `references/flow-fill-push.md` | заливка transition, 204 | залей, fill, push |
| `references/pitfalls.md` | patch, 44405, % чекина | правка MD, блок 5 |
| `references/verification.md` | полный чеклист | перед заливкой/отчётом |

## Verification Checklist (краткий)

- [ ] SELFCHECK/CHECK: сначала `srtool report`/`preview`; ручной флоу — при сбое
- [ ] FILL/PLAN: transition `61`; итоги: `271`, не `61`
- [ ] Перед **каждой** заливкой — свежий `GET /transitions`
- [ ] PLAN: факт прошлого SR первым; заливка только 44401–44403
- [ ] SELFCHECK: блок 5 по всем N целям + «Итог:»; draft → check → заливка
- [ ] CHECK: критерии поштучно; объективность — причинно-следственная связь
- [ ] Заливка: только явно запрошенные поля; `\r\n`, буллет `·`
- [ ] rclone sync после WorkVault
- [ ] Полный чеклист: `references/verification.md`
