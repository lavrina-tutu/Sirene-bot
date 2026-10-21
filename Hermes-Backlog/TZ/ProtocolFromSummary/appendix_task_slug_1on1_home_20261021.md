---
tool: ProtocolFromSummary
kind: appendix
topic: task_slug_1on1_home
date: 2026-10-21
status: superseded
package: pfs-slagi-zadach-v-1on1-meetingah
master: ProtocolFromSummary_TZ.md §38 (v1.33.0) — superseded §39 v1.34.0
superseded-by: appendix_task_slug_1on1_from_context_20261021.md
---

# Appendix: meeting-home fallback для in-scope picker (21.10.2026)

**SUPERSEDED 21.10 вечером.** SoT слага in-scope — **§39** (`appendix_task_slug_1on1_from_context_20261021.md`).
§38 meeting-home (`Кирилл 1-1.` из display_name) отменён. Этот файл — исторические цитаты.

Справочник к §38 master-ТЗ (архив). `[NEW-ENTITY]` **нет**.

План: `Hermes-Backlog/dev/pfs-slagi-zadach-v-1on1-meetingah/_fix_plan_20261021.md`
(П.1). Код / `entities.json` / прогоны инструмента — **не** этот файл
(П.2–П.5).

---

## Что меняется одним предложением

In-scope задача после LLM+union **всегда** имеет ведущий префикс:
проектный `task_slug` **или** meeting-home. Норма §33/§34
«union=0 → пустой префикс = норма» для in-scope **снята**.

---

## Цитаты норм **до** (master 1.32.0)

### §29 — закрытый список, fail-soft, AC-004, AC-009

Закрытый список (master §29 «Закрытый список кандидатов»):

> Записи `entities.json` с `kind=project` **и** непустым `task_slug`.
> В список не входят 1-1 / `person_1on1` / `person` / `tool` / `misc` /
> `sync_aid` / `unknown`.

Fail-soft LLM (master §29 «In-scope + fail-soft LLM»):

> задачу опубликовать без нового слага; если у маршрута есть
> `route.tag_prefix` / `pfs.tag` (Лёня, транспортный `ЦУ.`) — оставить
> его как сейчас; иначе без префикса.

AC-004 §29:

> Если `task.text` **as-is** уже начинается с любого известного
> `task_slug` или `pfs.tag`, задача **не** идёт в batch LLM, повторный
> прогон / republish не дописывает второй префикс.

AC-009 §29:

> Diff не содержит `MarkObjectsFromSummary` / frontmatter `project_bind`
> / `task_slug` в summary. Grep USERTOOLS/MOFS по `task_slug` пуст.

AC-010 §29 (kind-валидатор):

> `kirill_1on1` с заполненным `task_slug` → fail

AC-011 §29 (TaskRefresh F2):

> `match_by_text` `startswith` по `pfs.tag` **или** `task_slug`

### §31 — allowlist 14

> Решение Саши 12.10 (§31 handover): closed_list = 14
> (`TASK_SLUG_BACKFILL_DEFAULT_ALLOWLIST`). … Этим пакетом allowlist
> **не** открывать

(канон размера списка живёт в §31; этот appendix его **не** двигает).

### §33 — таблица fallback и эталон «пусто = норма»

Таблица «Детерминированный fallback при пустом ответе LLM»:

| Матчей `task.text` ∩ closed_list | Действие |
|---|---|
| ровно 1 | `new_text = canonical_task_slug + orig_text` … без пробела после точки |
| 0 | `_fail_soft_text` (as-is; meeting-level `pfs.tag` если есть — как §29 fail-soft) |
| ≥2 | fail-soft, **не** угадывать |

Эталон 14.10 (задачи 3–6):

> 3–6 без префикса — норма, не «все шесть должны получить слаг».

AC-003 §33:

> Ноль входов → текст без проектного слага; LLM вызван; empty-warn нет,
> если assignee тоже без сигнала.

### §34 — union и eligible bind

Eligible bind:

> `slug` непустой **и** `slug ∈ closed_list` (14).
> `unbound` / `rejected` / `sr` вне 14 / пустой slug → игнор.

Таблица fallback union:

| `len(slug set)` | Действие |
|---|---|
| ровно 1 | canonical `task_slug` без пробела |
| 0 | `_fail_soft_text` (as-is; meeting-level `pfs.tag` если есть) |
| ≥2 | fail-soft, **не** угадывать |

Empty-warn §34:

> Empty-warn `"task_slug LLM empty response"` — только если сигнал
> (union) был, валидного выбора модели нет **и** fallback не склеил
> уникальный матч. Чистая 1-1 без union-сигнала — штатный fail-soft,
> empty-warn нет.

AC-009 §34:

> Diff пакета не содержит `USERTOOLS/MarkObjectsFromSummary` и не
> пишет `task_slug` / `project_bind.status` в summary. … PFS читает
> frontmatter read-only.

AC-012 §34:

> Ровно один slug в union → canonical prefix. Ноль → без проектного
> слага, empty-warn нет если сигнала не было. Два+ → fail-soft.

---

## Нормы **после** (§38; union=0)

Порядок (LLM → union → home) **не** ломает closed_list:

1. Валидный LLM-выбор из closed_list → проектный `task_slug`
   (`{slug}{текст}` без пробела после точки, AC-001 §29).
2. Union §34 ровно 1 → тот же канон проекта.
3. Union **0** → **meeting-home**, не as-is:
   `route.tag_prefix` (= `pfs.tag`) если задан, иначе
   `{display_name}.` сущности `route.entity`.
4. Union **≥2** → fail-soft **без** угадывания проекта **и без**
   meeting-home (home тоже был бы угадыванием «встречи вместо двух
   проектов») + empty-warn, как §34 D.

Bind `slug=kirill_1on1` **не eligible** (`slug ∉ closed_list`). Он не
голосует против `ai_analitik` и не подменяет проект. Home срабатывает
только когда проектного голоса нет.

`entities.<1on1>.task_slug` по-прежнему **запрещён** (валидатор kind,
AC-010 §29). 1:1 **не** входит в closed_list. Allowlist 14 / сущность
`sr` — без изменений (§31 / §34 AC-010).

### Формат meeting-home vs проектный

| Источник префикса | Склейка с текстом | Пример |
|---|---|---|
| Проектный `task_slug` | `{task_slug}{текст}` **без** пробела после точки | `AI-аналитик.Проверить наличие всех доступов` |
| Meeting-home | `{home} {text}` **с пробелом** после точки тега | `Кирилл 1-1. Перевести основную платформу на Codex` |
| Канон Лёни (уже на диске) | тот же fail-soft с пробелом | `Лёня 1-1. …` |

Не переводить home на `{slug}{текст}` без пробела: сломает опубликованные
«Лёня 1-1. …». Проектный формат **не** менять.

### Идемпотентность (AC-004 §29 жив, расширен)

Meeting-home входит в known prefixes фильтра входа batch: непустой
`pfs.tag` маршрута **и/или** `{display_name}.` сущности `route.entity`
(плюс прежние `task_slug` ∪ все непустые `pfs.tag` реестра). Republish
текста `Кирилл 1-1. …` при `tag_prefix=None` **не** идёт в LLM и **не**
удваивает префикс.

TaskRefresh F2 **код не патчить**: уже матчит `pfs.tag` любых записей с
блоком `pfs` (прецедент Лёня). Backfill `pfs.tag="{display_name}."` —
П.4 через EntityRegistryCLI, не этот TZ:patch и не поле `task_slug`.
До П.4 picker сам клеит display_name-home.

### Empty-warn

Только неспасённый union **≥2**. Union=0 + home — **не** warn.

Skip `empty closed list` / registry off / нет `llm_fn`: home **всё
равно** (закрытый список пуст не обнуляет 1:1-префикс). Проектный
маршрут picker по-прежнему skip (AC-002 §29).

---

## Эталон 21.10 (наблюдаемая выдача)

Встреча `2026-10-21 07-36-08 Кирилл 1-1`, площадка `523032632`,
якорь `pfsrow-b391f7f8daa6`. Picker in-scope, `tag_prefix=None`,
`kirill_1on1.task_slug` absent.

| # | Задача (сокр.) | Префикс | Основание |
|---|---|---|---|
| 1 | Перевести основную платформу на Codex | **`Кирилл 1-1.`** + пробел | union=0 → display_name-home |
| 2 | Перенести доработанный MSP Metabase… | **`Кирилл 1-1.`** + пробел | union=0 → display_name-home |
| 3 | Проверить наличие всех доступов | **`AI-аналитик.`** без пробела | eligible bind `ai_analitik` ∈ 14 |

Empty-warn на встрече нет.

---

## Что эта дельта **не** делает

- Не кладёт 1:1 в closed_list и не заводит `entities.<1on1>.task_slug`.
- Не меняет `_eligible_bind_slug` / `slug_to_canonical` / allowlist 14.
- Не пишет `task_slug` из MOFS (AC-009).
- Не зовёт picker на promote (AC-012 §29).
- Не патчит TaskRefresh / AnywhereContacts / `project_bind.py` / крон /
  окно / `last_synced_at` / `--recording-key` / `--oct`.
- Не ставит home на `kind=project` / `multisync` (out-of-scope picker;
  meeting-level `pfs.tag` в `render_row` как сейчас).
- Не редактирует `entities.json` (П.4 после impl).
- Не подменяет `[NEW-ENTITY]`.
