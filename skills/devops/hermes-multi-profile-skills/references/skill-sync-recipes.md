Source recipes: check each step and both link layers; do not run restore merely to verify documentation.

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

