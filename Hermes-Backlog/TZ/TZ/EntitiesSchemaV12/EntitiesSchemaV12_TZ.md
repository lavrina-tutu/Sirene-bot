---
tool: EntitiesSchemaV12
status: superseded
version: 1.2
date: 2026-09-29
superseded-by: TZ/EntityRegistry/EntityRegistry_TZ.md
appendix: TZ/EntityRegistry/appendix_entities-schema-v12_brief_20260922.md
---

# EntitiesSchemaV12 — не мастер

Этот файл **больше не является мастер-ТЗ**. Самостоятельного инструмента
`EntitiesSchemaV12` в `EcosystemManifest.json` `tools{}` нет и не будет:
гейта `emit-prompt --tool EntitiesSchemaV12` нет (`[FAIL] инструмент не найден
в манифесте`).

**Канон схемы `entities.json` v1.2** — `TZ/EntityRegistry/EntityRegistry_TZ.md`
(манифестный ключ `entity_registry`, `tz_ref` указывает сюда). Бриф-исходник
21–22.09.2026 сохранён как
`TZ/EntityRegistry/appendix_entities-schema-v12_brief_20260922.md`.

Решение: `TZ:patch` t_e1c9acf8, цепочка `DEV/entities-backfill`, 29.09.2026.
Каталог оставлен как заглушка, чтобы `SKIP_TZ_DIRS` (EcosystemIntegration §9.2)
не ломал `--check-drift`, пока `ORCH:shared-state` не снимет skip. Не
регистрировать `EntitiesSchemaV12` в `tools{}`.
