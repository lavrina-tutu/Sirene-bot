

# Material moved from MOFS SKILL.md

> История исходника (даты указаны внутри), не текущая инструкция; актуальные условия — в SKILL.md.

## Текущий статус (22.07.2026)

- **Версия кода:** v1.0.0, 186/186 тестов ✅ (MOFS v0.9.0 + LLM-фолбэк + авто-rematch)
- **ТЗ:** `~/WorkVault/Hermes-Backlog/TZ/MarkObjectsFromSummary/MarkObjectsFromSummary_TZ.md` v0.9.0; приложение v1.0.0: `MarkObjectsFromSummary_v100_TZ.md`
- **entities.json:** `~/WorkVault/Registries/entities.json` (~44 сущности: проекты/1-1/синки + 13 tools + adm/okr/sr/vestnik/atribuciya/antibot/dayana_1on1/alfa/adm и др. добавлены 22.07)
- **Реестр:** `~/USERTOOLS/AnywhereContacts/_mark_objects_registry.json` (**не** в папке MarkObjectsFromSummary!); `mofs_unmatched.md` → `~/WorkVault/Registries/mofs_unmatched.md`
- **Архив:** 575 встреч, 573/575 с projects, contacts backfill S1+S2 468/514 ✅ (S3 не потребовался)
- **MofsIndex:** v0.4.0, 575 встреч, 72 MB, `~/USERTOOLS/MofsIndex/state/index.sqlite`
- **Кроны:**
  - `mofs_run_cron` (job_id: aeeccba37e4a) — `16 8-19 * * 1-5`, no_agent, deliver=local. Молчит при processed=0, ⚠️ при unmatched_count>0.
  - `mofs_index_rebuild` (job_id: 7e013cd5c6f9) — `0 23 * * *`, no_agent, deliver=local. Ежедневный full-rebuild как страховка.
  - Цепочка: MoveFromFF XX:05 → PFS-batch XX:10 → PFS-notify XX:15 → MOFS XX:16.
  - **Ошибка крона MOFS → канбан, не самому (21.09.2026).** При ошибке `mofs_run_cron` (job aeeccba37e4a) или `mofs_index_rebuild` (job 7e013cd5c6f9) НЕ чинить самому и НЕ звать архитектора напрямую через `agent -p`. Постановка на канбан: `BUG:diagnose` (root cause + план П.1…П.N) → `GATE:diagnose-review` → `HF:impl`/`HF:test` (по hermes-feature Блок 6В). План починки — `_fix_plan_YYYYMMDD.md` рядом с инструментом (`~/USERTOOLS/MarkObjectsFromSummary/`). Локальный обход средствами скилла (rematch/entity-registry) — только как одношаговый ответ, не как реализация фикса кода `pipeline.py`. Прецедент: NameError parse_rooms 19.09.2026 — починено через BUG:diagnose-граф, не напрямую.

**LLM-конфиг (MOFS v0.10.1):** источник = `~/.hermes/config.yaml` (`model.default` + `model.provider` + `custom_providers`); OpenAI-совместимый клиент к `llm-gateway.tutu.ru`; env-override `MOFS_LLM_MODEL` / `_BASE_URL` / `_API_KEY` / `_ROUTING_PROVIDER` (default) / `_REASONING_EFFORT` (high); CLI `--llm-model` (только `backfill-contacts`, перекрывает только модель); last-resort `LLM_FALLBACK_MODEL` / `LLM_FALLBACK_BASE_URL` / `LLM_FALLBACK_PROVIDER`. `ANTHROPIC_API_KEY` не читается; нет ключа → warning → skip (fail-soft). Смена модели — правка `config.yaml`, не код.

## date: во frontmatter (реализовано 21.07.2026)

`date:` проставляется автоматически из имени файла при каждом `run`/`rematch`.
Идемпотентно — не перезаписывает если поле уже есть.

```python
# pipeline.py — в process_meeting после merge корзин
if not fm.get("date"):
    m_date = _FILE_DATE_RE.match(summary_path.name)
    if m_date:
        fm["date"] = m_date.group(1)
```

## Связь summary ↔ transcript

Детерминированная — по имени файла, суффикс меняется:
```
2026-07-08 11-05-00 Кирилл 1-1 - summary.md
2026-07-08 11-05-00 Кирилл 1-1 - transcript.md
```
Хранить ссылку в frontmatter не нужно — вычисляется на лету заменой суффикса.

## Зафиксированный план (Саша, 21.07.2026)

| Этап | Задачи | Статус |
|---|---|---|
| **1. Инфраструктура** | `date:` в MOFS ✅ → `mofs index` (SQLite+FTS5) ✅ | ✅ Готов |
| **2. Июль** | rematch --all июль (contacts + date) | ✅ Готов (61 встреча) |
| **3. Поиск** | обновить `workvault-rag` → три режима + индекс | ✅ Готов (v2.2.0) |
| **4. Проверка Саши** | смотрит результаты в Obsidian + поиск из TG → корректировки | ✅ Пройдена (22.07.2026) |
| **5. Архив** | backfill-contacts + rematch tools по архиву | ✅ Готов (tools 575 встреч, contacts 468/514) |
| **6. Крон** | ежечасный `mofs run --mode=cron` XX:16 пн-пт | ✅ Создан (job: mofs_run_cron, `16 8-19 * * 1-5`) |

**ВАЖНО:** не ставить крон без явного «ставь» от Саши (только после этапа 4).

## workvault-rag — архитектура поиска (решение 21.07.2026)

Единый скилл `workvault-rag` покрывает три режима:
- **Поиск встреч** — SQL к `mofs index` (SQLite+FTS5), <5мс
- **Детали встречи** — читает summary.md конкретной встречи
- **Цитаты из транскрипта** — читает transcript.md, отвечает через LLM

**Два отдельных инструмента НЕ создаём** — всё в одном `workvault-rag`.
Ripgrep (вариант 2) при наличии SQLite+FTS5 не нужен — медленнее на порядок.

## MOFS v1.0.0 — реализованные решения (22.07.2026) ✅

| Решение | Статус | Детали |
|---|---|---|
| LLM-фолбэк при projects=[] | ✅ | LLM из `~/.hermes/config.yaml` при `entity_hits==[]`, threshold=0.90; last-resort `LLM_FALLBACK_*` |
| Low-confidence очередь | ✅ | `mofs_unmatched.md` автоматически, бриф по запросу |
| Убрать дубль reindex из bash | ✅ | Hook в pipeline достаточен; отдельный крон `mofs_index_rebuild` 23:00 |
| Частота MOFS крона | ✅ | Оставить ежечасно XX:16 |
| Авто-rematch по хэшу entities.json | ✅ | SHA-256 8 hex; при изменении → полный rematch в том же прогоне |
| Порог confidence | ✅ | 0.90 |
| TG-уведомление при unmatched | ✅ | «⚠️ MOFS: N встреч без проекта» в крон-выводе |

**Бэклог:** создать скилл + крон для разбора `mofs_unmatched.md` — по всем типам сущностей, сортировка по частоте встречаемости (в `todo`).

