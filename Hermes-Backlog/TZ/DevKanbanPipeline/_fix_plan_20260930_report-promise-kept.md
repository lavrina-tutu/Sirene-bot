# `_fix_plan` — report-promise-kept (BUG:diagnose t_dc075dc2)

Дата: 2026-09-30
Слаг: `report-promise-kept`
Кейс (оценка архитектора, **не** команда skip): **BUGFIX** полный, не LIGHT
Диагностика: только чтение (kanban.db / notify-list / cron output / скиллы / DKP). Ничего не менялось, кроме этого файла-плана.

Диагноз и план: архитектор `cursor-grok-4.6-high` (фаза `BUG:diagnose`, карточка `t_dc075dc2`, граф `DEV/report-promise-kept`).

Смежный, **не** этот баг: `_fix_plan_done-gate_20260929.md` (operator-hold / «done пока Саша не сделал глагол»). Здесь дыра другая: работа **уже сделана**, Саша **не увидел** результат, пока сам не спросил.

---

## 0. Диагноз одной фразой

Файл на диске / `kanban_comment` / аттач **не есть** доставка Саше. Контракт `AC-delivered:` закрывает только отчёт AC на `GATE:done`. Аудит/диагноз/блокер закрываются молча: R5 `BUG:diagnose` не подписан, корень-контейнер complete’ится **до** результата, крон `4b115ecdb1da` смотрит только **открытые** карточки и на тике после complete пишет «все хвосты завершены» **без тела отчёта**.

---

## 1. ROOT CAUSE (три независимых разрыва, нужен любой один)

Инцидент 30.09: `DEV/audit-closed-cards-verify`.

| Время (MSK) | Факт |
|---|---|
| 09:56 | Корень `t_40143bf8` create, workspace `scratch`. Body: «Далее репорт Саше таблицей **в чат**». |
| 09:57–10:06 | Корень running → complete (root-as-container). Summary: «спек передан потомку `t_98682c84`… Ждём диспетчер». **Отчёта ещё нет.** |
| 10:06 | `notify-list` корня: `telegram:-1004300127777:**3**` `notify+wake`. Child `t_98682c84` — **0 подписок** (канон R5: `BUG:diagnose` не подписывать). |
| 10:06 / 10:17 | Крон `4b115ecdb1da` (deliver `:1`): сначала «граф в работе», затем (после complete корня) «активных DEV нет», `t_98682c84` на 10:17 **не упомянут** как живая работа. |
| 10:46–11:14 | Child run #762: comment с таблицей + `kanban_complete` + аттач `AUDIT-REPORT-FINAL.md`. Summary **самозаявил** «Отчёт-таблица **в чат** + аттач». |
| 11:08 | Крон: `t_98682c84` ещё `running`, «новых закрытий нет». |
| 11:14 | Карточка `done`. Файл: workspace корня `t_40143bf8/AUDIT-REPORT-FINAL.md` (12:54 копия) и `attachments/t_98682c84/AUDIT-REPORT-FINAL.md`. |
| 11:20 | Крон **после** complete: «Завершилось с прошлого тика: **новых завершений не фиксирую**». Итог: «все хвосты завершены». Тела отчёта нет. |
| 11:32+ | То же: done=393, (д) пусто. Саша увидел итог **только после вопроса** «какой итог аудита?». |

### Разрыв A — воркер: «чат» = comment, не origin

`hermes-feature` требует пост в origin **только** для отчёта AC на `GATE:done` (маркер `AC-delivered:`). Done-критерий `BUG:diagnose` = «план/`_fix_plan` на диске» (таблица «Фазы ↔ скиллы»). Исследовательский/аудиторский отчёт в том же классе: диск + comment.

Воркер `t_98682c84` написал итог в `kanban_comment` и аттач, назвал это «в чат». Silent-воркер **не** имеет сессии origin. Self-report ≠ факт (уже питфолл оркестрации) — здесь тот же класс: complete с ложью о канале.

Нет маркера вида `RESULT-delivered:` / запрета complete, если Саша-facing артефакт не ушёл в courier.

### Разрыв B — R5 + root-as-container: wake срабатывает не на тот event

Канон DKP / `kanban-dev-cases` п.8: **не** подписывать `BUG:diagnose`. Набор R5 **не расширять** (AC-002) — этот план **не** предлагает подписать diagnose.

Корень **был** подписан (`:3`, `notify+wake`). Terminal `completed` корня ушёл в **10:06** с текстом «расконтейнерен, ждём диспетчер» — это **не** отчёт. Когда отчёт появился в 11:14, подписанная карточка уже `done`, нового terminal на корне нет. Child без sub → тишина.

### Разрыв C — крон-напоминание `4b115ecdb1da`: статус-тикер, не курьер результата

Промпт job `4b115ecdb1da` (enabled, interval 10m, `deliver: telegram:-1004300127777:1`):

- Фильтр п.1: только **открытые** (не done / не archived).
- П. (д) «что завершилось с прошлого тика» — **не операционализирован**: нет команды «`kanban list`/SQL карточки с `completed` в окне с прошлого run». Агент **выводит** «ничего не закрылось» из пустого open-list.
- Стоп-фраза: «если не-done графов нет и ошибок нет — кратко „все хвосты завершены“… и стоп» — на тике **сразу после** последнего complete срабатывает и **проглатывает** payload.
- Канал крона = **`:1`**, origin инцидента = **`:3`**. Даже идеальный (д) сейчас не обязан нести тело в origin (Саша явно указал этот крон как courier — `:1` допустим как канал напоминания; origin не подменять `:7`/DM).

Наблюдаемо: `deliveries.db` для этих execution `content` len=0 (текст живёт в `cron/output/4b115ecdb1da/*.md`, не в колонке deliveries) — на диагноз не влияет; факт недоставки тела Саше = файлы 11:20 / 11:32.

---

## 2. Что это **не** есть

| Не путать | Почему |
|---|---|
| Баг preflight `AC-delivered` (`_fix_plan_20260925_preflight-ac-report-delivery.md`) | Там `GATE:done` + список AC ≠ отчёт. Здесь фазы **без** `GATE:done`, отчёт аудита. |
| Operator-hold (`_fix_plan_done-gate_20260929.md`) | Там done **раньше** действия Саши. Здесь done **без показа** уже готового результата. |
| Расширение R5 на `BUG:diagnose` | Запрещено AC-002 / шум промежуточных `completed`. Courier = существующий крон + маркер, не новый subscribe-set. |
| Ядро канбана / `TERMINAL_KINDS` | Не трогать. |
| Новый крон / новый скилл / USERTOOL | Reuse: `hermes-feature` + `kanban-dev-pipeline-orchestration` + `kanban-dev-cases` + **существующий** job `4b115ecdb1da`. |

---

## 3. Целевой контракт (канон)

**Результат фазы, адресованный Саше** (отчёт, факт завершения с выводом, блокер с причиной) обязан попасть в **хотя бы один** живой канал без вопроса Саши:

1. **Origin-топик** графа — если карточка в наборе R5 (`notify+wake`) **и** событие ещё впереди (не «complete корня до работы»).
2. Иначе / страховка: **крон `4b115ecdb1da`**, пункт (д), **с телом** (не «карточка done»).

Инвариант: `path на диске` ∨ `kanban_comment` ∨ `attachment` **≠** доставка. Как `AC-delivered:` для AC-отчёта.

Маркер (тот же класс, что `AC-delivered:` / `flag-waived: Sasha`):

```
RESULT-delivered: reminder
## Итог
<тело или первые ~4 КБ + abs-path полного файла>
```

Допустимо: `RESULT-delivered: origin` — если воркер/оркестратор реально постил в origin **до** complete (как AC). Голый `RESULT-delivered:` без хвоста — FAIL (как голый `AC-delivered:`).

`AC-delivered:` на `GATE:done` **не** заменяется: AC-отчёт по-прежнему origin + маркер на `GATE:done`. `RESULT-delivered:` — для всего остального Саша-facing (diagnose, RS, аудит, блокер, «вернусь с отчётом»).

**Запрет complete** (скилл, не ядро): если body/title/summary карточки обещает отчёт Саше / «в чат» / таблицу итогов, а маркера нет — `kanban_block(kind=transient, reason="RESULT pending courier")` **или** дописать маркер после того, как тело лежит в comment в форме, которую крон обязан процитировать. Не complete с фразой «отчёт в чат», если чат = comment.

Root-as-container: complete корня с summary «ждём диспетчер» **не** закрывает обязанность доставки. Доставка — на карточке, где появился артефакт (обычно `BUG:diagnose` / `RS:analyze` / `GATE:done`).

---

## 4. Оценка объёма / LIGHT

**Не LIGHT.** Причины (GLOSSARY §2 LIGHT: ≤3 файла кода+тест+скилл, без новых сущностей/**cron**/.env/манифеста):

- Пишется **промпт существующего** `jobs.json` job `4b115ecdb1da` — файл общего state, writer = `ORCH:shared-state` (`LOCK_EX`).
- Канон — аддитивная секция DKP (ТЗ).
- Скиллы: ≥3 (`hermes-feature`, `kanban-dev-pipeline-orchestration`, `kanban-dev-cases`; зеркало `tz-workflow` одной строкой).

Семейство: **BUGFIX** (поведенческий баг пайплайна). LIGHT-сужение — **только оркестратор** после `GATE:diagnose-review`, если решит не трогать DKP и обойтись 2 скиллами + comment на job без `jobs.json` (хуже: промпт живёт в json). Рекомендация архитектора: полный BUGFIX с `TZ:patch` DKP + ORCH на job.

Файлы impl (оценка, оркестратор не обязан копировать список как skip-фаз):

| # | Путь | Что |
|---|---|---|
| 1 | `~/hermes-workspace/skills/devops/hermes-feature/SKILL.md` (канон → restore) | Протокол complete: Саша-facing → маркер `RESULT-delivered:` + тело в comment; запрет «в чат» без маркера; diagnose не равен «только диск». Bump version. |
| 2 | `~/hermes-workspace/skills/devops/kanban-dev-pipeline-orchestration/SKILL.md` | Новый питфолл: прецедент `t_40143bf8`/`t_98682c84`; файл ≠ Саша увидел; корень-контейнер complete ≠ доставка. |
| 3 | `~/.hermes/skills/devops/kanban-dev-cases/SKILL.md` | Правило в «Ключевые правила»: результат фазы → reminder/origin; R5 set **без** изменений. |
| 4 | `~/hermes-workspace/skills/devops/tz-workflow/SKILL.md` | Одна строка: TZ/BRF в origin как сейчас; не-R5 итоги — `RESULT-delivered` + крон. |
| 5 | `~/.hermes/cron/jobs.json` ключ `4b115ecdb1da`.prompt | Операционализировать (д); снять стоп до (д); не новый job. Только ORCH. |
| 6 | `TZ/DevKanbanPipeline/DevKanbanPipeline_TZ.md` | Аддитивная секция + AC-R0x; bump 0.4.3. `TZ:patch` не impl. |

Тесты: grep-смоук скиллов + фикстура «карточка done 5 мин назад с comment RESULT-pending / телом отчёта» → чеклист промпта крона требует процитировать тело. Отдельный pytest не обязателен, если промпт не выносится в `.py`. Ядро не патчить.

---

## 5. ПЛАН ПОЧИНКИ П.1…П.N

Порядок фаз графа задаёт **оркестратор** (G5). Ниже содержание, не `kanban_create`.

### П.1. Канон DKP — `TZ:patch`

`DevKanbanPipeline_TZ.md` bump **0.4.3** (аддитивно к 0.4.2). Секция «Результат фазы → Саша (report-promise-kept)»:

- Инвариант диск/comment/аттач ≠ доставка.
- Маркер `RESULT-delivered: origin|reminder`.
- `AC-delivered:` без изменений (только `GATE:done` / AC-отчёт).
- R5 набор **заморожен**; courier не-R5 = job `4b115ecdb1da`.
- Root-as-container complete не аттестует доставку.
- Прецедент `t_98682c84` 30.09.

GLOSSARY: один абзац в §3 или §6 (артефакт маркера), без новых фаз. `DialogBacklogToKanban` не трогать.

**IAC-01** | TZ:patch→REV:tz | `DevKanbanPipeline_TZ.md` | `rg -n "RESULT-delivered" DevKanbanPipeline_TZ.md` | — | AC-R01, AC-R05

### П.2. Воркер `hermes-feature`

В «Протокол воркера» / чек-лист фаз / Блок 6В / GATE:done (рядом, не смешивая AC):

Перед `kanban_complete` любой фазы, чей выход для Саши (отчёт, таблица, вердикт аудита, `_fix_plan` как ответ на «разберись», блокер с вопросом):

1. Тело в `kanban_comment` (уже часто есть).
2. Строка `RESULT-delivered: reminder` (или `origin`, если пост в origin был **в этом** ходе).
3. Не писать в summary «в чат» / «отчёт доставлен», если маркера нет.
4. `BUG:diagnose`: диск `_fix_plan` **и** маркер; иначе block transient.

Не требовать от silent-воркера `send_message` в TG (у крона DELIVERY сам). Обязанность воркера — **пакет для курьера**.

**IAC-02** | HF:impl→HF:test | `hermes-feature/SKILL.md` | `rg "RESULT-delivered" hermes-feature/SKILL.md` и 0 рабочих «отчёт в чат» как done-критерий без маркера | IAC-01 | AC-R01, AC-R05

### П.3. Координация — питфолл оркестрации + kanban-dev-cases

`kanban-dev-pipeline-orchestration`: питфолл N — «файл на диске ≠ Саша увидел»; таблица инцидента; запрет считать complete корня доставкой; крон (д) обязан цитировать тело.

`kanban-dev-cases`: пункт правил (не меняя R5-список).

**IAC-03** | HF:impl→HF:test | оба SKILL.md | `rg "t_98682c84|RESULT-delivered|report-promise-kept"` | IAC-02 | AC-R01

### П.4. Промпт крона `4b115ecdb1da` — `ORCH:shared-state`

`jobs.json` под `LOCK_EX`. Job **не** создавать заново (тот же id). В prompt после п.4 добавить обязательный п.5 ≈:

```
5. ЗАВЕРШЁННОЕ С ПРОШЛОГО ТИКА (не выводить из пустого open-list):
   - Взять last_run_at этого job (или «10 мин назад»).
   - Найти карточки status=done с completed в этом окне (не только title DEV/; включая BUG:/RS:/GATE:).
   - Для каждой: summary + последний comment + имена attachments.
   - Если есть отчёт-таблица / _fix_plan / «Итог» / RESULT-delivered / AC-delivered —
     процитировать ТЕЛО (до 4000 символов) + abs-path файла. «Карточка закрыта» без тела = провал тика.
6. Стоп «все хвосты завершены» — ТОЛЬКО после п.5. Если п.5 непустой — доклад (д) обязателен, даже если open DEV=0.
IDEA/triage по-прежнему не исполнять.
```

Не менять `deliver` на `:7` / DM. Остаётся `:1`, пока Саша не скажет иначе. Origin `:3` не обязан совпадать — это выбранный канал напоминания.

**IAC-04** | ORCH→GATE:done | `jobs.json` id `4b115ecdb1da` | `python3 -c` json load; prompt содержит «ЗАВЕРШЁННОЕ С ПРОШЛОГО» и запрет стопа до (д); `id` тот же | IAC-03 | AC-R02, AC-R03, AC-R04

### П.5. Смоук (HF:test, без живого аудита 391 карточки)

1. `rg` leftover: в рабочих (не changelog) кусках скиллов нет «отчёт в чат» как критерия complete без `RESULT-delivered`.
2. R5: `rg` «подписать BUG:diagnose» = 0 новых; набор как AC-002.
3. Сухой прогон логики п.5: по `kanban show t_98682c84` comment 11:13 + attachment — текст, который крон **должен** был унести 11:20; чеклист промпта это покрывает (ревью текста, не обязательно live tick).
4. Не рестартовать gateway. Не слать тестовый мусор Саше в боевой `:1` без пометки смоук / без согласия.

**IAC-05** | HF:test | скиллы + jobs.json | команды IAC-02…04 + ручной diff промпта vs этот план §П.4 | IAC-04 | AC-R04, AC-R06

### П.6. Docs-handoff / ORCH

Bump версий скиллов; `restore-all-skills.sh` — ORCH. Манифест: новая сущность **не** нужна (`dev_kanban_pipeline` уже есть). Digest — если ORCH и так гоняет render.

---

## 6. Критерии приёмки пакета (черновик `AC-R0x` для TZ:patch)

Только этот пакет. Payload будущего `GATE:take-into-work`.

### AC-R01 — воркер не complete «в чат» без маркера
В `hermes-feature` (и зеркале orchestration/dev-cases) complete Саша-facing фазы требует `RESULT-delivered: origin|reminder` в comment. Наблюдаемо: `rg`.

### AC-R02 — крон (д) читает недавно done
Промпт `4b115ecdb1da` обязывает искать `done` в окне с прошлого тика и цитировать тело отчёта. Наблюдаемо: json prompt.

### AC-R03 — стоп не раньше (д)
Фраза «все хвосты завершены» не отменяет п.5, если окно complete непустое.

### AC-R04 — R5 не расширен
`BUG:diagnose` по-прежнему без subscribe. 0 leftover «подписать diagnose».

### AC-R05 — диск ≠ доставка
В DKP явная строка инварианта. Смоук: сценарий «файл есть, маркера нет» в скилле = block/не complete.

### AC-R06 — complete корня-контейнера ≠ доставка результата
В orchestration питфолл с прецедентом `t_40143bf8` 10:06 vs отчёт 11:14.

---

## 7. IAC (полный хвост; LIGHT не рекомендован)

```
IAC-## | phase_from→phase_to | path | verify | depends | covers
IAC-01 | TZ:patch→REV:tz | DevKanbanPipeline_TZ.md | rg RESULT-delivered | — | AC-R01 AC-R05
IAC-02 | HF:impl→HF:test | hermes-feature/SKILL.md | rg RESULT-delivered; нет done=«в чат» без маркера | IAC-01 | AC-R01 AC-R05
IAC-03 | HF:impl→HF:test | kanban-dev-pipeline-orchestration + kanban-dev-cases | rg t_98682c84 / report-promise-kept | IAC-02 | AC-R01 AC-R06
IAC-04 | ORCH→GATE:done | ~/.hermes/cron/jobs.json | id=4b115ecdb1da; prompt п.5–6 как §П.4 | IAC-03 | AC-R02 AC-R03 AC-R04
IAC-05 | HF:test→GATE:done | скиллы+json | IAC-02…04 + R5 rg | IAC-04 | AC-R04 AC-R06
```

---

## 8. Риски

| Риск | Митигация |
|---|---|
| Крон `:1` vs origin `:3` — Саша смотрит не General | Канон: этот job **и есть** канал напоминания (решение постановки). Не плодить второй job. Явный «пиши в :N» по-прежнему override графа, не этого крона. |
| Шум (д) на каждом мелком complete | Цитировать тело **только** если comment/summary/attachment похожи на отчёт/маркер; иначе одна строка id+summary. |
| Воркер ставит маркер без тела | Как AC-delivered: regex хвоста `\S+` **и** непустой блок после заголовка «Итог». |
| Двойной канон с done-gate operator-hold | Не смешивать пакеты; в DKP две секции. |
| LIGHT «только скилл, jobs.json руками в чате» | Тогда (д) снова протухнет. ORCH обязателен. |

---

## 9. Что НЕ трогать

- Ядро `kanban_db*` / `TERMINAL_KINDS` / expand R5.
- Новый крон, новый скилл, USERTOOL.
- Gateway restart.
- `DialogBacklogToKanban`.
- Переписывание `AUDIT-REPORT-FINAL.md` / повтор аудита 392 карточек.
- Авто-complete кризисных `GATE:go` / `block-accept`.

---

## 10. G5

Этот файл — содержание диагноза. `kanban_create` графа / `--case` / skip фаз — оркестратор, не эта карточка.
