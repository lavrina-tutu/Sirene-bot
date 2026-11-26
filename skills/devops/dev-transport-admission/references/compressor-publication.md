# Публикация выжимки компрессора и write_scope

Применимо при ведении поезда, когда compressor-фаза (TZ:compress/HF:compress) выполнена агентом (codex) и фазу надо закрыть. Норма — Б56/Б13.2 master-ТЗ. Запись агентом `extract.md` ещё не публикация и не основание complete.

## Интерпретатор pipeline CLI

Запускать pipeline CLI через venv-python: `/home/tkachenkoav/hermes-agent/.venv/bin/python3 -m pipeline.cli …`. Системный `python3` (3.9) без yaml/jsonschema падает на импорте `pipeline_context` → `ModuleNotFoundError`; в `execute_code`-ядре этих модулей тоже нет. Сверить интерпретатор, прежде чем повторять прогон; не считать это багом кода.

## Резолв модели компрессора

В YAML `tools.dev_workflow.roles.compressor` задать конкретную модель + `effort` (напр. `gpt-6-luna`/`medium`). Пустой/null/marker `hermes-native` уводит на absent `HERMES_COMPRESSOR_*` env → `AuthenticationError`/`empty-result`, codex-ветка не включается. Codex-резолв требует константной модели.

## write_scope и `_in_scope`

`_in_scope` матчит вложенную запись ТОЛЬКО если элемент write_scope оканчивается на `/`. Каталог в write_scope **без трэйл-слеш** не допускает свои подфайлы → легальная запись режется как `output outside write_scope`. Писать каталоги со слешём (`…/`) ПЛЮС точные пути канонов (`extract.md`, `extract-N.md`, `TZ-patch.md`, файл master-ТЗ). Это главная ложная причина `outside write_scope`; не судить «файл написан» пока G2 не принял.

## Принцип: публикация — системный no-agent шаг, не обязанность слабой модели

Требование Саши (жёсткое): **не требовать от компрессора невозможное — это всегда более слабая модель**. Компрессор-LLM отвечает ТОЛЬКО за текст выжимки; identity, хеши, разбор частей, coverage, публикацию, result/receipt и proof несёт Python-код системы (это no-agent шаг, без модели). Модель не должна воспроизводить даже `packet_id`. Если вызов требует от компрессора самому вести приёмку/хэши — это дефект архитектуры вызова, а не слабость модели; чинить надо вызов (перенос публикации в общую финализацию invoke_role до result/receipt), а не «просить модель точнее».

Живой признак неполной публикации: `invoke-role` компрессора вернул rc=0 и `extract.md` реально переписан, НО в `proof` фазы есть `context_prepare`/`context_result` без `extract_production` → `complete-phase` честно падает `compressor publication/prepare/result identity mismatch` (`pipeline_context.compressor_metadata`). Это не баг приёмки: приёмка работает как надо и lock этого хочет. Диагностировать по `proof.extract_production`, а НЕ по факту существования `extract.md`.

Инвариант: **`invoke-role rc=0` для компрессора означает наличие валидной публикации текущего prepare и согласованного result/receipt.** Существование `extract.md` этого НЕ доказывает; успешная публикация доказывается только записью `extract_production` через `publish_validated_extract`.

Целевой контракт цепочки: `accepted packet → prepare → привязанный request → ответ → validated publication → result+receipt → complete-phase: metadata+done → следующий packet`. Identity на всей цепочке переносит Python.

## Закрытие compressor-фазы

Compressor закрывает фазу только через `publish_validated_extract`: она требует `extract_production` в proof и **дословного покрытия** всех идентификаторов master-ТЗ (каждый `AC-###`, `IAC-##` и все семейства вроде AC-PW/AC-RP/COD-C) в совокупности частей. Оркестратор после выхода агента:
1. дополняет выжимку недостающими маркерами;
2. бьёт на части ≤5Ki, каждой ставит заголовок `## Часть i/N` (multipart — обязателен при >1 части);
3. зовёт `publish_validated_extract` с `packet_id`/`prepare_identity` из accepted context;
4. ПЕРЕСЧИТЫВАЕТ `output_snapshot` по принятому пакету и обновляет `proof.context_result.outputs` — публикация перезаписывает `extract.md` как алиас части 1, иначе G2 даёт `result output changed` на complete.

Никогда не править старый packet/state в обход G2; пересчёт снапшотом — сверка после штатной публикации, не подделка результата.

## Возврат REV REQUEST-CHANGES (rework, не recover)

REV:tz/RV→REQUEST-CHANGES возвращается адресным rework, не recover. В контракте `brief.md` (`handoff-contract`):
- `inputs.TZ:patch` получает `purpose: rework-request`, `phase: REV:tz`, путь к `REV-tz.md`;
- write_scope `TZ:patch` добавляет каталог скилла и master-ТЗ (без этого архитектор не вправе писать master, а Б13.2 требует внесения требований в master тем же ходом `TZ:patch`);
- `outputs.TZ:patch` включает и `TZ-patch.md` (canonical), и master (`kind: master`).
Затем `next` применяет rewind: handoff.kind=rework, st.phase=TZ:patch. REV complete — только по APPROVE в `REV-*.md`, не по `REQUEST-CHANGES`.

Полезный замер для REV: полное покрытие (0 missing по всем семействам AC) проверяется пересчётом `coverage_pass` по всем `extract*.md` перед повторной ревизией — это закрывает R2 ревизора.
