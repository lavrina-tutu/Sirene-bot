# Модуль 0 «Единый конфиг экосистемы» — зафиксированная постановка

**Дата:** 2026-09-30
**Статус:** бриф закрыт, постановка зафиксирована (архитектор cursor-grok-4.6-high, сессия 91318875-52a2-4d09-8dca-7267bff56169). Готово к каркасу ТЗ.
**Эпискус контекст:** инфраструктурный эпик «Единый конфиг → обработка самари из FF». Модуль 0 = единый конфиг; Модуль 1 (FF-самаризатор + переключаемость MOFS/PFS) = блок 1, сохранён как IDEA `t_609e8869` в triage, берём после модуля 0.

## Решения Саши
1. **Вариант A (OverlayConfig):** топ-уровень `config`-указатель в `EcosystemManifest.schema.json` + отдельный `EcosystemConfig.yaml` (значения) + `EcosystemConfig.schema.json` + лоадер `usertools_config.py`.
2. **Legacy выпиливается полностью** после эксплуатационной приёмки (уйти от несистемного хранения; старые `.env`/конфиги/ссылки удалить, остаться только на едином).
3. **Подтверждение приёмки — Вариант 1:** только после ЯВНОЙ реплики Саши по каждому инструменту. Для волны 3 (без своего конфиг-файла) допустима одна пакетная реплика на список чистых регистраций.

## Канон (артефакты)
| Артефакт | Роль |
|---|---|
| `EcosystemManifest.schema.json` → required top-level `config` | Указатель + реестр миграции/отката, НЕ payload значений. Бамп 0.5.0 → 0.6.0 |
| `~/WorkVault/Registries/EcosystemConfig.yaml` | SoT несекретных значений (`shared:` + `tools.<key>:`) |
| `~/WorkVault/Registries/EcosystemConfig.schema.json` | Схема YAML |
| `~/.hermes/lib/usertools_config.py` | Единый лоадер (расширение `~/.hermes/lib/usertools_env.py`, новый USERTOOL не нужен) |
| `~/.config/hermes/.env` | SoT секретов |
| `~/.hermes/config.yaml` | SoT LLM (`model.default`/`provider`/`custom_providers`); per-tool override — только секция YAML |

В манифесте у `config.tools.<key>`: `enabled`, `migration_status`, `overlay` (только dual-read), `rollback_snapshot`.
Digest: путь конфига + счётчики статусов, НЕ значения и НЕ секреты.
Владелец индекса — EcosystemIntegration + ORCH:shared-state. Новый инструмент в tools{} не заводится.

## Слои (не смешивать)
1. Индекс экосистемы — манифест.
2. Несекретный runtime — `EcosystemConfig.yaml`.
3. Секреты — shared `.env`.
4. LLM — Hermes `config.yaml`.
5. Бизнес-правила инструмента (`loop_rules.yaml`, `contract_rules.yaml`, `translit.yaml`) — НЕ инфраструктурный конфиг, в единый YAML не переезжают, волной удаления legacy не трогаются.

`config.py` после приёмки может остаться тонкой оболочкой (типизированный доступ, сборка ROUTES из entities.json). Литералы путей/моделей/токенов/дублей env — удаляются. Пустой per-tool `.env` удаляется целиком; уникальные секреты сначала переезжают в shared `.env`.

## Каскад чтения (dual-read, волны 0–3, временный; побеждает более высокий)
1. Process env (вкл. аварийный `USERTOOLS_CONFIG_MODE=legacy` только для этого процесса/инструмента)
2. `~/USERTOOLS/<Tool>/config.overlay.yaml` — только пока `migration_status=dual_read`
3. `tools.<key>` в `EcosystemConfig.yaml`
4. `shared:`
5. LLM из Hermes, затем optional `tools.<key>.llm`
6. Секреты из shared `.env`
7. Legacy: старый `.env` / литералы `config.py`

После приёмки инструмента — пункты 2 и 7 для него запрещены. После экосистемной приёмки — ветки 2 и 7 удаляются из лоадера (нет ключа → fail loud, не «подхватить старое»).

## Откат (per-tool требование)
| Фаза | Как вернуть один инструмент |
|---|---|
| Dual-read | `USERTOOLS_CONFIG_MODE=legacy` или overlay на старые файлы; соседи не трогать |
| После per-tool приёмки | Старых файлов нет. Restore секции YAML из `~/.hermes/_Archives/ecosystem-config/<tool>/<timestamp>.yaml` + `rollback_snapshot`. `enabled:false` — стоп без отката данных |
| После экосистемной чистки | То же: архив YAML / правка единого; веток legacy в коде нет |

## Факт эксплуатационной приёмки (per-tool → `migration_status: accepted`)
1. **Источник ключей:** `usertools_config explain <tool>` — каждый несекретный ключ `source=ecosystem_config`, секрет `source=shared_env`, ноль `source=legacy`/`source=overlay`.
2. **Реальный цикл, не dry-run:** крон ≥3 подряд успешных тика в обычном окне ИЛИ один полный рабочий день (что раньше); по запросу ≥1 реальный вызов Саши/скилла с ожидаемым результатом; волна 3 — explain без недостающих ключей + один реальный вызов (если есть боевой вход).
3. **ErrorBus:** в окне приёмки нет НОВЫХ событий этого tool про конфиг/env/missing key/YAML parse.
4. **Фиксация:** `ORCH:shared-state` после того, как Саша по пакету улик подтверждает перенос (ЯВНО, Вариант 1). Без фиксации legacy не удалять.

Удаление файлов — отдельный императив на уже `accepted` инструмент («работает, удаляй legacy»).

**Экосистема «единый конфиг единственный»:** все active/draft/paused tools = `migration_status: unified_only`; drift-check без дублей путей; из лоадера вырезаны dual-read/legacy/overlay-к-старым; digest показывает unified_only.

## Волны и момент удаления legacy
**Принял инструмент → сразу выпил его legacy → в конце выпил механизм fallback из лоадера.**

- **Волна 0** — каркас: схема `config`, пустой/shared YAML, схема YAML, лоадер с dual-read + `explain` + `migration_status: not_started`. Старые файлы на месте.
- **Волна 1** — пилот на реальной работе: FirefliesAutojoin, MoveFromFF, ConfluenceSync, ProtocolFromSummary. Dual-read, YAML побеждает. После приёмки каждого пилота: accepted → удалить его дубли в .env/литералы в его config.py/его overlay → перенести его уникальные секреты в shared .env → unified_only.
- **Волна 2** — остальные с `.env`/`config.py`. Цикл по одному; удаление строго per-tool после accepted.
- **Волна 3** — инструменты без своего конфиг-файла: регистрация в YAML (часто только `enabled` + конвенция logs). Приёмка по правилам волны 3.
- **Волна 4** — единая чистка (когда последний active/draft/paused = accepted/unified_only): вырезать legacy/overlay/`USERTOOLS_CONFIG_MODE` из лоадера; снести осиротевшие пустые `.env` и мёртвые ссылки; `--check-drift` «второй источник = 0»; чеклист tz-workflow/hermes-feature «новый ключ только в YAML+схеме; литерал/new `.env` = дефект».

Итог после волны 4: восстановить «как в июне» старыми `.env` нельзя — только архив YAML и бэкап `_Archives`.

## Будущий FF-самаризатор (Модуль 1)
`get_llm("ff_summarizer")` из лоадера: default = Hermes (config.yaml), override только в `tools.ff_summarizer.llm` или env. См. IDEA `t_609e8869`.

## Инварианты разработки (с волны 0)
Любой новый/дорабатываемый инструмент читает лоадер, не плодит `.env`, не пишет пути литералом. Dual-read — только для ещё не принятых старых. После `unified_only` возврат литералов = регресс.