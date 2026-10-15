# version-handoff — OverlayConfig волна 0 (2026-10-01)

Граф: `DEV/eco-config` (Единый конфиг экосистемы, модуль 0)
Карточка плана: `t_e315e706` (HF:plan) · фаза handoff: `HF:docs-handoff` `t_a917e91f`
Исполнитель: composer-2.5 (код/тесты реализованы в `HF:impl`/`HF:test`; здесь — docs + фиксация версий)

## Скоуп волны 0

Каркас OverlayConfig: top-level `config` в схеме манифеста, `EcosystemConfig.yaml` + `EcosystemConfig.schema.json`, лоадер `~/.hermes/lib/usertools_config.py` (dual-read/`explain`), `render_manifest.py --digest` показывает конфиг, все 46 ключей `tools{}` → `migration_status: not_started`. Код, конфиг и лоадер — `HF:impl`/`HF:test` (22 pytest passed на `test_usertools_config.py` + `test_render_manifest.py`). IAC-07 (docs version-bump + пункт про конфиг-ключ в скиллах) — в этом же пакете.

**Вне скоупа волны 0:** живой `EcosystemManifest.json` (0.5.0→0.6.0 с `config`) и боевой digest — **IAC-08/IAC-09 на `ORCH:shared-state`**; runtime пилотов + `dual_read`/`accepted` (IAC-13…IAC-23) — волны 1–4.

## Версии канона (после волны 0)

| Артефакт | Версия | Суть для волны 0 |
|---|---|---|
| `EcosystemIntegration_TZ.md` | **0.5.1** | мастер-ТЗ модуля 0: §10 OverlayConfig, AC-001…AC-020, I1/I2, контракты; TZ:finalize 30.09 |
| `EcosystemManifest.schema.json` | **0.6.0** (схема; живой JSON остаётся 0.5.0 до ORCH) | аддитивный `status` enum +`released` (нужен живому `edit_plan_confluence`); top-level `config` (path/schema_path/tools), migration_status |
| `EcosystemConfig.yaml` / `.schema.json` | **0.1.0** | SoT несекретной конфигурации: `shared: {}` + 46 ключей `tools{}` (`enabled`), бизнес-YAML вне required |
| `usertools_config.py` | н/д (`~/.hermes/lib`) | лоадер dual-read: process env > overlay > `tools.<key>` > `shared` > Hermes LLM / `tools.<key>.llm` > shared `.env` > legacy; `explain <tool>` |
| `render_manifest.py` | н/д | `--digest` считает tools/entities/applications + конфиг; `--check-drift` нет «второго SoT конфига» |
| `tz-workflow` (skill) | **2.10.0** | чеклист Verification: новый конфиг-ключ — только YAML+схема; литерал/`per-tool .env` = дефект; dual-read запрещён для новых tools |
| `hermes-feature` (skill) | **2.13.0** | тот же пункт чеклиста; коммит `bb14a75` |

## Что изменилось на диске (волна 0)

### `WorkVault/Registries/`
- `EcosystemManifest.schema.json` — enum `status` + `released`, `config` в `properties`/`required`, `migration_status`.
- `EcosystemConfig.schema.json` — `shared`/`tools` в required; негатив: ключи `*TOKEN*`/`*SECRET*`/`*PASSWORD*`/`*API_KEY*` → валидатор бросает.
- `EcosystemConfig.yaml` — `schema_version: 0.1.0`, `shared: {}`, 46 ключей `tools{}` с `enabled`; секретов нет.
- `render_manifest.py` + `test_render_manifest.py` — digest с конфигом и счётчиком `migration_status`.
- `test_usertools_config.py` — каскад на фикстуре `dual_read`.

### `~/.hermes/lib/`
- `usertools_config.py` — лоадер (импортирующий существующий `usertools_env.py`, не заменяя его API).

### Скиллы (`hermes-workspace`, коммит `bb14a75`, G3 чисто)
- `tz-workflow` 2.10.0, `hermes-feature` 2.13.0 — пункт про `EcosystemConfig.yaml` в Verification Checklist (проверено `grep`: `tz-workflow:425`, `hermes-feature:614`).

## Верификация docs (фаза HF:docs-handoff)

| Проверка | Результат |
|---|---|
| pytest `test_usertools_config.py` + `test_render_manifest.py` | **22 passed** |
| схема манифеста: `status.enum` содержит `released` | ✅ |
| схема манифеста: `config` в `properties` | ✅ |
| скиллы: пункт про `EcosystemConfig.yaml` + версии 2.10.0/2.13.0 в frontmatter | ✅ (`grep`, строки 425/614) |
| G3: скиллы закоммичены | ✅ `bb14a75` (чисто) |
| IAC-07 (docs version-bump в том же ходе) | ✅ |

## Манифест (для ORCH:shared-state)

Живой `EcosystemManifest.json` на этой фазе **не трогался** (сохранивется `0.5.0` без `config`). Ожидаемые шаги ORCH:
`EcosystemManifest.json` до `schema_version: "0.6.0"` + `config.path` / `config.schema_path` / `config.tools.<46>.migration_status=not_started` (IAC-08), затем `render_manifest.py --digest` → `EcosystemManifest.digest.md` (IAC-09). `restore-all-skills.sh` (реплика бэмпа тз-workflow 2.10.0 / hermes-feature 2.13.0 из `hermes-workspace`).

## Следующие шаги (не эта фаза)

1. `ORCH:shared-state` — бэмп манифеста + digest + restore-all-skills.sh.
2. Волны 1–2 (по пилотам: FirefliesAutojoin / MoveFromFF / ConfluenceSync / ProtocolFromSummary): runtime `dual_read`, реплика приёмки AC-009, статус `accepted`.
3. Волна 4: `unified_only`, очистка осиротевших `.env` (AC-011/016 по императиву «удаляй»).

## Метаданные `kanban_complete` (HF:docs-handoff)

```yaml
role: исполнитель
model: composer-2.5
tz_version: 0.5.1
tz_mtime: 2026-09-30T17:55:40Z
iac_passed: [IAC-07]
manifest_hints:
  - EcosystemManifest.json: schema_version 0.5.0→0.6.0, config.path=/home/tkachenkoav/WorkVault/Registries/EcosystemConfig.yaml
  - ExecManifest.config.schema_path=/home/tkachenkoav/WorkVault/Registries/EcosystemConfig.schema.json
  - config.tools.<key>.migration_status=not_started для всех 46 ключей tools{}
  - render_manifest.py --digest → EcosystemManifest.digest.md (IAC-09)
  - restore-all-skills.sh (реплика tz-workflow 2.10.0 / hermes-feature 2.13.0)
changed_files:
  - ~/WorkVault/Hermes-Backlog/TZ/EcosystemIntegration/version_handoff_20261001_wave0.md
git_proof:
  hermes-workspace: bb14a75  # tz-workflow 2.10.0, hermes-feature 2.13.0 (impl волны 0, G3 чисто)
cursor_session_id: unavailable-in-cli-worker
```