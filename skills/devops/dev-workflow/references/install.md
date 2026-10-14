# Установка DevWorkflow на Hermes (Б13.3, AC-042)

Цель: поднять **скилл + pipeline** на хосте без правок ядра `hermes-agent`. Манифест, schema eco-config и `restore-all-skills.sh` в репозитории агента настраивает **ORCH** (`ORCH:shared-state`) — здесь только шаги, которые делает принимающий контур.

## Предусловия

- Git-доступ к `hermes-workspace` (скилл `devops/dev-workflow`).
- Копия `WorkVault` или как минимум `Registries/pipeline/` и каталоги ТЗ/state по путям хоста.
- `EcosystemConfig.yaml` с ключом `tools.dev_workflow` (шаблон: `config.example.yaml`).
- Секреты бэкендов в `~/.hermes/.env` (`CURSOR_API_KEY`, …).

## Чеклист

1. **Скилл** — checkout ветки с `dev-workflow` в `~/hermes-workspace/skills/devops/dev-workflow/`.
2. **Симлинки профилей** — `restore-all-skills.sh` (после того как ORCH добавил скилл в манифест активного набора; до W4 скилл может быть только в workspace без активного symlink).
3. **Pipeline** — скопировать `Registries/pipeline/` в vault этого хоста (тот же путь, что в YAML `PIPELINE_ROOT`).
4. **Конфиг** — вписать `tools.dev_workflow`: пути **этого** хоста (`DEV_STATE_ROOT`, `TZ_ROOT`, `PIPELINE_ROOT`, `SKILL_ROOT`, `DIGEST_PATH`), блоки `invoke`, `roles`, `notify`, `errorbus`, `orchestration`.
5. **Секреты** — не в YAML; только shared `.env`.
6. **Проверка контура:**
   ```bash
   export PYTHONPATH=<родитель PIPELINE_ROOT>
   python3 -m pipeline.cli status --check
   ```
   Exit 0 обязателен перед боевым init.
7. **Смоук** (без канбана как SoT):
   ```bash
   python3 -m pipeline.cli init --case RESEARCH --slug install-smoke \
     --title "install smoke" --origin-chat ID --origin-thread ID
   python3 -m pipeline.cli abort --slug install-smoke --reason "smoke" --evidence "install"
   ```
   Папка `dev/install-smoke/` остаётся (`abort` не rm).

## Обёртка из скилла

```bash
export PIPELINE_ROOT=/path/to/Registries/pipeline
~/hermes-workspace/skills/devops/dev-workflow/scripts/pipeline.sh status
```

`PIPELINE_ROOT` можно не задавать, если все пути уже в YAML и CLI читает их через `paths.py`.

## Не требуется

- Патчи `~/hermes-agent`.
- Живый канбан как источник правды (для `workflow-only`).
- USERTOOL-пакет `USERTOOLS/DevWorkflow/`.
- Per-tool `.env` у DevWorkflow.

## После `hermes update`

Процедура скилла: `restore-all-skills.sh` → `pipeline status --check`. Exit 1 = контур задет (нет pipeline, нет скилла, drift канона, импорт kanban в pipeline).

## Продуктовый комплект (Б13.5)

Для человека без разработки: `README.md` → `onboarding.md` → `cases-guide.md`. Handoff живого слага — отдельно `handoff.md`.
