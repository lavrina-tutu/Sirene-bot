# Образец конформ-аудита — OFC (26.08.2026)

Конкретный разбор, подтвердивший, что инструмент «draft» уже полностью реализован. Использовать как шаблон чек-листа для нового инструмента.

## Ситуация
ТЗ `TZ/ObsidianFromConfluence/ObsidianFromConfluence_TZ.md` — `draft`/«ждёт берем в работу» в `MAIN_TZ_INVENTORY.md`. Саша: «делаем». Архитектор при планировании проверил диск и нашёл полную реализацию + активный крон.

## Что нашлось (диск)
| Компонент ТЗ | Файл | Статус |
|---|---|---|
| Экспортёр (генерализация obsidian_export.py) | `~/USERTOOLS/ProtocolFromSummary/protocolfromsummary/obsidian_export.py` | есть (functions `iterate_all_rows`, `extract_content_cell`, `export_entity_protocol_to_markdown`) |
| Writer | `entity_writer.py::write_entity_protocol` | есть (idempotent: mkdir + tmp + os.replace) |
| Оркестратор | `entity_export.py::sync_entity_protocol`, `list_project_slugs` | есть |
| CLI | `scripts/ofc_sync.py` | есть |
| Обёртка+крон | `~/.hermes/scripts/ofc_sync.sh` + `jobs.json` job `bf52e6985523` | активен (`*/30 8-23 * * 1-5`, no_agent, будни 8-23) |
| МofsIndex doc_type='protocol' | `MofsIndex/mofs_index/{protocol_indexer,db,hooks,query}.py` | есть |
| Поиск с подписью слоя | скилл `workvault-rag/SKILL.md` | есть (строки 48/64/147) |
| Тесты | `tests/test_entity_export.py` + MofsIndex tests | есть |

## Реальные пробелы (gap), найденные аудитом
1. **Мониторинг размера** storage страницы (>5MB) не реализован в OFC-направлении (GET, в отличие от PFS PUT) — конвертер/файл могут вырасти без предупреждения.
2. **`MAIN_TZ_INVENTORY.md` рассинхронизирован**: `draft` при проде — обновить после решения Саши.
3. **Покрытие данных**: из 17 `kind=project` только 8 имеют `pfs.page_id`; остальные 9 не получат `protocol.md` (тихое ограничение v0.1).
4. Дубль `page_id 490170597` (trisigma/ab_platforma) — поведение «пишем обоим содержимое» реализовано и протестировано, соответствует ТЗ.

## Cursor-промпт (структура, переиспользуемая)
Промпт архитектору аудита содержал:
- контекст (инструмент, статус в реестре vs найденная реальность);
- полный текст ТЗ (СОКРАЩЁННЫЙ до ключевых пунктов/секций, чтобы не жечь токены);
- факты на диске (пути, проверены — «не перепроверяй»);
- чек-лист по секциям ТЗ + отдельный блок «Интеграция с ErrorBus» (правило каналов, instrumentation_registry, потеря стderr в no_agent, двойная доставка);
- жёсткое «ТОЛЬКО read-only, без side-effect»;
- формат отчёта.

## Питфоллы подтверждённые
- Реестр отстаёт от диска — всегда сверять код/крон, не верить статусу.
- `read_file` на очень длинных строках → ложный «Binary file»; читать через `open(f, encoding='utf-8').read()`.