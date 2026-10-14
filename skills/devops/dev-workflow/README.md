# dev-workflow

Скилл оркестратора **DevWorkflow** (версия скилла **0.3.2**, мастер-ТЗ **v0.3.2**).

Заменяет связку `hermes-feature` + `tz-workflow` + канбан-оркестрацию после завершения миграции W4. На переходе W0–W3 работает **dual-path**: часть слагов — здесь, остальные — по старым скиллам (см. `SKILL.md`).

## Быстрый старт

1. Установка контура: `references/install.md`
2. Процедура в чате: `SKILL.md`
3. Выбор типа работы: `references/cases-guide.md`
4. Не-разработчик: `references/onboarding.md`

## Где код

- Python: `~/WorkVault/Registries/pipeline/` (не в git hermes-workspace)
- Состояние задач: `~/WorkVault/Hermes-Backlog/dev/<slug>/`
- Конфиг: `EcosystemConfig.yaml` → `tools.dev_workflow` (шаблон `references/config.example.yaml`)

## Тесты pipeline

Из каталога `Registries/`:

```bash
export PYTHONPATH=~/WorkVault/Registries
python3 -m pytest pipeline/tests -q
```

## Документ-источник

`~/WorkVault/Hermes-Backlog/TZ/DevWorkflow/DevWorkflow_TZ.md`
