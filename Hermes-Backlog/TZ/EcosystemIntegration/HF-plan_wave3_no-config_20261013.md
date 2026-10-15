# HF:plan — волна 3 (без своего конфиг-файла): probe-AC с первого драфта

фаза: `HF:plan` (первый драфт)  
слаг: `DEV/anywhere-contacts` (системный класс battle-interpreters §10.12)  
роль: архитектор (`cursor-grok-4.6-high`)  
дата диска: 2026-10-13  
канон: EcosystemIntegration §10.12.5 — probe-AC обязан входить в `HF:plan` волны **с первого драфта**, на каждый ключ волны.

---

## Контекст

Волна 3 — «без своего конфиг-файла»: остальные `tools{}` вне w1/w2, которым только регистрация `enabled` + конвенция путей/logs, отдельного Overlay-конфига нет. Даже для «чистой регистрации» §10.12.5: если боевой вход есть — probe по нему; входа нет — строка реестра `entry_kind` + явное «входа нет», при этом `import yaml` / `usertools_config` probe гоняет на python, которым инструмент вызвали бы.

## IAC (прототип на ключ волны 3)

| IAC-## | phase_from→phase_to | path | verify | depends | covers AC-### |
|---|---|---|---|---|---|
| I3-PR | `HF:impl`→`HF:test` | `~/WorkVault/Registries/battle_interpreters.yaml` + `~/.hermes/lib/probe_battle_venv.py` | Для каждого ключа волны 3 в реестре: `entry_kind` ∈ {cron, wrapper, skill, shebang} (или явное «входа нет»), `battle_python` = python, которым инструмент вызвали бы. `python3 ~/.hermes/lib/probe_battle_venv.py` PASS по этому ключу: `import yaml` + `import usertools_config` **боевым** python; declared импорты где есть. `usertools_config.py explain <tool>` **тем же** python. Ключ без боевого входа: `entry_kind` + «входа нет», probe всё равно гоняет import yaml/usertools_config на релевантном python. Pytest в PFS/hermes/per-tool venv этот AC **не** закрывает. | IAC-01/02 реестра battle-interpreters | AC-B01 (probe волны 3), AC волны 3 |

## verify (IAC-10)

`rg -n 'probe_battle_venv.py' …/HF-plan_wave3_no-config_20261013.md …/HF-plan_battle-interpreters_20261013.md …/HF-plan_wave1_probe-ac_addendum_20261013.md …/HF-plan_wave4_fallback-cut_20261013.md` — ≥1 на файл.

## Что НЕ трогать

- Новый `tools{}` под OverlayConfig / probe — не заводить.
- `migration_status`, manifest/digest, `.env`, `accepted` — только `ORCH:shared-state` после PASS.
- dual_read не для новых tools; новый конфиг-ключ — только `EcosystemConfig.yaml` + schema (§10.12.7).