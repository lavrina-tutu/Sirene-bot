# HF:plan — волна 4 (fallback-cut): повторный probe-AC с первого драфта

фаза: `HF:plan` (первый драфт)  
слаг: `DEV/anywhere-contacts` (системный класс battle-interpreters §10.12)  
роль: архитектор (`cursor-grok-4.6-high`)  
дата диска: 2026-10-13  
канон: EcosystemIntegration §10.12.5 — probe-AC обязан входить в `HF:plan` волны **с первого драфта**.

---

## Контекст

Волна 4 — вырез слоёв 2/7 лоадера `usertools_config.py` (legacy `.env` / fallback-пути). После выреза probe **повторяется** на тех же боевых python ключей (регресс «пакет был только в legacy-пути»). Убрать fallback не значит убрать боевой python входа — наоборот, closure входа обязан остаться bойным и probe обязан зелёным.

## IAC (прототип на ключ волны 4)

| IAC-## | phase_from→phase_to | path | verify | depends | covers AC-### |
|---|---|---|---|---|---|
| I4-PR | `HF:impl`→`HF:test` | `~/WorkVault/Registries/battle_interpreters.yaml` + `~/.hermes/lib/probe_battle_venv.py` | После выреза слоёв 2/7 лоадера — **повторный** `python3 ~/.hermes/lib/probe_battle_venv.py` на тех же `battle_python` реестра: `import yaml` + `import usertools_config` + declared **боевым** python каждого ключа волны 4; closure входа (wrapper/скилл/shebang/крон) совпадает с `battle_python`. Каждый PASS — индикатор, что пакет инструмента не жил только в legacy-пути лоадера. Pytest в PFS/hermes/per-tool venv этот AC **не** закрывает. | IAC-01/02/03/04 реестра battle-interpreters | AC-B01 (probe волны 4), AC волны 4 |

## verify (IAC-10)

`rg -n 'probe_battle_venv.py' …/HF-plan_wave4_fallback-cut_20261013.md …/HF-plan_battle-interpreters_20261013.md …/HF-plan_wave1_probe-ac_addendum_20261013.md …/HF-plan_wave3_no-config_20261013.md` — ≥1 на файл.

## Что НЕ трогать (в этом HF:impl)

- **Не исполнять** вырез fallback-слоёв лоадера — только первый драфт плана с probe-AC (маркер IAC-10 в мастер-плане).
- legacy-ветку `USERTOOLS_CONFIG_MODE` не трогать; `.env` пилотов не сносить до отдельного императива (§10.12/§10.11.7).
- `migration_status`/manifest/digest — только `ORCH:shared-state` после PASS.