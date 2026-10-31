---
name: hermes-feature
description: "Use when: цикл ТЗ→код Hermes, баг, исследование, доработка"
version: 2.14.0
author: agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [hermes, cursor, development, feature, process, debug, research]
    related_skills: [tz-workflow, hermes-agent-skill-authoring, hermes-ops]
---

# hermes-feature

## Overview

Единый процесс Hermes и USERTOOLS: ТЗ → план → реализация → тесты → документация → диагностика/откат. Оркестратор ведёт DevWorkflow через `pipeline init`/`next`/`complete-phase`; роли запускаются через `emit-prompt` → `invoke-role`. Исполнители не изменяют общий state.

Архитектор (default) не пишет ТЗ, планы или анализ в чате: используй предусмотренный role-путь и передавай документы полностью (`cat`, абсолютный путь или явное `часть 1/N`). Для бага сначала обязательна фаза `BUG:diagnose`; прямой `agent -p` до неё запрещён.

## When to Use

- «разработай», «новый инструмент», «напиши код», «реализуй» → Блоки 0–4.
- «баг», «ошибка», «не работает», «почини» → `BUG:diagnose`, затем Блок 7.
- «исследуй», «проанализируй», «сравни» → Блок 8/RESEARCH.
- «обнови Hermes», «merge upstream» → Блок 1 + [upgrade reference](references/hermes-upgrade-pattern.md).
- 3+ изменений конфига/скиллов/инструментов → QA (Блок 6А).

Не использовать для простой рутины без ТЗ/вариантов или правок стиля общения.

### Маршрутизация

Баг-триггер всегда создаёт `DEV/<slug>` и `BUG:diagnose` первым `pipeline init`-ходом, до любого role/делегирования; затем `GATE:diagnose-review` (auto), TZ-WRITE и полный или LIGHT хвост. LIGHT разрешён только после гейта: ≤3 файлов кода+тестов, без shared/новых сущностей/cron/.env/манифеста. Ошибка провайдера LLM — не BUGFIX.

Запрос без изменения кода/процесса — прямой ответ без DevWorkflow-slug. При сомнении выбирай `BUG:diagnose`. После `TZ:finalize` AC показывается в origin, `GATE:take-into-work` auto-pass (`auto-pass: ac-shown`).

## Термины и dual-path

Перед первым `PREFIX:фаза` читай `~/WorkVault/Hermes-Backlog/TZ/GLOSSARY.md`; используй только канонические имена. При `orchestration.mode` ≠ `workflow-only` соблюдай `pilot_slugs`, не допускай два поезда на slug и останавливайся при живом kanban-running; детали — [core runbook](references/devworkflow-core.md).

## DevWorkflow-шаг

1. Проверь активный slug (`todo|ready|running|blocked`), корень `DEV/<slug>`, `GATE:take-into-work` и отсутствие дубликата.
2. Создавай полный граф одним батчем; не задавай model override в `pipeline init`/рецепте. На живом slug не запускай параллельный ручной Cursor; off-board требует паузы и retro-учёта.
3. Перед каждой ролью: `pipeline emit-prompt ... --out /tmp/task.md` должен вернуть 0; перед `complete-phase` нужен `pipeline check` 0 и маркер `context-used:`. `--force`/`flag-waived` не обходят context-bundle.
4. Общий state (`EcosystemManifest.json`, `entities.json`, `.env`, `jobs.json`, digest/render) пишет только `ORCH:shared-state`; воркер сообщает `manifest_hints`.
5. `GATE:done` auto после preflight 0, снятых holds и пустых вопросов; AC-отчёт сначала публикуется в origin и фиксируется маркером `AC-delivered: origin`.

Граф, origin-routing, identity-checklist, disk-fact контроль планирования, collapsed-chain guard и one-pass правила — [core runbook](references/devworkflow-core.md).

## Блок 0: ТЗ

ТЗ финализирует архитектор; после `TZ:finalize` поезд продолжается автоматически. Кризис фиксируется в origin и блокирует корень до решения Саши. Подробности role-пути — [roles and phases](references/roles-and-phases.md).

## Блок 1: Анализ вариантов

Архитектор даёт 2–3 варианта, сначала рекомендацию; варианты нумеруются 1/2/3 и строятся reuse-first. После выбора вопросы задаются по одному; подробная процедура — [roles and phases](references/roles-and-phases.md) и [reuse-first](references/reuse-first-rule.md).

## Блок 1А: Планирование

До кода нужен пофайловый план с IAC, тестами, точками проверки и отдельным согласованием новых сущностей. `HF:plan` read-only; `GATE:plan-approve` auto. Полный контракт — [roles and phases](references/roles-and-phases.md).

## Блок 2: Реализация

Исполнитель пишет по плану; мелкое отклонение (≤2 файлов без смены архитектуры) допустимо, крупное требует доплана, системный блокер — вопрос Саше. Бэкап и identity-предусловия обязательны; детали — [roles and phases](references/roles-and-phases.md).

## Блок 3: Тестирование

`HF:test` выполняет тот же исполнитель по IAC; отдельной роли тестировщика нет. Готово только после всех verify, включая `probe_battle_venv.py` для eco-config; крупный дефект эскалируется архитектору через решение Саши.

## Блок 4: Документирование

`HF:docs-handoff` меняет текст скилла/ТЗ и передаёт `manifest_hints`; манифест и общий state — только `ORCH:shared-state`. ТЗ хранится до вывода инструмента из эксплуатации.

## Блок 5: Бэкапы и откат

Архитектор бэкапит всегда; исполнитель — при изменении `config.yaml`/`jobs.json`. Путь и retention: `~/.hermes/_Archives/hermes-backup-YYYYMMDD-HHMMSS/`, 2 недели; аварийный откат — архитектор.

## Блок 5Б: Разрешающие сигналы

Side-effect разрешён только прямым императивом Саши или пунктом согласованного плана. `question-answer`, `own-inference` и `conditional` не разрешают запись, cron или mutating API; полный классификатор — [roles and phases](references/roles-and-phases.md).

## Блок 6: Эскалация

Критическая поломка или неопределённость в ТЗ → стоп и сообщение Саше; ночью сохрани состояние в ТЗ и жди решения. Рутинный cron без ошибок не буди.

## Блок 6А: QA

Для hotfix без предварительного плана: архитекторский checklist → до 3 циклов исправления; остаток ❌ означает откат и доклад. Если IAC-план уже пройден, 6А пропускается.

## Блок 6Б: Делегирование

На живом графе не используй `cronjob`/`delegate_task` для диспатчащихся детей. Вне графа соблюдай D1/D2 namespace, toolsets, таймауты, полный контекст и reuse-first; [subagent rules](references/subagent-rules.md).

## Блок 6В: Диагностика перед починкой

Не чинить сразу: `BUG:diagnose` (read-only) → `_fix_plan_YYYYMMDD.md`/непустой body → auto `GATE:diagnose-review` → TZ-WRITE → HF-реализация. План и контекстные guards — [bugfix runbook](references/bugfix-workflow.md).

## Блок 7: Диагностика и отладка

Используй systematic-debugging: root cause → pattern → hypothesis → fix. Диагноз остаётся `BUG:diagnose`, фикс — `HF:impl`; при изменении ТЗ запускай `render_manifest.py --check-drift`. Reuse-first обязателен.

## Блок 8: Исследования и анализ

RESEARCH имеет slug и фазы `RS:*`; collect/analyze и `REV:report` идут раздельными ролями. Алгоритм: Scope → Сбор → Анализ → Рекомендации; без данных и графа код/конфиги/скиллы не менять.

## Справочники

- [DevWorkflow core](references/devworkflow-core.md) — dual-path, граф, воркеры, гейты, one-pass.
- [Bugfix routing](references/bugfix-workflow.md) — классификация, BUGFIX, emit-prompt/check, диагностика.
- [Roles and phases](references/roles-and-phases.md) — модели, блоки 0–8, планы, тесты, state ownership, venv.
- [Subagent rules](references/subagent-rules.md) — делегирование и контракты промптов.
- [Verification checklist](references/verification-checklist.md) — полный итоговый чеклист.
- [Cursor CLI](references/cursor-cli.md), [patterns](references/cursor-cli-patterns.md), [limitations](references/cursor-cli-limitations.md).
- [Hermes upgrade](references/hermes-upgrade-pattern.md) — merge, risk zones, upgrade pitfalls.
- [Pitfall remediation](references/pitfall-remediation-workflow.md), [SRTool](references/srtool-v2-pitfalls.md), [MoveFromLoop v0.4.2](references/movefromloop-v042-pitfalls.md), [v0.4.3](references/movefromloop-v043-pitfalls.md), [reuse-first](references/reuse-first-rule.md).

## Verification Checklist

Перед завершением проверь [полный checklist](references/verification-checklist.md): гейты и AC в origin, IAC/backup, модели и полный контекст, BUGFIX-first, commit/drift/eco-config invariants и отсутствие новых сущностей без согласования.
