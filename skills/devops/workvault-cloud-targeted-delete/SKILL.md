---
name: workvault-cloud-targeted-delete
description: "Use when синк облака блокируется симлинками."
version: 1.0.0
author: Sirene
license: MIT
platforms: [linux]
metadata:
  hermes:
    tags: [WorkVault, rclone, ownCloud, webdav, cleanup, sync]
    related_skills: [workvault-sync-infra, workvault-sync, workvault-entities]
---

# WorkVault cloud (ownCloud) — targeted delete when full sync is blocked

Аварийный, но безопасный способ убрать конкретные файлы/папки из облака ownCloud, когда штатный `owncloud-sync.service` падает и потому не доезжает до облака.

## Когда это нужно

`systemctl --user start owncloud-sync.service` вернул rc≠0, логи `~/.local/share/hermes/logs/owncloud-sync.log` набиты ERROR вида:

```
Can't follow symlink without -L/--copy-links
not deleting files as there were IO errors
```

**Механизм блокировки:** в `Hermes-Backlog/dev/**` лежат сотни симлинков (артефакты тестовых basetemp dev-workflow HF). rclone не умеет писать симлинки в webdav → IO-errors при копировании → rclone из-за этого отказывается делать ЛЮБЫЕ удаления в облаке («not deleting files as there were IO errors» — защита от потери данных). Признак: локально файл удалён/изменён, но облако не обновилось.

## Правило scope: sync vs точечные операторы

Запрет «не запускать rclone руками» относится к **реконсиляции** (`rclone sync`), её деструктивная слепая сторона стирает всё, что не покрыто exclude-списком. Он НЕ запрещает точечные операторы по точным путям:

- `rclone deletefile "owncloud:WorkVault/<точный путь/файл>"` — один файл
- `rclone purge "owncloud:WorkVault/<точный путь/папка>"` — целиком известная папка (namespace верхнего уровня): например папка-карточка сущности

Эти операторы действуют только на названный объект, расширить scope не могут. Использовать их можно только с точным путём, никогда по wildcard/префиксу.

## Процедура точечного удаления из облака

1. **Собери манифест локальных путей** к удалению (папки-карточки `Entities/<slug>/` целиком + файлы встреч).
2. **Бэкап ДО удаления** — скопируй всё, что предстоит удалить, в `~/WorkVault_backup/<имя>-<ts>/` с сохранением относительной структуры и запиши манифест в `_REMOVED.txt` (для возможного отката). Если владелец явно сказал «без восстановления» — этот шаг ПРОПУСТИТЬ: создание копии противоречит императиву необратимости и оставляет след удаляемого.
3. **Удаляй файлы из облака** по одному `rclone deletefile "owncloud:WorkVault/<rel>"`. Пустые папки-карточки — `rclone purge "owncloud:WorkVault/Entities/<slug>"`.
4. **Не забудь теневые файлы в облаке**, которых нет на ВМ (только на облаке, нигде локально): просканируй целевые ветки через `rclone lsf owncloud:WorkVault/... --recursive` и удали совпадения по имени/алиасу. Иначе после «успешной» чистки в облаке останется мусор.
5. **Верифицируй**: повторный `rclone lsf` той же ветки с паттерном сущностей дал 0 совпадений. Ошибка `directory not found` при повторном листинге — НЕ ошибка, а подтверждение, что `purge` уже убрал папку.

## Питфоллы

- **rclone deletefile не берёт папки** — папку (даже пустую после удаления файлов) убирает только `rclone purge`.
- **Симлинки блокируют синк — чинится чисткой артефактов, не точечными удалениями.** root-cause: сотни симлинков в `Hermes-Backlog/dev/**` (слепки тестов dev-workflow HF: `evidence/HF-impl-*-runtime`, `basetemp`, `_backup_pre_impl`, `.venv`) → rclone «not deleting … there were IO errors». Устранение проверено в проде: удалить сами каталоги-«ложки» симлинков (родитель каждого `os.path.islink`), а не точечно чистить облако:
  ```python
  for root,dirs,files in os.walk(V, followlinks=False):
      for d in list(dirs)+list(files):
          p=os.path.join(root,d)
          if os.path.islink(p): dirs_to_del.add(os.path.dirname(p))
  for d in dirs_to_del: shutil.rmtree(d)   # только подкаталоги, НЕ top-level файлы/документы
  ```
  Проверка: `find …/WorkVault -type l | wc -l` == 0, затем штатный синк проходит без симлинковых ERROR. Эти каталоги — мусор тестовых прогонов, удаляются безвозвратно (по договорённости Саши «удали без восстановления»).
- **Не запускать синк параллельно** — `rclone sync` из таймера + ручной `systemctl start` дают гонку двух процессов, второй падает на `error reading source directory: directory not found` на только что удалённых каталогах (ложный сигнал «сломан синк»). Один экземпляр на один прогон; при подозрении на гонку — `systemctl --user stop` + дождаться завершения, перед перезапуском.
- **Первый полный синк после долгого простоя идёт долго** — сервис логирует на NOTICE (построчной передачи не видно, это НЕ зависание), держится циклами таймера и статусом `activating`, пока большой diff не досчитается. Не убивать по таймауту; лог растёт — признак живой работы.
- **В логе большой старый хвост**, таймстемпы вводят в заблуждение — фильтруй по релевантным ERROR-строкам (`Can't follow symlink`, `not deleting files`), а не по «последним строкам».
- **Прежде чем удалять из облака конкретные встречи** — убедись, что у Саши стоит именно задача удаления (для чистки архива это прямой императив).
- **`RCLONE_TIMEOUT` без единицы валит ВСЕ вызовы rclone** — переменная требует duration с единицей (`RCLONE_TIMEOUT=20s`), голое число (`=20`) даёт CRITICAL на каждой команде и пустой вывод, который легко принять за «уже удалено». Ограничивать время через обёртку `timeout 60 rclone ...`, а не переменную окружения.

## Related

- `workvault-sync-infra` — диагностика инфраструктуры синка; сюда этот скилл должен быть объединён при консолидации
- `workvault-sync` — триггер синка
- `workvault-entities` — структура Entities, удаление сущностей
