# Hermes Upgrade — Pattern & Data

> **Исторический журнал единичного апгрейда Hermes v0.18.2 → v0.20.0 (07.08.2026).** Cursor CLI отменён (решение Саши 10.11.2026), оперативные роли — через codex CLI. Ниже — только переиспользуемые паттерны и питфоллы, модель-агностичные.

Этот файл описывает паттерн обновления Hermes из upstream.

## Branch Layout

- **Branch:** `_test-cutover` (12 commits ahead of origin/main)
- **Upstream:** origin/main (5136 commits ahead)
- **Fork:** git@github.com:ialextkachenko-byte/hermes-agent.git
- **Install dir:** `/home/tkachenkoav/hermes-agent`
- **Config:** `~/.hermes/profiles/default/config.yaml`

## Our 12 Local Commits (top→bottom) — статус подтверждён 07.08.2026

| # | Hash | Message | Статус |
|---|---|---|---|
| 1 | 97202b86fa | fix(gateway): retry home-channel startup notification | РЕАЛЬНЫЙ КОНФЛИКТ — перенести retry в DeliveryTransport |
| 2-8 | progress: step X.Y | QA-маркеры | Нулевой риск, внутренние файлы |
| 9 | ede3bae5fb | Merge remote-tracking branch origin/main | merge-маркер |
| 10 | 03472b1b33 | feat(telegram): opt-in DEBUG logging | Сливается чисто |
| 11 | 352b040249 | feat(gateway): additional startup notification channels | Сливается чисто |
| 12 | 276cb5296e | fix(cron): SILENT-guard last-line-equals rule | ВЫТЕСНЕН — апстрим ввёл общий matcher |

## Конфликты из dry merge (подтверждено дважды)

| Файл | Риск | Решение |
|---|---|---|
| `cron/scheduler.py` | LOW | `git checkout --theirs` |
| `tests/cron/test_scheduler.py` | LOW | `git checkout --theirs` |
| `gateway/run.py` | HIGH | Ручная работа: перенести retry в `DeliveryTransport.send()` |

59 из 62 файлов зон риска сливаются автоматически.

## Risk Zones (62 files changed upstream)

### cron/ (7 files)
- executions.py, jobs.py, lifecycle_guard.py, scheduler.py, scheduler_provider.py, suggestions.py

### gateway/ (45+ files)
- run.py — **36,958 lines changed** (+40633 / -18088 total across all)
- session.py (1176 lines), session_context.py (173), slash_commands.py (1792)
- New files: session_state.py (476), session_stall.py (121), shutdown_watchdog.py (457)
- Modified: authz_mixin.py, channel_directory.py, config.py, delivery.py, status.py, stream_consumer.py, turn_context.py, turn_lease.py (352), wake.py (184)

### agent/
- prompt_builder.py

## Backup Convention

- **Git:** `git tag -a "pre-upgrade-$(date '+%Y%m%d-%H%M%S')"` + `git commit -A` if dirty
- **Local:** `~/.hermes/_Archives/hermes-backup-YYYYMMDD-HHMMSS.tar.gz`
- **Contents:** config.yaml, .env, profiles/default/, state.db, cron/, logs/, auth.json
- **Retention:** 14 days, cleanup via `find -mtime +14 -exec rm -rf {} +`

## Execution Results (07.08.2026)

### What actually happened
- **Strategy:** merge (confirmed — rebase/squash rejected)
- **Conflicts:** 3 files (confirmed by dry merge twice)
- **gateway/run.py resolution:** `_send_with_polling_settle()` removed, retry logic moved to `DeliveryTransport.send()` in `gateway/delivery.py`
- **Test fix:** `tests/gateway/test_telegram_startup_notification_retry.py` updated to test `DeliveryTransport.send()` instead of `runner._send_with_polling_settle()`
- **Version:** v0.18.2 → v0.20.0
- **Commits:** `d237f9d810` (merge), `550e91f74a` (config v0→v33)

### `hermes doctor --fix` для config migration
After merge, `hermes doctor` showed `Config version outdated (v0 → v33)`. Running `hermes -p default doctor --fix` auto-migrated config.yaml to v33.

## Upstream Turbulence Signal

If upstream has:
- 9+ reverts in a cycle
- 100+ commits in quarantine/hold
- **→ Defer for 1-2 weeks**, let upstream stabilize

## ⚠️ Питфол: venv теряет pytest после upstream merge

После merge большого апстрима (1000+ коммитов) `scripts/run_tests.sh` может не найти pytest в `.venv/` — `error: no virtualenv with pytest found`. Причина: изменения в `pyproject.toml` или конфликты в зависимостях ломают установленные пакеты.

**Кроме того:** системный `pytest` (из `/usr/bin/python3`, Python 3.9) может не поддерживать синтаксис апстрима (`str | object` в аннотациях требует Python 3.10+). Ошибка: `TypeError: unsupported operand type(s) for |: 'type' and 'type'`.

**Фикс:**
```bash
.venv/bin/python -m ensurepip
.venv/bin/python -m pip install pytest pytest-xdist pytest-asyncio
.venv/bin/python -m pytest tests/... -q
```

**Правило:** всегда использовать `.venv/bin/python -m pytest`, НЕ системный `pytest`. Проверить: `.venv/bin/python -m pytest --version`. Прецедент: 07.08.2026, upgrade Hermes v0.18.2 → v0.20.0 (5136 коммитов).

## ⚠️ Питфол: большие задачи анализа — через codex-роль

Для задач анализа/планирования с большим объёмом входных данных (5000+ коммитов, 60+ файлов) — использовать **architect через codex CLI** (`gpt-6-astra`, `invoke-role`), не держать задачу в одном вызове с ограниченным таймаутом. Прецедент: 07.08.2026, single large-analysis call таймаутился (822с+, пустой output).
