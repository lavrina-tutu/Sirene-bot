# upstream/ — трекинг NousResearch/hermes-agent

Это **метаданные**, не код. Сам клон upstream живёт отдельно:
`~/Documents/Cursor_projects/hermes-agent`.

## Файлы

- `pinned-version.txt` — commit/тег, на котором сейчас работает Hermes у Саши.
- `changelog.md` — ручные заметки по релевантным изменениям upstream при каждом апдейте.
- `rollback-history.txt` — лог предыдущих pin'ов для возможного отката.

## Процедура обновления

```bash
bash scripts/upstream_update.sh
```

Скрипт:
1. Сохраняет текущий HEAD клона в `rollback-history.txt` как `prev`.
2. Бэкапит `pip freeze` в `upstream/pip-freeze-before-<date>.txt`.
3. Фетчит upstream, показывает diff-log, делает `git pull --ff-only`.
4. Обновляет `pinned-version.txt` (commit, tag, date, prev).
5. Пересобирает venv (`pip install -e . --upgrade`).
6. Smoke-тестит: `hermes --version`, `hermes doctor`.

## Откат

```bash
bash scripts/upstream_rollback.sh
```

Читает `prev:` из `pinned-version.txt`, делает `git checkout <prev>` в клоне hermes-agent и переустанавливает зависимости.

## Когда обновляться

- **Раз в неделю** (вс 04:00 MSK) — через cron-задачу.
- Срочно — при security-фиксах upstream (нужно следить за релизами).
- НИКОГДА — внутри активного рабочего дня без бэкапа `pip freeze`.

## Что НЕ делать

- Не превращать клон hermes-agent в submodule этого репо: при апдейте submodule reference надо коммитить, и Hermes сам не сможет себя обновлять.
- Не форкать upstream без необходимости: мы не патчим код, только конфиг и скиллы.
