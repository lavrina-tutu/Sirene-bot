# autosync_github.sh bug — root cause & fix

## Original buggy block (до 03.08.2026)

```bash
echo "[autosync] mirroring skills..."
if [ -d "$HERMES_HOME/skills" ]; then
  rm -rf skills
  mkdir -p skills
  cp -r "$HERMES_HOME/skills/." skills/
  find skills -name '__pycache__' -type d -exec rm -rf {} + 2>/dev/null || true
fi
```

**Что делал:** удалял все скиллы в `hermes-workspace/skills/` и заменял содержимым `~/.hermes/skills/` (только bundled skills, ~70 шт). Запускался каждую ночь в 2:00 через крон `5d16b96a9ed5` (`autosync_full_with_cleanup.sh`).

**Результат:** 150 кастомных скиллов → 70 bundled. Git-репо терял 80 скиллов каждый день. 03.08.2026 `hermes update` перезаписал `~/.hermes/skills/` → автосинк скопировал новый набор bundled → кастомные скиллы исчезли из git.

## Fixed block

```bash
echo "[autosync] restoring skill symlinks to Hermes profiles..."
if [ -f "$WS/restore-all-skills.sh" ]; then
  bash "$WS/restore-all-skills.sh"
fi
```

**Что делает теперь:** восстанавливает симлинки в профилях Hermes ИЗ workspace, а не наоборот. Направление данных: workspace → Hermes, не Hermes → workspace.

## Хронология восстановления (03.08.2026)

1. Обнаружено: 132 скилла в бэкапе куратора 29.07 vs 74 в tz-dev
2. Найдено: `hermes-workspace` всё ещё содержит 132 скилла (git)
3. Добавлено 18 скиллов из `hermes-config` → 150 total
4. Созданы скрипты симлинков
5. Настроен default (143 симлинка) и tz-dev (74 симлинка)
6. Исправлен `autosync_github.sh`
7. Поставлен крон `restore-skills-daily` (3:00 ежедневно)

## Historical source excerpts (not current instructions)

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


## Канон направления синка WorkVault ↔ hermes-workspace

**`restore-all-skills.sh` синхронизирует ТОЛЬКО симлинки скиллов.** Он НЕ должен копировать ничего в WorkVault (ТЗ, entities.json) — направление синка ТЗ/данных-графа строго **WorkVault → git**, единственная точка — `~/.hermes/scripts/autosync_github.sh` (крон 02:00). WorkVault = источник правды, git-зеркало (`hermes-workspace/Hermes-Backlog`) = бэкап.

Обратное (`git → WorkVault`) в `restore-all-skills.sh` или любом крон добавлено быть не должно: это откатывает дневные правки ТЗ старым зеркалом. Прецедент 16.10.2026 — блоки `cp` зеркало→WorkVault откатили ProtocolFromSummary v1.29.0 → v1.28.1; удалены.

