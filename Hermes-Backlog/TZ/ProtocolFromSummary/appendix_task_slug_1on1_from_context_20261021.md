---
tool: ProtocolFromSummary
kind: appendix
topic: task_slug_1on1_from_context
date: 2026-10-21
status: TZ:patch
package: pfs-slug-1on1-iz-konteksta-vstrechi
master: ProtocolFromSummary_TZ.md §39 (v1.34.0)
---

# Appendix: слаг 1:1 из контекста задачи, обязательный ADM (21.10.2026)

Справочник к **§39** master-ТЗ. SoT норм — §39. `[NEW-ENTITY]` **нет**.

Канон решения Саши: `Hermes-Backlog/dev/pfs-slug-1on1-iz-konteksta-vstrechi/sasha_slugi_decision_20261021.md`.
Diagnose: `_fix_plan_20261021_slugs.md`. Указатель фазы: `dev/pfs-slug-1on1-iz-konteksta-vstrechi/TZ-patch.md`.

Код / `entities.json` — **не** этот файл.

---

## Что меняется одним предложением

У in-scope задачи **всегда** есть слаг из `{AI-аналитик, Trisigma, Парсинг, АДМ}`, выбранный LLM/union **по контексту этой задачи** (§34). Имя встречи / сущности 1:1 / мультисинка — не слаг. §38 meeting-home **отменён**.

---

## Цитаты до / после

### Решение Саши (дословно, вечер 21.10)

> у задачи не может не быть слага
> Встреча 1:1 и мультисинки не могут являться слагами
> Сейчас слаги возможны для проектов: AI-аналитик, Trisigma, Парсинг.
> Всё остальное, скорее всего, административная задача → слаг ADM.

### §34 (живёт) — норматив сигнала

Источник uniqueness: `assignee ∪ task.text ∪ discussion ∪ eligible bind`.
**Не** источники: `meeting_name`, средняя тема 1-1, notes, участники.

### §38 (superseded) — что снимаем

Union=0 → `{display_name}.` («Кирилл 1-1. ») с пробелом; home в known prefixes skip; skip registry всё равно клеит home.

### §39 (этот пакет)

| Было (§38 / diagnose as-is) | Стало |
|---|---|
| home = имя сущности | запрещено |
| union=0 → home или as-is | union=0 → **`АДМ.`** |
| union≥2 → as-is | union≥2 среди 4 → **`АДМ.`** |
| LLM выбирает из 14 | LLM выбирает из **4** (overlay, реестр 14 не трогать) |
| «нет слага» законный fail-soft | в проде незаконно |
| home в skip → republish липкий | 1:1-префикс **strip**, задача в batch |

---

## Overlay vs closed_list 14

`entities.json` `kind=project` ∧ `task_slug` = 14 (канон §31). Среди них уже есть:

| slug | task_slug |
|---|---|
| `ai_analitik` | `AI-аналитик.` |
| `trisigma` | `Trisigma.` |
| `parsing` | `Парсинг.` |
| `adm` | `АДМ.` |

Пикер **не** читает остальные 10 как кандидатов **нового** слага. Исторический префикс из 10 на republish **не** стирается (AC-004).

---

## Эталон 21.10 после лечения

Встреча `2026-10-21 07-36-08 Кирилл 1-1`, якорь `pfsrow-b391f7f8daa6`.

| # | После picker | Почему |
|---|---|---|
| 1 Codex | `АДМ.Перевести…` (empty LLM / нет входа в тройку) | не 1:1-home; Codex ∉ тройке |
| 2 Metabase | `АДМ.Перенести…` | то же |
| 3 доступы | `AI-аналитик.Проверить…` | eligible bind `ai_analitik` ∈ 4 |

---

## Априор (дополнение Саши, второй проход TZ:patch)

Саша: проставить вероятности в таблице entities **или** лучший вариант архитектора.

**Вердикт: изменено.** Частотный хинт (AI-аналитик среди тройки; ADM как fallback) — в overlay пикера (`pick_hint`), не в `entities.json`. Числовых P() нет. Явный проект в тексте сильнее хинта; пустой/конфликтный union → ADM, хинт туда не входит. Нормы 1–9 §39 не откатываются.

---

## Границы

Не менять: `entities.json` (в т.ч. не добавлять `probability`/`pick_prior`), MOFS, TR, pipeline/route/storage_xml, скилл Pitfall 17, allowlist 14, `entities.<1on1>.task_slug`.
