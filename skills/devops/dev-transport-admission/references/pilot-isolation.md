# Изолированный пилот: fixture backend вместо LLM-ролей

Как прогонять процедуру (F07/F14/F15, P1…P5, IAC-16.pre/final) на реальном
pipeline CLI без единого платного role-инвока: содержательные роли заменяются
локальным исполняемым fixture, оркестратор решает, драйвер подаёт входы.

## Структура

```text
evidence/pilot/<run-id>/
  dev/            # изолированный DEV_STATE_ROOT (state, queue.log.jsonl, каноны)
  tz/             # TZ_ROOT: GLOSSARY.md (fixture) + EcosystemManifest.digest.md
  EcosystemConfig.yaml   # изолированный конфиг (см. ниже)
  fixture_backend.py     # исполняемый stand-in ролей
  driver.py              # feed/capture, НЕ достраивает решения
```

## Изолированный EcosystemConfig.yaml
Обязательные ключи (проверить через `load_ecosystem_yaml`, не строкой):

```yaml
tools:
  dev_workflow:
    env:
      DEV_STATE_ROOT: <run-id>/dev
      TZ_ROOT: <run-id>/tz
      DIGEST_PATH: <run-id>/EcosystemManifest.digest.md
    invoke:
      default_backend: codex
    backends:
      codex:
        bin: <run-id>/../fixture_backend.py
```
`PIPELINE_ROOT` и `SKILL_ROOT` ведут на боевые Registries/hermes-workspace —
процедурный CLI реальный, изолируются только state/config/роли.

## Как CLI вызывает fixture
Fixture должен принимать ровно ту строку, что invoke_role строит по YAML:

```text
<bin> exec -C <workspace> -m <model> -c 'effort=…' --skip-git-repo-check --json --sandbox danger-full-access -- <prompt>
```

Признак того, что окружение резолвит боевой root вместо изолированного:
canonical-артефакт пишется в боевой `WorkVault/Hermes-Backlog/dev/<slug>/`.
Лечится env `B55_PILOT_DEV_ROOT=<run-id>/dev`; fixture резолвит workspace из него
(canon пишется в `$B55_PILOT_DEV_ROOT/<slug>/`).

## Парсинг промпта в fixture
Emit-файл несёт пары `slug:`/`phase:` c двоеточием:

```python
import re
m_slug = re.search(r'slug\s*:?\s*([\w\-\.]+)', prompt)
m_phase = re.search(r'phase\s*:?\s*([\w\-\:]+)', prompt)
```

Canon-файл фазы называется строго по `CANONICAL_ARTIFACT` (напр. `RS-collect.md`,
`REV-plan.md`). Если имя фазы не распарсилось, fixture пишет `-canon.md` и
получаешь `canonical_artifact_fail` («пиши в RS-collect.md, канон не обновлён») —
это не таймаут и не платный инвок, а парсинг промпта.

## Управление сценариями
Control-файл `dev/<slug>.pilotctl.json` с массивом `{"phase", "outcome", "canon"}`:

- F07: `outcome=recover` — вернуть rc=143 без канона → процедура делает один
  `recover` той пары; повторный сбой → interrupt (лимит), count остаётся 1.
- F14: REV:plan дважды `outcome=request-changes` → оба канона с `## Вердикт
  REQUEST-CHANGES`; третий rework не запускается. Снимки rev-1/rev-2 рядом с trace.
- P-задания: готовность пишется отдельным событием, не init (см. pitfalls в SKILL.md).
  FIFO читает `ready_at` из журнала событий «Б55:готовность».

## Слои evidence, которые читает verifier
`test_b55_pilot_evidence.py` (root через env `B55_EVIDENCE_ROOT`) требует:

- `orchestration.jsonl`, `transport.jsonl`, `cli.jsonl` — rows с заданными ключами.
- `load.json`, `handoff-times.json`.
- `faults/F07/trace.jsonl`, `faults/F14/trace.jsonl`, `faults/F15/trace.jsonl` —
  каждая row с ключами `{input, decision, effect}`; решения — точные токены,
  напр. F14 требует decision **`diagnose_before_third_rework`**.
- `faults/F15/requirements-delta.md` + `faults/F15/approvals/architect.md` +
  `faults/F15/approvals/reviewer.md`.

Токены и ключи должны совпадать дословно: verifier делает
`any(row[decision] == …)`. Копировать exact-набор ключей из теста перед
заполнением, не «похожий» смысл.

## Честные метрики пилота
У синтетического backend нет реального provider cost; расход оркестратора без
telemetry — «не измерено», не 0 (правило HF-plan §8: отсутствие телеметрии =
unknown). Ноль платных role-инвоков при прогоне пилота — разрешённый факт,
если YAML `backends.codex.bin` действительно ведёт на fixture, а не на боевой
бинарь (проверить через loader, не глазами).
