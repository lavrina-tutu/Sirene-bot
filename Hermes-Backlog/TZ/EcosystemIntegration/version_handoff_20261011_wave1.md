# version-handoff — OverlayConfig волна 1 (2026-10-11)

Граф: `DEV/eco-config-w1` (Единый конфиг экосистемы, модуль 0 — пилоты dual_read)
Карточки: `t_45d90257` (HF:plan) · `t_d4216e34` (HF:impl) · `t_91cc435c` (HF:test) · `t_9f63eb02` (HF:docs-handoff) · `t_771aa483` (ORCH:shared-state, ожидается)
Исполнитель docs: composer-2.5 (фаза `HF:docs-handoff`; код/тесты — impl/test)

## Скоуп волны 1

Четыре пилота на runtime dual_read через `usertools_config`: `fireflies_autojoin`, `move_from_ff`, `confluence_sync`, `protocol_from_summary`. Несекреты в `EcosystemConfig.yaml` (`shared:` + `tools.<key>`), YAML побеждает per-tool `.env`/литералы на совпадающем ключе; ветка `USERTOOLS_CONFIG_MODE=legacy` сохранена (AC-013). Per-tool `.env` пилотов **не** удалялись; overlay-файлы **не** создавались.

**Вне ready-критерия §10.11.7 этой волны (не делалось):** `accepted` / `unified_only`, императив «удаляй», `rollback_snapshot`, выпил fallback из лоадера (волна 4).

**Вне скоупа исполнителя (ожидает ORCH):** живой `migration_status: dual_read` в `EcosystemManifest.json`, digest `dual_read=4 not_started=42`, `CONFLUENCE_TOKEN` в `~/.config/hermes/.env` (IAC-03), посадка `Q-1`…`Q-4` (IAC-19).

## Версии канона (после волны 1, код на диске)

| Артефакт | Версия | Суть для волны 1 |
|---|---|---|
| `EcosystemIntegration_TZ.md` | **0.6.0** (без бампа) | §10.11 задаёт состав пилотов и ready-критерий; норматив достаточен — правки master-ТЗ не требовались |
| `EcosystemManifest.json` | **0.6.0** + `config` | на handoff: все 46 ключей `migration_status: not_started` (IAC-14 — ORCH) |
| `EcosystemManifest.digest.md` | снимок wave0 | `not_started=46 dual_read=0` до `render_manifest.py --digest` после ORCH |
| `EcosystemConfig.yaml` / `.schema.json` | **0.1.0 → 0.1.1** | `shared: WORKVAULT_PATH`, `CONFLUENCE_URL`; 4 пилота расширены; 42 ключа — только `enabled` |
| `usertools_config.py` | н/д (`~/.hermes/lib`) | без изменений API; пилоты читают `load_tool_config` на основном пути |
| `render_manifest.py` | н/д | `--check-drift` exit 0 после волны 1 |

## Что изменилось на диске (волна 1)

### `WorkVault/Registries/`
- [`EcosystemConfig.schema.json`](file:///home/tkachenkoav/WorkVault/Registries/EcosystemConfig.schema.json) — бамп **0.1.1**, именованные ключи волны 1 в `tool_section.properties`; `additionalProperties: string` сохранён; `propertyNames` режет секретные имена.
- [`EcosystemConfig.yaml`](file:///home/tkachenkoav/WorkVault/Registries/EcosystemConfig.yaml) — `shared` + блоки четырёх пилотов (см. план IAC-02 / §3 HF:plan).
- [`test_usertools_config.py`](file:///home/tkachenkoav/WorkVault/Registries/test_usertools_config.py) — YAML-win и изоляция соседа для 4 ключей.

### `USERTOOLS/` (4× `config.py`, dual_read + legacy)
- [`FirefliesAutojoin/ffjoin/config.py`](file:///home/tkachenkoav/USERTOOLS/FirefliesAutojoin/ffjoin/config.py)
- [`MoveFromFF/movefromff/config.py`](file:///home/tkachenkoav/USERTOOLS/MoveFromFF/movefromff/config.py) (git-worktree — коммит в репозитории инструмента)
- [`ConfluenceSync/confluencesync/config.py`](file:///home/tkachenkoav/USERTOOLS/ConfluenceSync/confluencesync/config.py)
- [`ProtocolFromSummary/protocolfromsummary/config.py`](file:///home/tkachenkoav/USERTOOLS/ProtocolFromSummary/protocolfromsummary/config.py) (git-worktree)

Per-tool `.env`: FF / MFF / CS на месте; у PFS корневого `.env` нет (как до волны).

### Улики AC-008 (артефакты HF:test)
- [`evidence_wave1_fireflies_autojoin.md`](evidence_wave1_fireflies_autojoin.md)
- [`evidence_wave1_move_from_ff.md`](evidence_wave1_move_from_ff.md)
- [`evidence_wave1_confluence_sync.md`](evidence_wave1_confluence_sync.md)
- [`evidence_wave1_protocol_from_summary.md`](evidence_wave1_protocol_from_summary.md)

План IAC (архив): [`HF-plan_wave1_dualread_4pilots_20261011.md`](HF-plan_wave1_dualread_4pilots_20261011.md)

## Верификация docs (фаза HF:docs-handoff, 2026-10-11)

| Проверка | Результат |
|---|---|
| pytest `test_usertools_config.py` + `test_render_manifest.py` | **28 passed** |
| `render_manifest.py --check-drift` | exit **0** (`No drift detected`) |
| `load_tool_config` 4 пилота | без KeyError (31/31/24/30 ключей) |
| `resolve_key` — несекреты пилотов | `ecosystem_config` / `shared` (FF `EXCHANGE_EMAIL`, MFF `TOOL_DIR`+`WORKVAULT_PATH`, CS/PFS пути и URL) |
| `CONFLUENCE_TOKEN` | **до ORCH IAC-03:** CS → `source=legacy` (per-tool `.env`); shared `.env` ключа нет; PFS — секрет не из shared до переноса |
| ErrorBus (пакеты улик) | **0** новых config/env/yaml/missing по каждому пилоту (см. evidence §2) |
| AC-008(b) крон-тики | 2026-10-11 вс — weekday-окно FF/MFF/PFS после миграции **не** наступило; в evidence зафиксировано отложение до пн 9–19 (plan Q-1), без fabricate |
| Манифест `migration_status` | все 46 `not_started` (код dual_read готов; индекс — ORCH IAC-14) |
| Master-ТЗ | **не менялся** — §10.11.1–10.11.7 уже описывают реализацию |

## Манифест (manifest_hints для `ORCH:shared-state`, карточка `t_771aa483`)

Исполнитель **не** писал: `EcosystemManifest.json`, `EcosystemManifest.digest.md`, `~/.config/hermes/.env`, `jobs.json`.

Ожидаемые шаги ORCH (IAC-03, IAC-14, IAC-19):

1. **IAC-03:** добавить `CONFLUENCE_TOKEN=` в `~/.config/hermes/.env` (копия из `ConfluenceSync/.env`; per-tool файл не удалять). Verify без печати значений: ключ присутствует; **не** писать токен в YAML/манифест/digest.
2. **IAC-14:** для `fireflies_autojoin`, `move_from_ff`, `confluence_sync`, `protocol_from_summary` — `config.tools.<key>.migration_status: dual_read`, `overlay: null`, `rollback_snapshot: null`; 42 остальных без изменений. Затем `python3 /home/tkachenkoav/WorkVault/Registries/render_manifest.py --digest` → digest с `dual_read=4 not_started=42`.
3. **IAC-19:** после зелёных пакетов улик (в т.ч. дозакрытие `CONFLUENCE_TOKEN source=shared_env` для CS/PFS после IAC-03) — на body карточки ORCH четыре пары `Q-n` + `tool_key: <key>` + «принять / не принять»; **не** писать `accepted`.

После IAC-03 перепроверить explain для CS/PFS: `CONFLUENCE_TOKEN` → `shared_env`.

## Следующие шаги (не эта фаза)

1. `ORCH:shared-state` (`t_771aa483`) — IAC-03 / IAC-14 / IAC-19.
2. Пн 9–19 — добор AC-008(b): ≥3 тика FF (и при необходимости MFF/PFS jobs) или 1 рабочий день.
3. Реплика Саши по каждому `Q-n` → `accepted` + `rollback_snapshot` (IAC-24, вне ready волны 1).
4. Отдельный императив «удаляй legacy» per tool после `accepted` (IAC-25…).

## Метаданные `kanban_complete` (HF:docs-handoff)

```yaml
role: исполнитель (docs)
model: composer-2.5
tz_version: 0.6.0
tz_mtime: 2026-10-11T15:20:17Z
iac_passed: [IAC-01, IAC-02, IAC-04…IAC-13, IAC-15…IAC-18, IAC-20…IAC-23]  # impl/test; ORCH IAC-03/14/19 вне исполнителя
manifest_hints:
  - EcosystemManifest.json: fireflies_autojoin, move_from_ff, confluence_sync, protocol_from_summary → migration_status=dual_read, overlay=null, rollback_snapshot=null
  - EcosystemManifest.json: 42 прочих config.tools.<key> → not_started без изменений
  - render_manifest.py --digest → EcosystemManifest.digest.md (dual_read=4 not_started=42)
  - ~/.config/hermes/.env: добавить CONFLUENCE_TOKEN (IAC-03); per-tool ConfluenceSync/.env не удалять
  - ORCH body: Q-1…Q-4 с tool_key по одному пилоту; accepted не писать
  - jobs.json / Gateway: не трогать; кроны не создавать
changed_files:
  - ~/WorkVault/Hermes-Backlog/TZ/EcosystemIntegration/version_handoff_20261011_wave1.md
  - ~/WorkVault/Registries/EcosystemConfig.schema.json
  - ~/WorkVault/Registries/EcosystemConfig.yaml
  - ~/WorkVault/Registries/test_usertools_config.py
  - ~/USERTOOLS/FirefliesAutojoin/ffjoin/config.py
  - ~/USERTOOLS/MoveFromFF/movefromff/config.py
  - ~/USERTOOLS/ConfluenceSync/confluencesync/config.py
  - ~/USERTOOLS/ProtocolFromSummary/protocolfromsummary/config.py
  - ~/WorkVault/Hermes-Backlog/TZ/EcosystemIntegration/evidence_wave1_*.md
not_touched:
  - EcosystemManifest.json
  - EcosystemManifest.digest.md
  - ~/.config/hermes/.env
  - jobs.json
cursor_session_id: 20261011_182315_7d0b0d
context-used:
  card: t_9f63eb02
  root: DEV/eco-config-w1
  phase: HF:docs-handoff
```
