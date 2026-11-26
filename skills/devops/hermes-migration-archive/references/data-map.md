---
# Полная по-путевая карта инвентаря ~/.hermes и сопутствующих каталогов для миграционного архива

Снято с хост-ВМ (пример ориентировочных размеров; перепроверять `du -sh` перед работой).

## ~/.hermes — всего ~19G, данные лишь малая часть

### ВАЖНО: имена каталогов-дистрибутивов (исключать)
Каталоги вида `<имя>-<версия>-linux-x64` (ffmpeg, python, node, uv, npm, ripgrep, chromium, cua-driver, agent-browser) — это пакетные менеджером распакованные бинарники, НЕ данные. Переустанавливаются `pm`/`hermes` на приёмной машине.

### Данные — включать
| Путь | Что это | Размер (пример) |
|---|---|---|
| `config.yaml` | источник конфигурации | ~29K |
| `.env` | токены/секреты, критичны | ~1K |
| `SOUL.md`, `HERMES.md`, `handover.md` | персональные файлы | KБ |
| `.hermes_history`, `upstream-monitor.json` | история/мониторинг | KБ |
| `skills/` | все наши скиллы (+ кастомные) | 53M |
| `profiles/`, `profiles-backup/` | профили | KБ |
| `state.db` | главная БД состояния/памяти | 4.1G |
| `sessions/`, `sessions.db` | сессии | MБ |
| `kanban.db`, `kanban/` | канбан | 7.5M |
| `projects.db` | проекты | 45K |
| `shared-state.db` | общее состояние | 172K |
| `verification_evidence.db` | evidence | 245K |
| `cron/` (jobs.json + executions/deliveries/notepad .db) | кроны и их локи; НЕ включать `output/`/`external-workers/` (временные доставки/логи воркеров) и `jobs.json.bak-*` | ~2M |
| `memories/` | память | 28K |
| `error_bus/events.db` | ошибки | 1.6M |
| `mcp-tokens/`, `platforms/`, `plugins/` | интеграции | KБ |
| `scripts/` | наши кастомные скрипты | ~1M |
| `channel_directory.json` | каналы | 2K |
| `google_token.json`, `google_client_secret.json` | гугл-интеграции | 1K |
| `honcho.json`, `auth.json` | auth/память | KБ |
| `worker-outboxes/`, `pii_scan/` | очереди/скан ПДн | MБ |

### Не-данные — исключать
`_Archives/` (8.4G снапшоты гермеса), `tools/` (2.1G бинарники), `installs/` (managed-workspace+venv), `cache/`, `node/`, `lsp/`, `bin/`, `logs/`, `hook_outputs/`, `environments/`, `qwen-fast/`, `haiku-fallback/` (+ генерации), `gateway.sock/pid/lock`, `state.db-wal/shm`, `cron/output/`, `cron/external-workers/`, `test_kanban_*.db*`, `tmp_*.py/json`, `*~`.

## Вне ~/.hermes — наши данные

| Путь | Что это | Размер | Включение |
|---|---|---|---|
| `~/USERTOOLS/*` | кастомные тулзы (исходники+конфиг+registry) | 1.5G | ДА, без venv/node_modules/`__pycache__` каждого и `_backup_*` |
| `~/hermes-workspace` | git репозиторий наших скиллов + config + restore/sync-скрипты | 156M | ДА, без `_bak-*`, `_bak-tzdev-*` |
| `~/WorkVault` | Obsidian vault целиком | 1.6G | ДА |

## Именование и компоновка
- Файл: `hermes-migration-<дата>.tar.gz` — один пакет.
- Собирать из staging вне WorkVault: БД — sqlite `.backup`, обычные файлы — `rsync -a` (живой агент пишет, не cp).
- Папка-назначение (для ownCloud) — `~/WorkVault/Hermes-Archive/`. Доставку верифицировать скачиванием копии сверкой `sha256` с локальным, не только `lsjson`.
- Внутрь архива положить `README.md` для приёмного агента: состав + пошаговое развёртывание (instal/hermes update → развернуть ~/.hermes → restore-all-skills из hermes-workspace → USERTOOLS → WorkVault как Obsidian → проверка скиллов/БД/кронов/тулзов) + риски (пути `/home/<user>`, live БД, секреты).
