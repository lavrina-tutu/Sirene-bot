---
type: appendix
title: Бриф-исходник схемы entities.json v1.2 (бывший «мастер» EntitiesSchemaV12)
date: 2026-09-22
absorbed: 2026-09-29
status: absorbed
owner: EntityRegistry
canonical: TZ/EntityRegistry/EntityRegistry_TZ.md (секция «Схема v1.2», v0.4.0)
source: TZ/EntitiesSchemaV12/EntitiesSchemaV12_TZ.md
---

# Appendix — бриф-исходник схемы v1.2 (21–22.09.2026)

Этот файл — **не мастер-ТЗ**. Это сохранённый бриф-исходник (бывший
`TZ/EntitiesSchemaV12/EntitiesSchemaV12_TZ.md`, case CHANGE, status approved,
секционный брif-уровень). Канон схемы v1.2 с 29.09.2026 живёт в
`TZ/EntityRegistry/EntityRegistry_TZ.md` (инструмент манифеста `entity_registry`).

Решение архитектора `TZ:patch` t_e1c9acf8 / `DEV/entities-backfill`: мастер B,
не A. Обоснование — в секции «Владелец мастер-документа схемы» master-ТЗ
EntityRegistry v0.4.0. `emit-prompt --tool EntitiesSchemaV12` падает: ключа нет
в `EcosystemManifest.json` `tools{}`. Рабочий `--tool entity_registry`.

Ниже — исходный текст брифа 22.09.2026 без содержательной переписи (канон
требований после поглощения — секция v0.4.0 master-файла).

---

# Entities Schema v1.2 — related_pages / people / loop_channels + 404-алерт

- status: approved
- mode: one-pass
- case: CHANGE
- created: 2026-09-22
- decided_by: Sasha (brief 21-22.09.2026, архитектор — delegate_task отчёты)

## 1. Цель

Расширить схему entities.json (v1.1 → v1.2) и добавить алертинг 404 протокольных страниц.
Решения зафиксированы Сашей в брифе (22.09.2026):

- ОБЪЕДИНЯЕМ: отдельное поле root_confluence_id НЕ создаётся; корень проекта — запись в
  `related_pages` с `primary: true`.
- `completion_report_id` — НЕ делаем.
- `status`-гварды публикации — НЕ делаем (жёсткий запрет Саши, «так не делаем»).
- `start_date`/`end_date` — НЕ делаем.
- people — только логины, ФИО запрещены (ПДн).

## 2. Схема: добавить в `properties` записи сущности

```json
"related_pages": {
  "type": "array",
  "items": {
    "type": "object",
    "required": ["page_id", "role"],
    "properties": {
      "page_id": {"type": "string", "pattern": "^[0-9]+$"},
      "role": {"enum": ["charter", "brief", "tasks", "report", "other"]},
      "primary": {"type": "boolean"},
      "title": {"type": "string"}
    },
    "additionalProperties": false
  }
},
"people": {
  "type": "array",
  "items": {
    "type": "object",
    "required": ["login"],
    "properties": {
      "login": {"type": "string", "pattern": "^[a-z][a-z0-9._-]*$"},
      "role": {"enum": ["customer", "pm", "sponsor", "team", "other"]}
    },
    "additionalProperties": false
  }
},
"loop_channels": {
  "type": "array",
  "items": {"type": "string", "pattern": "^[a-z0-9_-]+$"},
  "uniqueItems": true
}
```

- `root_confluence_id` отдельным полем НЕ делать: корень = related_pages с `primary: true`
  (решение Саши 22.09, несмотря на возражение архитектора о «ровно одном root» —
  проверка «ровно одна primary» на валидаторе/кли, не на JSON Schema).
- `additionalProperties: false` в объектах people — осознанный ПДн-гвард.
- `charter.confluence_id` не трогать и не дублировать в related_pages.
- Инвариант (validator.py, optional): ровно одна `primary: true` среди related_pages;
  related_pages не дублирует pfs.page_id; запрет page_id 523032632/432316254/331125844.
- Bump `schema_version` 1.1 → 1.2 и обновить пин-тест `test_entities_registry.py:27`.

## 3. CLI (EntityRegistryCLI)

- SchemaIntrospector автоматически построит флаги. Учёт квирка `--related-pag`
  (эвристика endswith("es")) — задокументировать в references/flags-reference.md.
- Заполнение массивов объектов — через `edit <slug> related_pages --value-json '...'`.
- Проверить: `add`/`edit` не падают, `validate` проходит, `--allow-new-field` не нужен.

## 4. Backfill (по данным сессии 21.09.2026, Confluence pageId → role)

| slug | primary (корень) | related_pages (role, page_id) |
|---|---|---|
| trisigma | 480923430 | report 523010358 |
| ai_analitik | 480905784 | — |
| ml_platforma | 487934086 | — |
| metroteka | 418568780 | tasks 444141522 |
| ai_ready | 490149042 | tasks 499570832 |
| vestnik | 324382467 | tasks 519474299 |
| atribuciya | 347445612 | tasks 519474257; brief 449571537; tasks 487924720 (приёмка) |
| cu | 469658375 | tasks 519474213; report 480922695 (дипломные проекты) |
| devrel | 480930821 | tasks 519474160 |
| parsing | 439235729 | tasks 439235748; report 477048493 (ЖД завершён); report 446995783 (ЖД протоколы) |
| antibot | 410783702 | tasks 439235653; report 449567776; report 441304017 (результаты) |

Остальные ~36 сущностей — НЕ backfill (канбан-карточка t_4b7cc2ff).

## 5. 404-алерт (PFS + OFC)

- PFS `pipeline.py` (404-ветки get_page/update_page ~строки 239-244, 440-445): при
  action="error" из-за 404 → вызвать `~/.hermes/scripts/report_error.sh --tool
  ProtocolFromSummary` (ErrorBus → TG), текст «страница протоколов <page_id> 404 →
  route мёртв, entity <slug>».
- OFC `entity_export.py` (~130-141): not_found агрегировать за прогон → один вызов
  report_error.sh со списком page_id (не штучно).
- Без status-гвардов, без автопереходов — только алерт.

## 6. Тесты

- Пин-тест schema_version 1.2.
- Sample-сущность с новыми полями проходит validate (Draft-07).
- Негатив: people с полем `fio` — схема отвергает; related_pages с двумя primary — reject.

## 7. Границы

- Исполнитель НЕ пишет в entities.json/manifest/.env/jobs.json — данные вносит
  ORCH:shared-state (Сирень) после done.
- Существующие читатели (PFS/OFC/TaskRefresh/MOFS) не должны менять поведение на
  отсутствующих полях — проверено архитектором, `.get()`-доступ.

## Прогресс выполнения

- [x] Схема v1.2: три поля + валидатор primary
- [x] Пин-тест обновлён (schema_version 1.2)
- [x] Backfill 11 проектов (ORCH:shared-state, канбан-исполнитель не пишет entities.json)
- [x] 404-алерт PFS + OFC
- [x] rclone sync WorkVault (owncloud-sync.service, ExecMainStatus=0)
