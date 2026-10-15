# HF:plan (addendum) — волна 1 (dual_read, 4 пилота): probe-AC battle-interpreters

фаза: `HF:plan` (addendum к `HF-plan_wave1_dualread_4pilots_20261011.md`)  
слаг: `DEV/anywhere-contacts` (системный класс battle-interpreters §10.12)  
роль: архитектор (`cursor-grok-4.6-high`)  
дата диска: 2026-10-13  
канон: EcosystemIntegration §10.12.5 (probe-AC обязателен в `HF:plan` **первого драфта** волны)

---

## Контекст

Исторический план волны 1 (dual_read 4 пилотов) **не переписывается** (§10.12.8: тексты AC-007…AC-014 и §10.11 не ретрофит). Этот аддендум добавляет **дополнительный** AC класса battle-interpreters: для каждого из 4 пилотов фиксируется боевой python + обязательный `probe_battle_venv.py` PASS на нём. Исторический `HF-plan_wave1_dualread_4pilots_20261011.md` остаётся как есть; настоящий аддендум лежит рядом и **не заменяет** его.

## IAC (probe-AC, добавка)

| IAC-## | phase_from→phase_to | path | verify | depends | covers AC-### |
|---|---|---|---|---|---|
| I1-PR | `HF:impl`→`HF:test` | `~/WorkVault/Registries/battle_interpreters.yaml` ключ `fireflies_autojoin` + `~/.hermes/lib/probe_battle_venv.py` | Боевой python = `FirefliesAutojoin/venv_linux/bin/python` (closure: user crontab → bin/run.sh). `python3 ~/.hermes/lib/probe_battle_venv.py` PASS по `fireflies_autojoin` (import yaml + usertools_config боевым python; declared импорты). `usertools_config.py explain fireflies_autojoin` **тем же** python (bin/run.sh внутри). | IAC-01 реестра battle-interpreters | AC-B01 (probe волна 1), AC-008 (пилот) |
| I1-PR | `HF:impl`→`HF:test` | ключ `move_from_ff` | Боевой python = `MoveFromFF/.venv/bin/python` (closure: job vm_movefromff / movefromff_sync.sh). Probe PASS по `move_from_ff` (yaml + pydantic). `explain move_from_ff` тем же python. | IAC-01 реестра | AC-B01, AC-008 (пилот) |
| I1-PR | `HF:impl`→`HF:test` | ключ `confluence_sync` | Боевой python = `ConfluenceSync/.venv/bin/python` (closure: `.venv/bin/confluencesync`). Probe PASS по `confluence_sync`. `explain confluence_sync` тем же python. | IAC-01 реестра | AC-B01, AC-008 (пилот) |
| I1-PR | `HF:impl`→`HF:test` | ключ `protocol_from_summary` | Боевой python = `ProtocolFromSummary/.venv/bin/python` (closure: job 21255143c523 / protocolfromsummary_notify_pending.sh). Probe PASS по `protocol_from_summary`. `explain protocol_from_summary` тем же python. | IAC-01 реестра | AC-B01, AC-008 (пилот) |

**Алгоритм по каждому пилоту:** (a) closure входа → `sys.executable` == battle_python реестра; (b) `probe_battle_venv.py` PASS по ключу; (c) пакет улик AC-008 собирается `explain`-ом **тем же** python (не Hermes 3.14). Поштучный `Q-n` AC-009 пилота — **после** PASS probe этого ключа (§10.12.5).

## Verify IAC-10 (этот файл)

`rg -n 'probe_battle_venv.py' …/HF-plan_wave1_probe-ac_addendum_20261013.md …/HF-plan_battle-interpreters_20261013.md …/HF-plan_wave3_no-config_20261013.md …/HF-plan_wave4_fallback-cut_20261013.md` — ≥1 на файл (артефакт батча IAC-10).

## Что НЕ трогать

- Исторический `HF-plan_wave1_dualread_4pilots_20261011.md` — только аддендум рядом, его строки IAC/AC не менять.
- В этой волне (первый драфт): `migration_status`, manifest/digest, `accepted`, посадку Q-n — как в исходном плане волны 1 (только после PASS probe этого ключа, рекомендация §10.12.5).