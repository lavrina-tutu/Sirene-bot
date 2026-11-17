# env-утечка TOOL_DIR/LOGS_PATH → «убегающий» реестр инструмента (17.08.2026)

## Симптом
Реестр/состояние инструмента в `~/USERTOOLS/*` пишется не в свою папку, а «переезжает» между
соседними тулами. У MOFS (`_mark_objects_registry.json`) нашли 3 блуждающие копии:
- `MarkObjectsFromSummary/_mark_objects_registry.json` — родная, устаревшая (до 21.07, 60 встреч)
- `AnywhereContacts/_mark_objects_registry.json` — была до 14.08 (634 встречи)
- `ConfluenceSync/_mark_objects_registry.json` — актуальная (635 встреч)

## Причина
В **общий** секрет-файл `~/.hermes/profiles/default/.env` при настройке ConfluenceSync ошибочно
дописали generic-переменные:
```
TOOL_DIR=/home/tkachenkoav/USERTOOLS/ConfluenceSync
LOGS_PATH=/home/tkachenkoav/WorkVault/_meta/ConfluenceSync
```
`pydantic-settings` даёт **приоритет `os.environ` над локальным `.env`** инструмента → `tool_dir`
(а от него `registry_path`/`lock_path`/`logs_path`) резолвится не в свою папку, а в ту, на которую
в данный момент указывает утёкшая переменная (последний тул, чьи значения дописали).

## Наблюдение: разметка сама по себе НЕ ломается
Даже при «убежавшем» реестре инструмент продолжал корректно размечать встречи (фронтматтер
записывался штатно, mtime совпадал с логом крона). Ломалась только внутренняя бухгалтерия
(реестр/лог/idempotency) — создавались дубли и риск future `rematch`. Поэтому визуальное ощущение
«инструмент не сработал» может быть ложным: проверять сам артефакт-результат, а не только реестр.

## Диагностика
```bash
grep -E "TOOL_DIR|LOGS_PATH" ~/.hermes/profiles/default/.env    # утечка в общем файле
env | grep -E "TOOL_DIR|LOGS_PATH"                               # реально «течёт» в процессы
find ~/USERTOOLS -name "_mark_objects_registry.json" 2>/dev/null # блуждающие копии
# подозрение: в .env инструмента стоит своя env_file, но os.environ перекрывает её
```

## Фикс
1. Убрать `TOOL_DIR`/`LOGS_PATH` из общего `~/.hermes/profiles/default/.env` (бэкап перед правкой,
   оставить поясняющий комментарий).
2. Вернуть корректные `TOOL_DIR`/`LOGS_PATH` в `.env` конкретного инструмента, если нужны.
3. Слить блуждающие копии в канонический файл инструмента:
   - дедуп по ключу (`meeting_id` / ключ `meetings`-словаря);
   - при коллизии брать запись с max `processed_at` (свежайшую);
   - бэкап ВСЕХ копий в `_backup_<tool>_remerge_<ts>/`;
   - атомарная запись (tmp + os.replace), сохранить `schema_version`/`entities_hash` из актуального;
   - удалить осиротевшие копии и `.mofs.lock` из чужих папок (в родной — не трогать).
4. Профилактика: уникальные имена переменных (`MOFS_TOOL_DIR`) или `load_dotenv(override=True)`
   в самом пакете, чтобы процессный `os.environ` не перекрывал локальный `.env`.

## Проверка после фикса
- `grep TOOL_DIR ~/.hermes/profiles/default/.env` → пусто (кроме комментария).
- Итоговый канонический реестр `len(meetings)` == размеру объединения всех копий (не меньше
  max из копий: 60∪634∪635 → 635).
- Встречи в `~/WorkVault/Meetings/NewMeetings/` не тронуты; `mofs run/rematch` не запускались.

## Процесс слияния через Cursor (проверено)
Задачу слияния реестров передавать исполнителю (composer-2.5) с жёстким требованием вернуть
**сырой вывод команд** (`ls -la`, `len(meetings)`, `head -c 400`), а не self-report — и после
возврата самостоятельно проверить на диске (число записей, присутствие ключевой встречи,
равенство результата объединению бэкапов).


## Historical source (superseded where it conflicts with SKILL.md; not current instruction)

## Питфолл 1: «убегающий» реестр/состояние → env-утечка TOOL_DIR/LOGS_PATH

Симптом: реестр инструмента пишется не в свою папку, а «переезжает» между соседними
`~/USERTOOLS/*`. Причина — в **общий** `~/.hermes/profiles/default/.env` по ошибке попали
generic-переменные `TOOL_DIR`/`LOGS_PATH` от другого тула. `pydantic-settings` даёт приоритет
`os.environ` над локальным `.env`, поэтому `tool_dir` (→ registry/lock/logs) утекает в чужую папку.

**Диагностика:**
```bash
grep -E "TOOL_DIR|LOGS_PATH" ~/.hermes/profiles/default/.env
find ~/USERTOOLS -name "_mark_objects_registry.json" 2>/dev/null   # блуждающие копии
# ВАЖНО: если .env чист, но в живом процессе env всё ещё есть — источник выше по цепочке:
env | grep -E "TOOL_DIR|LOGS_PATH"            # что реально видит процесс
grep -nE "TOOL_DIR|LOGS_PATH" ~/.bashrc ~/.bash_profile ~/.profile   # login-shell
tr '\0' '\n' < /proc/<pid>/environ | grep -E "TOOL_DIR|LOGS_PATH"    # родитель/сессия
systemctl --user show-environment | grep -E "TOOL_DIR|LOGS_PATH"     # systemd-user
```
**Фикс:** убрать утёкшие переменные из общего `.env` → вернуть их в `.env` конкретного тула →
слить блуждающие копии реестра в канонический (дедуп по ключу, при коллизии брать запись с max
`processed_at`, бэкап копий, атомарная запись tmp+os.replace, удалить осиротевшие `.mofs.lock`).
**Питфолл 1а (НЕОБХОДИМО): чистки только общего `.env` НЕДОСТАТОЧНО.** Это было уже сделано 17.08,
но реестр продолжал «убегать»: generic-переменные пережили чистку, т.к. лежали в живом окружении
долгоживущего процесса/сессии (источник выше .env-файла). Поэтому структурная профилактика —
**обязательна**, а не опция: уникальные имена (`MOFS_TOOL_DIR`/`MOFS_LOGS_PATH`) или
`load_dotenv(..., override=True)` в пакете, чтобы локальный `.env` тула имел приоритет над чужими
generic-переменными процесса. После фикса перепроверить в СВЕЖЕЙ сессии и в контексте крона
(не в текущей, где переменная могла «зависнуть»). Подробности: `references/env-leak-registry-merge-20260817.md`.
