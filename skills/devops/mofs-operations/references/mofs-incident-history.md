

# Material moved from MOFS SKILL.md

> История исходника (даты указаны внутри), не текущая инструкция; актуальные условия — в SKILL.md.

## Питфоллы

- **Матчинг проектов — смотреть на тело summary, не только на название файла (22.07.2026).** Название встречи часто не содержит slug проекта. Читать тело (первые ~200 символов), выдвигать гипотезу, предлагать Саше. Прецеденты: «Daily» → `datatalks`, «Custom Agent Aralov» → `aralov_1on1`. В v1.0.0 закроется LLM-фолбэком при `projects=[]`.

- **Бриф по проектам — N называть ЯВНО до первого вопроса (22.07.2026).** Посчитать смысловые группы, объявить N: «1 из 8». «1 из N» без числа — нарушение, Саша указал явно. Порядок: частое+позднее → редкое+раннее.

- **⚠️ ФОРМАТ ВАРИАНТОВ В БРИФЕ — ТОЛЬКО ЧИСЛА 1/2/3, НИКОГДА НЕ A/B/C (22.07.2026).** Саша явно запретил буквенные варианты: «не удобно абц или abc — так неприемлемо». Каждый вариант под отдельным пронумерованным числом. Рекомендацию Opus — указывать явно: «Рекомендация: 1». Работает для всех брифов, не только MOFS.

- **Перед созданием новой сущности — проверить существующие aliases.** «ЦУ» → уже есть `cu` без русского alias. «ИИ-зация» → уже есть `ai_ready`. `entity-registry list | grep -i <ключевое слово>`. Добавить alias дешевле чем создавать дубль.

- **Опечатки в названиях файлов — добавлять alias с опечаткой.** Прецедент: «Мониториг конкурентов» (без «н») не матчил `parsing`. Решение: `entity-registry edit parsing aliases "мониториг конкурентов" --append -y` — единственный способ без правки оригинальных файлов.

- **`entity-registry add` — обязательные флаги (22.07.2026).** Команда `--aliases "a,b,c"` не работает — ошибка `unrecognized arguments`. Правильно: каждый alias отдельным `--alias "значение"`. Без `--parent-null` при kind=project будет `missing_required: parent`. Шаблон: `entity-registry add <slug> --kind project --display-name "..." --alias "алиас1" --alias "алиас2" --parent-null -y`

- **После изменений entities.json — всегда rematch + rebuild индекса.** Добавление aliases не даёт эффекта пока не запущен `mofs rematch --from X --to Y --bucket projects --yes` и `mofs-index index --rebuild --yes`. Встречи с уже проставленным `objects_version` не перематчиваются автоматически (до реализации авто-rematch по хэшу в v1.0.0).

- **Дубль reindex в mofs_run_cron.sh — архитектурный баг (22.07.2026).** Bash-скрипт вызывает `mofs-index index` (полный rebuild) после того как hook `reindex_batch` в pipeline.py уже сделал инкрементную переиндексацию. Лишний IO (~2-5с). Правильно: убрать `mofs-index index` из bash, добавить отдельный weekly-крон (воскресенье) для full-reindex как safety net.

- **Задним числом alias не срабатывает без rematch.** После добавления alias в entities.json встречи с уже проставленным `objects_version` НЕ перематчиваются автоматически. Нужен явный `mofs rematch --bucket projects --from X --to Y --yes`. Auto-rematch по хэшу entities.json — запланировано (MOFS backlog), не реализовано.

- **backfill-contacts — порядок источников:** сначала `--sources det` (S1+S2, детерминированные, нулевой риск) → apply по всему архиву → даёт 91% покрытие (468/514). Потом отдельно `--sources s3 --only-empty-contacts` (Haiku) только для файлов где S1+S2 не дали результата (~48 файлов). S3 не запускать по всем 514 — избыточно. S3 требует ручной сверки ~10 файлов перед массовым apply.
- **backfill vs rematch:** `mofs backfill-contacts` — для архива старого формата (без раздела «Участники»). `mofs rematch --bucket contacts` — для встреч нового формата (есть раздел «Участники»). Не путать.
- **Бэкап перед массовым прогоном — только `full-workvault-backup`**, не `mofs bootstrap --snapshot`. Bootstrap-снапшот фиксирует только MOFS-реестр (не содержимое файлов WorkVault), не подходит как полный бэкап. Правильно: `bash ~/.hermes/scripts/full_workvault_backup.sh` перед этапами 2 и 5. Прецедент 21.07.2026: был создан bootstrap-снапшот → Саша явно исправил на full-workvault-backup.
- **Contacts plain-text заголовок (КРИТИЧНО v0.8.2):** MoveFromFF генерирует ТРИ формата заголовков секций — все три должны распознаваться `_extract_section`:
  1. `## Участники:` — markdown H2 (~36 файлов)
  2. `**Участники:**` — bold (~23 файла)
  3. `Участники:` — plain-text без разметки (~24 файла)
  При contacts = [] у части встреч — проверять формат заголовков: `grep "Участники" file.md`. В text_extractor.py добавлен `_SECTION_PLAIN = re.compile(r"^([А-ЯЁA-Z][А-Яа-яЁёA-Za-z ]{2,30}):\s*$", re.MULTILINE)`.
  **Ограничение `_SECTION_PLAIN`:** паттерн требует заглавной буквы + 2-30 символов + двоеточие без текста после — чтобы не съедать строки-исполнители типа `Скворцова Диана: задача`.
- **editable install namespace-package ловушка:** `pip install -e .` с `[tool.setuptools.packages.find] include = ["pkg*"]` может создать namespace-package вместо regular-package — `__init__.py` не выполняется, публичный API недоступен. Симптомы: `pkg.__file__ is None`, `ImportError: cannot import name 'func' from 'pkg'`. **Фикс:** заменить `packages.find` на явный `[tool.setuptools] packages = ["pkg"]` и переустановить. Прецедент: mofs_index 21.07.2026.
- **unmatched_candidates замусоривание:** если unmatched_candidates.json > 500 записей на 60 встреч — значит служебные слова (Саммари, Участники, Решения, Блокеры, высокая, среднее…) попадают в кандидаты. Добавить `_SECTION_STOPWORDS` в text_extractor.py и фильтровать в resolve_contacts перед матчингом.

- **⚠️ MOFS генерирует `## Секция` (без двоеточия) — было несовместимо с PFS (28–29.07.2026, РЕШЕНО).** MOFS записывает заголовки как `## Участники`, `## Задачи` и т.д. (markdown H2, без двоеточия). До 29.07.2026 `summary_parser.py` в PFS требовал двоеточие в конце → секции не найдены → PFS публиковал пустую строку. **Системный фикс реализован 29.07.2026** — в `summary_parser._find_sections()` строка 130 расширен regex: двоеточие стало опциональным (`[^:\\n]*:?` вместо `.*:`). Теперь оба формата (`Участники:` и `## Участники`) парсируются корректно. Если снова появляются пустые протоколы — проверить `grep "## Участники\|Участники:" <summary>.md` и убедиться что `summary_parser.py` строка 130 содержит `[^:\\n]*:?`.

- **Smoke-test dry-run:** `mofs run --meeting-id X --dry-run` → проверить `mtime` файла до/после.
  Если изменился — dry-run сломан, не запускать на архиве.
- **Диагностические задачи:** `enabled_toolsets: ["file"]` (без terminal).
  Команду передавать ДОСЛОВНО с `--dry-run`.
- **Alias для коротких аббревиатур** — только с точкой (startswith), не substring.
- **entities.json** — только через `entity-registry` CLI, не вручную.
- **Сущность без блока `pfs` не попадает в PFS ROUTES.** `_load_routes_from_registry()` пропускает записи без `pfs` — встреча уходит в fallback «неразобранное» даже если alias совпадает. Фикс: добавить `pfs: {page_id: "...", tag: "ИМЯ."}`. Прецедент 28.07.2026: OKR-встреча не резолвилась — у сущности `okr` был alias, но не было блока `pfs`.
- **Fallback `vstrechi_nerazobrannoe` обязан присутствовать в entities.json.** Если запись отсутствует — при любом fallback в PFS будет `KeyError: 'vstrechi_nerazobrannoe'`. Симптом в отчёте PFS: `error: 'vstrechi_nerazobrannoe'`. Прецедент 28.07.2026.
- **⚠️ Расширение aliases → PFS публикует старый архив (22.07.2026).** При добавлении новых aliases к PFS-сущностям в entities.json — старые встречи (до CUTOVER_DATE) начинают матчиться на ROUTES PFS. Если их нет в реестре PFS — `process_pending` публикует как новые. Перед масштабным добавлением aliases: `grep -rl "<новый alias>" ~/WorkVault/Meetings/NewMeetings/*summary* | wc -l`. При наличии CUTOVER_DATE guard в PFS pipeline.py (с 22.07.2026) — встречи до 2026-07-10 защищены автоматически.

- **MOFS v1.0.0 (22.07.2026): LLM-фолбэк + авто-rematch реализованы.** При `projects=[]` после regex → LLM (конфиг `~/.hermes/config.yaml`, OpenAI-клиент к шлюзу; last-resort `LLM_FALLBACK_*`) классифицирует по entities.json (threshold=0.90). Low-confidence → `mofs_unmatched.md`. При изменении entities.json → авто-rematch по SHA-256 хэшу файла. Ежедневный full-reindex — крон `mofs_index_rebuild` (23:00, job: 7e013cd5c6f9). Скрипт: `~/.hermes/scripts/mofs_index_rebuild.sh`.

- **idempotency при contacts rematch:** `run` пропускает уже обработанные встречи.
  Для перепрогона только contacts — `mofs rematch --bucket contacts --from X --to Y --dry-run`.
- **cwd не важен** — с v0.7.0 `.env` читается по абсолютному пути из `config.py`.
  Крон можно запускать из любой директории.
- **Порядок поштучного ревью dry-run:** сначала dry-run → поштучный разбор проблем → фикс aliases → повторный dry-run → реальный прогон. Не торопиться к реальному прогону.

- **⚠️ MoveFromFF иногда возвращает Bullet points вместо Custom Summary (28.07.2026).** Симптом: summary содержит только `## Bullet points` + `## Notes` без секций `Участники:/Задачи:/Решения:`. Причина: Custom AI Skill в Fireflies не вернул output для встречи. PFS публикует пустую строку в протокол. Диагностика: `grep "## Bullet" <summary>.md` — если есть, Custom Skill не сработал. Решение — принудительный refetch: (1) найти meeting_id из `_registry_meet.json` по title, (2) удалить запись из registry, (3) удалить файл summary, (4) `python3 -m movefromff --mode manual --meeting-id <id> --no-tg --verbose`, (5) проверить `## Участники:`, (6) republish через PFS с `--confirm-republish`.

- **⚠️ Диагностика "skipped=N, processed=0" при ручном запуске (28.07.2026).** Если `mofs run --from X --to Y` возвращает `skipped=N` для встреч у которых внешне frontmatter кажется пустым или неполным — это означает что реестр `~/USERTOOLS/AnywhereContacts/_mark_objects_registry.json` уже содержит запись с `objects_version=0.6.0` (крон отработал раньше). Диагностика:
  ```python
  import json
  with open('/home/tkachenkoav/USERTOOLS/AnywhereContacts/_mark_objects_registry.json') as f:
      reg = json.load(f)
  meeting_id = '2026-07-28 12-30-00 Название'
  entry = (reg.get('meetings') or {}).get(meeting_id, {})
  print('objects_version:', entry.get('objects_version'))
  print('processed_at:', entry.get('processed_at'))
  ```
  Если `objects_version` совпадает с `OBJECTS_VERSION` в `pipeline.py` (сейчас `0.6.0`) — встреча уже обработана, skipped — норма. Frontmatter при этом уже корректный.
  Для принудительного перепрогона: `mofs rematch --meeting-id "..." --bucket all`.

