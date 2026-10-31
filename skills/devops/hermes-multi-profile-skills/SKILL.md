---
name: hermes-multi-profile-skills
description: "скиллы пропали: git hermes-workspace → симлинки профиля"
version: 2.0.1
author: agent
tags: [hermes, skills, profiles, symlinks, git, sync]
platforms: [linux]
---

Скилл про управление кастомными скиллами Hermes через hermes-workspace (git) → симлинки → профиль default.

# Hermes Multi-Profile Skills

Класс задачи: держать один канонический набор кастомных скиллов в git-репозитории и подключать их к профилю Hermes через симлинки — без дублирования файлов и с защитой от потери при `hermes update`.

## Архитектура

```
~/hermes-workspace/                       ← Git-репо (канонический источник)
├── skills/                               ← 150+ кастомных скиллов
│   ├── devops/
│   │   ├── tz-workflow/SKILL.md
│   │   └── ...
│   └── ...
├── sync-to-hermes.sh                     ← симлинки workspace → default
└── restore-all-skills.sh                 ← восстановление (фактически = sync-to-hermes.sh default)

~/.hermes/profiles/default/skills/        ← Профиль Hermes
├── [bundled skills — managed by hermes update]
├── devops/
│   └── tz-workflow → ~/hermes-workspace/skills/devops/tz-workflow  ← симлинк
└── ...
```

> Ранее был слой tz-dev, decommissioned 13.08.2026, детали — `references/historical-tz-dev-architecture.md`.

## КРИТИЧЕСКИЙ питфолл: симлинк в `profiles/default/skills/` НЕ делает скилл видимым

**Прецедент 04.09.2026 (`deep-mine-project`):** скилл существовал в git (`hermes-workspace/skills/research/deep-mine-project/`), симлинк был в `~/.hermes/profiles/default/skills/research/deep-mine-project` (sync-to-hermes.sh показывал «Already OK 163»), но агент его **не видел**: его не было в `<available_skills>`, `skill_view` его не находил, CLI из скилла не вызывался.

**Причина — ДВА СЛОЯ симлинков, а не один.** Сканируемый путь — НЕ `~/.hermes/profiles/default/skills/`, а **живой** `~/.hermes/skills/<category>/<name>`. Это отдельное дерево верхнеуровневых симлинков вида:
```bash
~/.hermes/skills/research/research-tools  ->  ../../profiles/default/skills/research/research-tools
~/.hermes/skills/research/workvault-rag   ->  ../../profiles/default/skills/research/workvault-rag
```
`sync-to-hermes.sh` / `restore-all-skills.sh` (`sync-to-hermes.sh default`) заполняют **только** `profiles/default/skills/` и НЕ трогают этот живой верхний слой. Поэтому скилл может быть в профиле, но невидим агенту.

**Симптом диагностики:** у `ls ~/.hermes/skills/research/` видны старожилы (`research-tools`, `workvault-rag`), а нового скилла нет, при этом в `profiles/default/skills/research/` он есть.

**Фикс (создать живой симлинк):**
```bash
cd ~/.hermes/skills/research && \
  ln -s ../../profiles/default/skills/research/deep-mine-project deep-mine-project
```
После этого `skill_view(name)` и `<available_skills>` начинают видеть скилл.

**Проверка после ЛЮБОГО добавления кастомного скилла:** не ограничиваться `find ~/.hermes/profiles/default/skills/` — обязательно убедиться, что скилл появился в живом `~/.hermes/skills/<category>/<name>` (и воспроизводится `skill_view`). Если новый скилл «невидим» — проверять этот верхний слой ПЕРВЫМ делом, прежде чем искать проблему в git/профиле.

**Принципы:**
- **Git** — единственный канонический источник кастомных скиллов. WorkVault НЕ используется (rsync перетирает).
- **default** — профиль Hermes, куда симлинками подключаются кастомные скиллы из git.
- Скрипты идемпотентны — можно запускать многократно без вреда.

## Канон направления синка WorkVault ↔ hermes-workspace

**`restore-all-skills.sh` синхронизирует ТОЛЬКО симлинки скиллов.** Он НЕ должен копировать ничего в WorkVault (ТЗ, entities.json) — направление синка ТЗ/данных-графа строго **WorkVault → git**, единственная точка — `~/.hermes/scripts/autosync_github.sh` (крон 02:00). WorkVault = источник правды, git-зеркало (`hermes-workspace/Hermes-Backlog`) = бэкап.

Обратное (`git → WorkVault`) в `restore-all-skills.sh` или любом крон добавлено быть не должно: это откатывает дневные правки ТЗ старым зеркалом. Прецедент 16.10.2026 — блоки `cp` зеркало→WorkVault откатили ProtocolFromSummary v1.29.0 → v1.28.1; удалены.

## Важные локации

| Что | Где |
|-----|-----|
| Git-репо (канонический источник) | `~/hermes-workspace/skills/` |
| Профиль default | `~/.hermes/profiles/default/skills/` |
| Бэкапы куратора | `<profile>/skills/.curator_backups/<timestamp>/skills.tar.gz` |
| Скрипты управления | `~/hermes-workspace/*.sh` |
| Скрипты автосинка | `~/.hermes/scripts/autosync_github.sh` |

Другие профили (anthropic, openai и др.) этим скиллом не синхронизируются.

## Процедура: первоначальная настройка

1. Убедиться, что `hermes-workspace` актуален (`git pull`, 150+ скиллов)
2. Запустить `sync-to-hermes.sh default` — создаст симлинки в default
3. Проверить: `find ~/.hermes/profiles/default/skills/ -mindepth 2 -maxdepth 3 -type l ! -exec test -e {} \; -print | wc -l` должно быть 0
4. Запустить `restore-all-skills.sh` — мастер-тест всей цепочки

## Аудит: где какие скиллы

```bash
# Посчитать скиллы в git-репо
find ~/hermes-workspace/skills/ -name "SKILL.md" -not -path "*/.git/*" -not -path "*/.curator_backups/*" | wc -l

# Посчитать симлинки в default (кастомные)
find ~/.hermes/profiles/default/skills/ -mindepth 2 -maxdepth 3 -type l | wc -l

# Найти скиллы в git, которых нет в default
find ~/hermes-workspace/skills/ -name "SKILL.md" -not -path "*/.git/*" | while read f; do
  dirname "$f" | sed 's|.*/skills/||' | tr '/' '\n' | tail -1
done | sort > /tmp/git.txt
find ~/.hermes/profiles/default/skills/ -mindepth 2 -maxdepth 3 -type l | while read l; do
  echo "$l" | sed 's|.*/skills/||' | tr '/' '\n' | tail -1
done | sort > /tmp/default.txt
comm -23 /tmp/git.txt /tmp/default.txt
```

## Скиллы, которые НЕ в git: реальная папка vs симлинк

**Прецедент 15.08.2026** (`hermes-prompt-architecture`): канонический источник — `~/hermes-workspace/skills/` (git-репо). Но часть dev-скиллов лежит **реальной папкой** прямо в `~/.hermes/skills/devops/`, не являясь симлинком на workspace → они вне git, не версионируются, autosync их не пушит. После правки `git status` в workspace молчит.

**Проверка связи:**
```bash
readlink -f ~/.hermes/skills/devops/<name>/SKILL.md
# возвращает тот же путь → НЕ симлинк → скилл вне git
# ведёт на ~/hermes-workspace/… → ок, под контролем
```
Проверить в git: `cd ~/hermes-workspace && git ls-files | grep -c <name>` (0 → вне версионирования).

**Подключить к версионированию (только для КАСТОМНЫХ скиллов):**

Store/bundled-скиллы (skill-store/hub-managed) НЕ переносить в симлинк: hub-installer (`_resolve_lock_install_path`) отклоняет symlink как `Unsafe install path`, их install/update сломаются — они обязаны остаться физическими. Разделять по автору/маркеру `.hub/lock.json` до переноса.

```bash
cp -r ~/.hermes/skills/devops/<skill> ~/hermes-workspace/skills/devops/<skill>
cd ~/hermes-workspace && git add -A && git commit && git push
```

**Питфолл — реальная папка затеняет свежую правку симлинка-источника:** если скилл живёт реальной папкой в `~/.hermes/skills/` (НЕ симлинк), то правка в canonical-источнике (`~/hermes-workspace/skills/…`) НЕ доходит до runtime — `skill_view`/агент продолжают читать старую копию, даже если `sync-to-hermes.sh` уже создал симлинк в `profiles/default/skills/`. Исполнитель, правящий скилл, часто касается только canonical (workspace) и не обновляет живую папку — self-report «правка внесена» при этом верен для источника и ЛОЖЕН для runtime.

**Проверка эффективности правки — по runtime-версии, не по источнику:** после патча скилла проверять `grep '^version:' ~/.hermes/skills/<cat>/<name>/SKILL.md` (тот путь, что реально читает агент), а не `~/hermes-workspace/…`. Старый номер в живом пути = правка не подхвачена, сколько бы её ни декларировал исполнитель.

**Завершающий шаг — конвертировать реальную папку в симлинк (с бэкапом):**
```bash
TS=$(date +%Y%m%d-%H%M%S); BK=~/.hermes/_Archives/skill-sync-fix-$TS; mkdir -p "$BK"
cp -a ~/.hermes/skills/<cat>/<name> "$BK/"
rm -rf ~/.hermes/skills/<cat>/<name>
ln -s ../../profiles/default/skills/<cat>/<name> ~/.hermes/skills/<cat>/<name>
```
После — повторно сверить версию в живом пути: совпадает с источником. Это восстанавливает канон «скилл = симлинк на workspace» и убирает источник будущих рассинхронов. Прецедент: `kanban-dev-pipeline-orchestration` и `cron-troubleshooting` жили реальными папками со старыми версиями; правка в canonical не достигала runtime до конвертации.

## Питфолл: `find -type d -name X` не проходит через симлинки — ложный NOT_FOUND

При локации скилла для правки не используй `find <root> -maxdepth N -type d -name "<skill>"` — он НЕ обходит симлинки и врёт «NOT_FOUND» про скиллы, которые существуют как симлинк на `~/hermes-workspace/skills/`. Это стоит времени, когда хочется снять размер/найти физический файл перед патчем.

**Правильный поиск — через файл, не директорию** (проходит сквозь симлинк):
```bash
find ~/hermes-workspace/skills ~/.hermes/skills -name SKILL.md -path "*/<name>/SKILL.md"
```
**Физический путь (readlink-разрешённый) для правки:**
```bash
readlink -f ~/.hermes/skills/<cat>/<name>/SKILL.md   # ведёт на ~/hermes-workspace/… = симлинк→git
readlink -f ~/.hermes/skills/<cat>/<name>/SKILL.md   # тот же путь = реальная папка вне git
```

**Корень НЕ единый:** большинство скиллов физически в `~/hermes-workspace/skills/`, но часть живёт реальной папкой ТОЛЬКО в `~/.hermes/skills/<cat>/` без симлинка в workspace (напр. `confluence-minutki-creation`). Искать по обоим корням и править по readlink-разрешённому пути, а не хардкодить workspace-путь заранее.

## Питфолл: autosync возвращает `.bak`-мусор, если `.gitignore` не ловит все формы разделителей

**Прецедент 15.08.2026:** `git rm --cached *.bak` + добавлены `*.bak` и `*.bak.*` в `.gitignore` — но следующий autosync СНОВА закоммитил и запушил `SKILL.md.bak-pre-merge-1`, `SKILL.md.bak-preopt-20260706-095241`.

**Причина:** имена содержат **дефис** после `.bak`, а шаблоны `*.bak` и `*.bak.*` ловят только точку/конец. Слепой `git add -A` в `autosync_github.sh` подхватывает их как новые файлы.

**Фикс `.gitignore`:**
```
# backups
*.bak
*.bak.*
*.bak-*
*.bak_*
*.bkp
_bak*
```

**Урок шире:** любой игнорируемый артефакт покрывать ВСЕМИ формами разделителя (`.`/`-`/`_`), иначе autosync вернёт его в следующем запуске. `git rm --cached` без корректного `.gitignore` проблему не решает — файл просто вернётся.

**Проверка:** `git ls-files | grep '\.bak'` → пусто; `git add -A && git status --short` → нет `.bak`-файлов в списке новых.

## Критический питфолл: autosync_github.sh стирает кастомные скиллы

**Симптом:** после `hermes update` или ночного автосинка кастомные скиллы исчезают из `hermes-workspace/skills/` и заменяются bundled-скиллами.

**Причина:** автосинк (`~/.hermes/scripts/autosync_github.sh`) содержал блок:
```bash
rm -rf skills
mkdir -p skills
cp -r "$HERMES_HOME/skills/." skills/
```
Этот блок удалял ВСЕ кастомные скиллы в workspace и заменял их содержимым `~/.hermes/skills/` (только bundled). Происходило каждую ночь в 2:00.

**Фикс:** заменить блок на вызов `restore-all-skills.sh`:
```bash
echo "[autosync] restoring skill symlinks to Hermes profiles..."
if [ -f "$WS/restore-all-skills.sh" ]; then
  bash "$WS/restore-all-skills.sh"
fi
```

Автосинк должен восстанавливать симлинки в Hermes ИЗ workspace, а не наоборот.

## Питфолл: hermes update перезаписывает skills/

`hermes update` перезаписывает директорию `skills/`, уничтожая все симлинки. Bundled skills остаются, кастомные пропадают.

**Защита:** ежедневный крон `restore-all-skills.sh` (в 3:00). Скрипт идемпотентный — повторный запуск не создаёт дубликатов, только чинит сломанное.

## Скрипты (все в ~/hermes-workspace/)

### sync-to-hermes.sh
Создаёт симлинки в профиле (default) из hermes-workspace.
- Идёт по всем `SKILL.md` в workspace
- Для каждого: если в профиле реальная директория (bundled) — пропускает
- Если симлинк с правильной целью — OK
- Если симлинк с неправильной целью — чинит
- Если ничего нет — создаёт симлинк
- Использование: `sync-to-hermes.sh [profile]` (по умолчанию default)

### restore-all-skills.sh
Мастер-скрипт восстановления после `hermes update`.
- Фактически вызывает `sync-to-hermes.sh default`
- Идемпотентный — безопасно запускать многократно

## Восстановление из бэкапа куратора

См. `references/skills-inventory.md` для полной процедуры и снапшота инвентаризации.

## Когда загружать этот скилл

- «скиллы потерялись / пропали»
- «где мои скиллы»
- «настроить / синхронизировать скиллы»
- «симлинки скиллов не работают»
- «восстановить скиллы после обновления»
- «аудит скиллов»
- «как синхронизировать скиллы»
- Любая работа с `hermes-workspace/skills/` и симлинками
- Изоляция внешних провайдеров (Honcho, MCP) между профилями — см. скилл `hermes-honcho-setup`

## Пошаговая верификация (правило Саши, 03.08.2026)

При выполнении многошаговых планов (восстановление, миграция, настройка):
- Выполнять **строго по одному шагу** → проверить результат
- **Нет ошибок** → следующий шаг
- **Есть ошибки** → стоп, сообщить Саше, НЕ продолжать
- Не выполнять все шаги подряд с финальным отчётом

**Прецедент:** при настройке симлинков между профилями шаг 4 (tz-dev→default) дал 74 битых симлинка из-за неверной формулы расчёта относительного пути. Если бы все шаги выполнялись подряд — ошибка была бы обнаружена только в конце. Пошаговая остановка позволила исправить формулу сразу. Детали tz-dev-архитектуры — `references/historical-tz-dev-architecture.md`.

## См. также

- `references/cron-multi-profile-pitfall.md` — кроны из non-default профиля: `cronjob` tool и `hermes cron run` не работают, ручной self-check через terminal.
- `references/autosync-bug-fix.md` — баг autosync, стирание кастомных скиллов.
- `references/historical-tz-dev-architecture.md` — архив: слой tz-dev, link-tzdev-to-default.sh, питфолл относительных путей.
- `references/architecture-implementation-2026-08-03.md` — детали реализации архитектуры (исторический снапшот).
- `references/skills-inventory.md` — инвентаризация скиллов и процедура восстановления из бэкапа (исторический снапшот).
