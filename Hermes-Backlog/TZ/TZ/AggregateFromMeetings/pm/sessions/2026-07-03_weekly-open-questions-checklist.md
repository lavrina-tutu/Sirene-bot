---
type: weekly-checklist
scope: hermes-vm / WorkVault / AggregateFromMeetings + TZ-system
period: 2026-06-26 — 2026-07-03
created: 2026-07-03
author: cursor-agent
status: active
---

# Чек-лист открытых вопросов — неделя 26.06–03.07.2026

> Сводка по всей работе недели: что договорили и перенесли в ТЗ, что **не взяли в реализацию**, что **не договорили до конца**, что **заблокировано**.
> Источники: `pm/OPEN_QUESTIONS.md`, `pm/IMPLEMENTATION_QUEUE.md`, `pm/PM_DECISIONS_LOG.md`, `BUILD_CHECKLIST.md`, сессии 29.06–03.07, аудит 02.07, миграция TZ 03.07.

## Легенда статусов

| Статус | Значение |
|--------|----------|
| ✅ | Закрыто: в ТЗ / выполнено / решение PM зафиксировано |
| 🟡 | В ТЗ или решено на брифе, **код не начат** |
| 🔴 | Открыто, ответа PM нет или блокирует работу |
| ⚠️ | Частично / есть расхождение / нужна доработка документов |
| 📋 | Спроектировано, ждёт явной команды «берём в работу» |
| 👤 | Требует действия PM (ревью, список, вердикт) |

---

## 0. Главный итог недели

| Что сделали | Статус |
|-------------|--------|
| Фаза A — ТЗ AggregateFromMeetings (OQ-001…014, PM Notes Q1–Q6, Q-B1…Q-C3) | ✅ v1.8 в `Hermes-Backlog/TZ/AggregateFromMeetings/` |
| Бриф PM Notes + reconciler + stable-ID `^{slug3}{hex}` | ✅ PD-049…058 в ТЗ |
| Opus выведен из pipeline (Haiku-only) | ✅ в ТЗ; 🟡 в коде не реализовано |
| Инвентаризация WorkVault + cleanup + `WorkVault_backup` | ✅ 02.07 |
| Независимый аудит ТЗ (non-Anthropic) | ⚠️ 5 findings, remediation **не выполнен** |
| Единая система хранения ТЗ (`Hermes-Backlog/TZ/`) | ✅ миграция 03.07 (Wave 1–2) |
| **Фаза B — код AggregateFromMeetings** | 🔴 **не начата** — нет команды «начинай Фазу B» |

---

## 1. AggregateFromMeetings — открытые вопросы (OQ / Q-*)

### 1.1 Реестр OQ (`OPEN_QUESTIONS.md`)

| ID | Тема | Статус | Комментарий |
|----|------|--------|-------------|
| OQ-001…014 | Все вопросы брифа 29.06 | ✅ `in_tz` | Закрыты в MASTER-HANDOFF |
| OQ-A01 | LLM выбор (Haiku/Opus) | ⚠️ | В реестре `answered`, фактически superseded PD-028 (Opus out) — **обновить реестр** |
| OQ-A02 | G vs D граница | ⚠️ | В реестре `answered`, давно `in_tz` — **обновить реестр** |

### 1.2 Бриф 30.06 (Q-B / Q-C) — все закрыты в ТЗ

| ID | Тема | Статус |
|----|------|--------|
| Q-B1…Q-B5 | PM Notes CRUD, формат, ID | ✅ PD-053…058 |
| Q-B6 | Exchange Org Lookup (4 вопроса) | 🔴 **не ответены PM** — см. §3 |
| Q-B7 | Уставы Confluence для bootstrap | 👤 **операционно открыт** — нужен список URL по проектам (trisigma, ml-platforma — только 2) |
| Q-C1 | Маппинг секций среза → PM Notes | ✅ |
| Q-C2 | E/H labels tasks/decisions/risks | ✅ |
| Q-C3 | slug3 / short_id / login3 | ✅ People подтверждён 30.06 |

---

## 2. Разработано в ТЗ, не взято в реализацию (Фаза B)

> Очередь: `pm/IMPLEMENTATION_QUEUE.md`. Все пункты `[ ]` = **не начато**.

### 2.1 Фаза A — хвосты в документации

| ID | Что | Статус | Комментарий |
|----|-----|--------|-------------|
| IQ-A03 | Tasks-query + default +5 раб. дней | ⚠️ | +5 дней **уже в TZ_C/TZ_D**; очередь помечена «частично» — **синхронизировать IQ** |
| IQ-A06 | Golden compare критерии recall | ⚠️ | Описано в TZ_C; детализация отложена на Фазу C |

### 2.2 Фаза B — код (весь блок 📋 / 🟡)

| ID | Модуль | Статус | blocked_by |
|----|--------|--------|------------|
| IQ-B01 | ff_parser (Решения + Action items) | 📋 | — |
| IQ-B02 | D: decisions из summary | 📋 | B01 |
| IQ-B03 | D: action_items + AC + +5 дней | 📋 | B01 |
| IQ-B04 | D: timeline статический | 📋 | — |
| IQ-B05 | G: snapshot per meeting | 📋 | — |
| IQ-B06 | Кросс-проект → decision в источник | 📋 | — |
| IQ-B07 | Дедуп задач (stable-id), **MVP блокер H6** | 📋 | B12 |
| IQ-B08 | E: People sandbox | 📋 | B02 |
| IQ-B09 | H: Syncs sandbox | 📋 | B02 |
| IQ-B10 | C: Haiku-only единый проход | 📋 | B01 |
| **IQ-B10a** | **H3-rework: Opus↔Haiku таблица** | 🔴 **гейт-блокер Фазы B** | B10; файл `h3-rework-comparison.md` **не создан** |
| IQ-B11 | D: risks.md авто + inferred | 📋 | B10 |
| IQ-B12 | Tasks-query + stable-id в G | 📋 | B05 |
| IQ-B13 | D: blockers `[blocker]` | 📋 | B10 |
| IQ-B15 | Confluence устав = встреча №0 | 📋 | B10; **ждёт URL уставов (Q-B7)** |
| IQ-B16 | Идемпотентность FF / ручной rerun | 📋 | — |
| IQ-B17 | Exchange Org Lookup (bk-098) | 📋 | B01; мини-ТЗ draft, 4 открытых вопроса |
| IQ-B18 | `pm_notes_reconciler` (Шаг 1) | 📋 | B05, B12 |
| IQ-B19 | F: два шага pipeline | 📋 | B18 |

### 2.3 Фаза C — приёмка (весь блок 📋 / 👤)

| ID | Шаг | Статус |
|----|-----|--------|
| IQ-C01 | Golden compare ml-platforma | 📋 |
| IQ-C02 | Golden compare trisigma | 📋 |
| IQ-C03 | PM ревью 3–5 проектов → **GATE H6** | 👤 |
| IQ-C04 | Cleanup sandbox | 📋 |
| IQ-C05 | Sonnet: предложения закрытия задач → PM Notes | 📋 |
| IQ-C06 | Recall авто-рисков ml-platforma | 📋 |

---

## 3. Exchange Org Lookup — 4 открытых вопроса (Q-B6)

Мини-ТЗ: `Hermes-Backlog/TZ/ExchangeOrgLookup/ExchangeOrgLookup_TZ.md` (status: **draft**)

| # | Вопрос | Статус | Рекомендация Opus (не принята) |
|---|--------|--------|--------------------------------|
| 1 | Протокол GAL: EWS / Graph / LDAP? | 🔴 | MS Graph или LDAP |
| 2 | Частота батча | 🔴 | ночной cron |
| 3 | `ambiguous` — автоселект или дайджест? | 🔴 | всегда дайджест PM |
| 4 | `manager` из GAL → login? | 🔴 | best-effort |

**Блокирует:** IQ-B17 (не критичен для старта B01, но нужен до prod E-модуля).

---

## 4. HUMAN-GATES — что ждёт PM

| Gate | Тема | Статус | Действие PM |
|------|------|--------|-------------|
| **H3-rework** | Precision C на Haiku vs Opus | 🔴 переоткрыт | Вердикт после IQ-B10a (таблица сравнения) |
| **H4** | Ревью сигналов 15 проектов | 👤 | `Inbox/signals-review-2026-06-29/` — ревью не зафиксировано |
| **H5b** | Ревью `classification_memory.json` | 👤 | После IQ-B01, человекочитаемый формат |
| **H6** | Разрешение писать в боевой WorkVault | 👤 | После IQ-C01/C02/C03 + golden compare |
| — | **Команда «начинай Фазу B»** | 🔴 | Явная команда не дана (integrity report §7) |
| — | **Ревью комплекта ТЗ v1.8 в Hermes** | 👤 | По архиву `tz-final-qc-20260630-1500.tgz` |
| Q-B7 | URL уставов Confluence | 👤 | Список проектов с уставом vs aliases-only |

---

## 5. Аудит ТЗ 02.07 — findings без remediation

Файл: `pm/sessions/2026-07-02_tz-audit-findings-non-anthropic.md` (status: **findings-detected**)

| # | Severity | Тема | Статус |
|---|----------|------|--------|
| 1 | HIGH | TZ_E: `#N` vs `^{login3}{hex}` в одном модуле | ⚠️ **не исправлено** |
| 2 | HIGH | PD-051 vs канон: `<!-- pm: -->` vs `### PM Notes (...)` | ⚠️ **не исправлено** |
| 3 | MEDIUM | short_id: «из slug» vs «PM задаёт явно» | ⚠️ **не исправлено** |
| 4 | MEDIUM | People: смешение short_id/login3 в формулировке TZ_G | ⚠️ **не исправлено** |
| 5 | LOW | Legacy-синтаксис в пояснительных секциях | ⚠️ **не исправлено** |

> Запрос на скрипт remediation + новый архив — **не выполнен**.

---

## 6. Миграция TZ-storage (03.07) — §14 открытые вопросы

ТЗ: `Hermes-Backlog/TZ/TZ-Workflow/TZ-storage-system.md` §14. Миграция **запущена** до решений по §14.

| # | Вопрос | Статус после 03.07 | Комментарий |
|---|--------|-------------------|-------------|
| 1 | MoveFromFF: переименовать `*_TZ_v2.1.md` → `MoveFromFF_TZ.md`? | ✅ | Сделано при миграции |
| 2 | Кириллица в `_Done/` архиве | ⚠️ | Перенесено как есть в backup; формально не подтверждено PM |
| 3 | README в USERTOOLS после переноса ТЗ | ⚠️ | Не проверено для всех инструментов |
| 4 | Когда архивировать ТЗ инструмента | ✅ | Зафиксировано в `_TZ-WORKFLOW-RULES.md` |
| 5 | bash-скрипт vs текстовые команды | ✅ | `archiving.md`, без скрипта |
| 6 | Имя файла TZ-storage-system | ✅ | `TZ/TZ-Workflow/TZ-storage-system.md` |
| 7 | apps-preview-summary → master или _misc | ✅ | Влито в MoveFromFF master (inventory) |
| 8 | Обновить `hermes-feature` skill | ⚠️ | Частично patched 03.07; полная Фаза 2A — проверить |

### Техдолг миграции

| Тема | Статус |
|------|--------|
| `_Backup-Rules.md` vs `_TZ-WORKFLOW-RULES.md` — дублирование | ⚠️ |
| Старые пути в `WorkVault_backup/Tools/...` vs новая схема `Hermes-Backlog/TZ/` | ⚠️ |
| Smoke-test «создай TestTool_TZ» | 👤 не зафиксирован |
| `MAIN_TZ_INVENTORY` колонка «Архив» — смешанные пути | ⚠️ |

---

## 7. WorkVault cleanup (02.07)

| Действие | Статус |
|----------|--------|
| Удалён мусор (8 элементов) | ✅ |
| Перенос 21 файла в `WorkVault_backup/` | ✅ |
| `_Backup-Rules.md` | ⚠️ частично устарел (см. §6) |
| `2026-07-02_WORKVAULT_INVENTORY.md` → `MAIN_WORKVAULT_INVENTORY.md` | ✅ 03.07 |

---

## 8. Согласование ≠ старт работы (напоминание)

| Решение | Статус реализации |
|---------|-------------------|
| ТЗ v1.8 согласовано на брифах 29–30.06 | ✅ документ |
| PM Notes / reconciler / stable-ID | 🟡 только ТЗ |
| «Agreement ≠ start of work» (`_TZ-WORKFLOW-RULES`) | 🔴 код/migration не начаты |

---

## 9. Приоритетный список «что решить дальше»

1. 👤 **Команда «начинай Фазу B»** (или явный отказ/пауза)
2. 👤 **Q-B7** — список уставов Confluence по проектам
3. 🔴 **Q-B6** — 4 вопроса Exchange Org Lookup (можно «на усмотрение реализатора»)
4. ⚠️ **Remediation аудита 02.07** (5 findings) — до или параллельно с B10a
5. 🔴 **H3-rework (IQ-B10a)** — блокер внутри Фазы B после старта B10
6. 👤 **GATE H4, H5b, H6** — ревью PM по мере готовности кода
7. ⚠️ Синхронизировать `OPEN_QUESTIONS.md`, `IMPLEMENTATION_QUEUE.md` (OQ-A*, IQ-A03)

---

## 10. Файлы-источники этой сводки

| Файл | Путь на ВМ |
|------|------------|
| Этот чек-лист | `Hermes-Backlog/TZ/AggregateFromMeetings/pm/sessions/2026-07-03_weekly-open-questions-checklist.md` |
| Очередь реализации | `.../pm/IMPLEMENTATION_QUEUE.md` |
| Открытые вопросы | `.../pm/OPEN_QUESTIONS.md` |
| Решения PM | `.../pm/PM_DECISIONS_LOG.md` |
| Аудит findings | `.../pm/sessions/2026-07-02_tz-audit-findings-non-anthropic.md` |
| Integrity report | `.../pm/sessions/2026-06-30_cursor-tz-integrity-report.md` |
| TZ workflow | `Hermes-Backlog/TZ/_TZ-WORKFLOW-RULES.md` |
| Vault inventory | `WorkVault/MAIN_WORKVAULT_INVENTORY.md` |
