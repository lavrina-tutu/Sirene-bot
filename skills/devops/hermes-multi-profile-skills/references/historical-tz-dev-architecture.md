# Архив: tz-dev слой в multi-profile skills

**Статус:** архив. Профиль tz-dev decommissioned 13.08.2026. См. `hermes-prompt-architecture/references/profile-decommissioning.md`.

Актуальная архитектура — workspace → default (без промежуточного слоя). Этот документ сохраняет исторический контекст для разбора инцидентов и прецедентов.

## Архитектура с tz-dev (до 13.08.2026)

```
~/hermes-workspace/                       ← Git-репо (канонический источник)
├── skills/                               ← 150+ кастомных скиллов
│   ├── devops/
│   │   ├── tz-workflow/SKILL.md
│   │   └── ...
│   └── ...
├── sync-to-hermes.sh                     ← симлинки workspace → default
├── link-tzdev-to-default.sh              ← симлинки default → tz-dev
└── restore-all-skills.sh                 ← мастер-скрипт (оба шага)

~/.hermes/profiles/default/skills/        ← Профиль-источник для Hermes
├── [bundled skills — managed by hermes update]
├── devops/
│   └── tz-workflow → ~/hermes-workspace/skills/devops/tz-workflow  ← симлинк
└── ...

~/.hermes/profiles/tz-dev/skills/         ← Рабочий профиль (Архитектор)
│   (ВАЖНО: это симлинк → ~/.hermes/skills/)
├── [bundled skills]
├── devops/
│   └── tz-workflow → ../../profiles/default/skills/devops/tz-workflow  ← симлинк
└── ...
```

**Принцип tz-dev:** симлинки на default, ничего своего не хранит.

Цепочка данных:
```
hermes-workspace/skills/ ──(symlink)──▶ default/skills/ ──(symlink)──▶ tz-dev/skills/
```

## Скрипт link-tzdev-to-default.sh

Создавал симлинки в tz-dev на кастомные скиллы из default.

- Находил все симлинки в `default/skills/` (это кастомные скиллы)
- Для каждого создавал симлинк в tz-dev с правильным относительным путём
- Использование: `link-tzdev-to-default.sh`
- Симлинки вида: `tz-dev/skills/<category>/<skill> → ../../profiles/default/skills/<category>/<skill>`
- Пропускал bundled skills в tz-dev

В составе `restore-all-skills.sh` (до decommission):
- Шаг 1: `sync-to-hermes.sh default`
- Шаг 2: `link-tzdev-to-default.sh`

## Критический питфолл: относительные пути при симлинках через tz-dev (исправлен 03.08.2026)

**Контекст:** `~/.hermes/profiles/tz-dev/skills` — это симлинк на `~/.hermes/skills`. Поэтому относительный путь от tz-dev до default считается НЕ от `profiles/tz-dev/skills/`, а от `~/.hermes/skills/`.

**Формула:** из `~/.hermes/skills/<skill_dir>` в `~/.hermes/profiles/default/skills/<skill_dir>`:
```
(depth+1) раз "../" + "profiles/default/skills/<skill_dir>"
```
где `depth` — количество слешей в `skill_dir`.

**Примеры:**
- `devops/tz-workflow` (depth=1): `../../profiles/default/skills/devops/tz-workflow`
- `mlops/inference/vllm` (depth=3): `../../../../profiles/default/skills/mlops/inference/vllm`

**Диагностика:** `find ~/.hermes/profiles/tz-dev/skills/ -mindepth 2 -maxdepth 3 -type l ! -exec test -e {} \; -print` — должен вернуть пустой вывод.

**Прецедент 03.08.2026:** три попытки подобрать формулу: (1) `depth+1` — недолёт, (2) хардкод `../../profiles/` — ломает depth≥3, (3) `depth+1` от реального пути — работает. Проверка `ls -la ~/.hermes/profiles/tz-dev/skills` показала симлинк → `~/.hermes/skills`, после чего формула была пересчитана.

При настройке симлинков между профилями шаг 4 (tz-dev→default) дал 74 битых симлинка из-за неверной формулы расчёта относительного пути. Если бы все шаги выполнялись подряд — ошибка была бы обнаружена только в конце. Пошаговая остановка позволила исправить формулу сразу.

## Процедура первоначальной настройки (историческая)

1. Убедиться, что `hermes-workspace` актуален (`git pull`, 150+ скиллов)
2. Запустить `sync-to-hermes.sh default` — создаст симлинки в default
3. Запустить `link-tzdev-to-default.sh` — создаст симлинки в tz-dev
4. Проверить: `find ~/.hermes/profiles/tz-dev/skills/ -mindepth 2 -maxdepth 3 -type l ! -exec test -e {} \; -print | wc -l` должно быть 0
5. Запустить `restore-all-skills.sh` — мастер-тест всей цепочки

## Результаты на момент реализации (03.08.2026)

| Компонент | Скиллов |
|-----------|---------|
| hermes-workspace (git) | 150 |
| default (bundled + symlink) | 145 |
| tz-dev (bundled + symlink → default) | 149 |
