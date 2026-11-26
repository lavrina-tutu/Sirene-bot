---
name: hermes-migration-archive
description: "Use when перенос Hermes-агента целиком на другую машину."
version: 1.0.0
author: Sirene
license: MIT
platforms: [linux, windows]
metadata:
  hermes:
    tags: [hermes, migration, backup, archive, restore]
    related_skills: [full-workvault-backup, tool-handoff-package, hermes-managed-install, workvault-outbox]
---

# Hermes Migration Archive — полный перенос агента на другую машину

## Когда применять

Триггеры: «перенести Hermes на другую машину», «сделать архив агента чтобы развернуть», «бэкап всего что кастомизировано». Отличать от `full-workvault-backup` (только ~/WorkVault в локальную backup-папку) и `tool-handoff-package` (один скилл/инструмент). Здесь — ЕДИНЫЙ архив данных всего агента, без дистрибутивов, для развёртывания приёмным Hermes-агентом.

## Ядро задачи

~/.hermes занимает ~19G, но данные (что переносить) — лишь малая часть; остальное — бинарные дистрибутивы, managed-workspace/venv и старые снапшоты. Саша требует: **только данные, один файл, без дистрибутивов, без неактуальных архивов**. Hermes-код и бинарные окружения на приёмной машине ставятся штатно (`hermes update`/`install`) — в архив их НЕ класть.

## Критерий «что есть данные»

**Включать** (конфиг, БД, кастомные скиллы, наши тулзы, Obsidian):
- `~/.hermes`: config.yaml, .env (токены/секреты — критично, без них подключения мертвы), SOUL.md, HERMES.md, handover.md, skills/, profiles/, profiles-backup/, state.db, sessions/ + sessions.db, kanban.db + kanban/, projects.db, shared-state.db, verification_evidence.db, cron/ (jobs.json + executions/deliveries/notepad .db), memories/, error_bus/events.db, mcp-tokens/, platforms/, plugins/, scripts/, channel_directory.json, google_token.json, google_client_secret.json, honcho.json, auth.json, worker-outboxes/, pii_scan/
- `~/USERTOOLS/*` — кастомные тулзы (исходники + конфигурацию + registry; исключить venv/node_modules/__pycache__ каждого тула и подпапки `_backup_*`)
- `~/hermes-workspace` — git-репозиторий наших скиллов + config + restore-all-skills.sh, sync-to-hermes.sh (исключить `_bak-*`, `_bak-tzdev-*`)
- `~/WorkVault` — Obsidian vault целиком

**Исключать** (неархив/мусор): `~/.hermes/_Archives/` (старые снапшоты гермеса), `tools/` (все бинарники: ffmpeg, python-интерпретаторы, chromium, node, npm, uv, ripgrep), `installs/` (managed-workspace, venv), `cache/`, `node/`, `lsp/`, `bin/`, `logs/`, `hook_outputs/`, `environments/`, `qwen-fast/`, `haiku-fallback/`, `gateway.sock/pid/lock`, `state.db-wal/shm`, `test_kanban_*`, `tmp_*.py/json`, все `*.bak*`, `_backup_*`, `_bak-*`.

Полная по-путевая карта инвентаря — `references/data-map.md`. Параллельная доводка плана/ТЗ независимым ревизором (цикл REQUEST-CHANGES) — `references/plan-review-loop.md`.

## Порядок работы

1. **Снять фактуру первым делом (read-only)**, до любых решений: `du -sh ~/.hermes/*`, `ls ~/.hermes`, `du -sh ~/USERTOOLS/* ~/hermes-workspace/* ~/WorkVault 2>/dev/null`. Каталоги-распухоловки (tools/, installs/, _Archives) сразу видно по размеру и имени — это дистрибутивы/снапшоты, не данные.
2. **Решить состав по критерию выше**, показать Саше списком «включать/исключать» с размером до/после сжатия. Саша сверяет состав перед сборкой (живые артефакты, не обещания).
3. **Разовую архитектурную задачу** («придумать план бэкапа и восстановления») отдать архитектору вне dev-workflow через Codex — см. ниже.
4. **Собрать staging вне WorkVault** (напр. `/var/tmp/hermes-export-<id>/`, `0700`): state.db и остальные активные БД снять sqlite `.backup` ДО rsync; обычные файлы копировать `rsync -a` (НЕ cp, живой агент пишет) с exclude-списком дистрибутивов/мусора/`cron/output`/`external-workers`. Потом `tar --use-compress-program=pigz -cf` из staging.
5. **Доставка в облако и сверка по sha256** — по скиллу `workvault-outbox`: `systemctl --user start owncloud-sync.service`, затем не `lsjson` размером, а скачать облачную копию и сверить `sha256` с локальным (не верить exit 0). Папка `~/WorkVault/Hermes-Archive/` уходит в ownCloud штатным пушем.

## Развёртывание на новой машине (план переезда, когда цель — НОВЫЙ основной инстанс)

Когда «перенести» = развернуть новый инстанс и переехать на него (≠ просто собрать архив), план закрывает три контура и подчиняется правилам ниже.

### Правило целостности
На исходной машине **ничего не выключать и не трогать** до полной приёмки нового инстанса — старый остаётся страховкой для отката (30 дней минимум). Кроны нового инстанса активируются только по явному «ставь кроны», иначе задвоятся с исходными расписаниями. Telegram-бот: не переносить токен на новый инстанс, где уже работает другой бот (два poller'а на один токен роняют gateway) — решить «новый бот» vs «тот же», иначе конфликт.

### Принцип «актуальное vs история» (требование Саши при переезде на новый основной инстанс)
Переезжает **только актуальное рабочее состояние**; вся **история разработки остаётся на исходной машине** (она — бессменный архив). Считать «историей» и явно исключать: `Hermes-Backlog/dev/**` (dev-кейсы по доработке инструментов), `Hermes-Backlog/TZ/**`, `research/**`, `_research/**`, все протоколы/журналы/decision-log/черновики/старые версии, `_Archives/**`, `_bak-*`, `_backup_*`. Разделение — на уровне каталогов ещё на исходной машине (исключающий список), а не «перенести всё, потом чистить». Обязательная проверка на этапе сборки: `tar -tzf <архив> | grep` на запрещённые пути ДО доставки.

**Скиллы — это НЕ история, они переезжают целиком.** Все актуальные навыки (SKILL.md + `references/` + `scripts/`) едут на новый инстанс: процессные (`dev-workflow`, `hermes-feature`, `tz-workflow` + их `references/canon.md`, `context.md`, `invoke.md`),инструментальные (`workvault-rag`, `mofs-operations`, `pfs-*`, `ecosystem-manifest-ops` и весь активный набор) — иначе агент на новой машине теряет повседневную механику (pipeline, роли, гейты). Вместе со скиллом `dev-workflow` переносится **актуальная версия master-норматива** `TZ/DevWorkflow/DevWorkflow_TZ.md` (одна версия-норма, не история правок), и путь в скилле/каноне переправляется на новое расположение — иначе ссылка «при расхождении» ведёт в пустоту. Не переезжает только история разработки скиллов: dev-кейсы, черновики, старые версии, `_bak-*`.

**Внутри самих скиллов исключать их же implementation-историю:** `references/implementation/**` (отчёты/evidence/acceptance артефакты реализации вроде `edit-plan-confluence/references/implementation/20261116/...` — до 2 ГБ), `.curator_backups/**`, `.hub/**`. SKILL.md + актуальные `references/` (не implementation) + `scripts/` + `tests/` — это всё, что нужно новому инстансу. Проверять размер каждого каталога скиллов (`du -sh <skills>/*`) до упаковки: распухоловка в одном навыке значит именно такой мусор, а не «скилл такой большой».

### Две независимые git-ветки навыков (исходная и новая машина живут раздельно)
Когда на новой машине окно навыки развиваются независимо (не копируются бесследно), в `hermes-workspace` держатся **две постоянные ветки**: исходная машина работает на своей текущей ветке (напр. `main`, Linux/ВМ — не трогается с новой), новая машина — на **отдельной постоянной ветке** (напр. `windows`). Правила: новая машина пушит только в свою ветку; входящая ветка исходной машины с неё не правится; **автоmerge запрещён** — слияние веток только по явному решению Саши и по одному навыку (cherry-pick), расхождение веток это норма (независимое развитие), а не ошибка. Это независимая линия навыков продолжает жить по (пункту про актуальные скиллы) на каждой машине. Код Hermes при этом общий (апстрим/форк), под платформы не форкается.

### Три контура переноса (не смешивать)
1. **Код** — НЕ переносим, ставим штатно: upstream `github.com/NousResearch/hermes-agent` даёт актуальную версию; наш форк `github.com/ialextkachenko-byte/hermes-agent` — рабочая сборка с кастомизациями. Всегда указывать оба репозитория в плане.
2. **Навыки** — клонируем `github.com/ialextkachenko-byte/hermes-workspace` (git — источник истины наших скиллов + config + `restore-all-skills.sh`), затем `hermes skill validate`. Пути `/home/<user>` в скиллах чинить развязкой через `~`/переменные окружения.
3. **Инструменты (USERTOOLS + MOFS + PFS + OFC + ЭкоКонфиг)** — переносим **ДАННЫЕ** (исходники + `.env` + БД/state, БЕЗ venv/node_modules/__pycache__), зависимости ставим заново (venv + `pip install -r requirements.txt`), затем **smoke-test каждого тула**. После переноса БД **пересобрать MOFS-индекс** (`mofs_index_rebuild.sh`) и проверить регистр-инструменты в `~/WorkVault/Registries/` (EcosystemConfig.yaml, EcosystemManifest.*, entities.json) — каталог сущностей строится заново.

### Windows (native, без WSL): раскладка и питфоллы приёмки

Когда приёмная машина — Windows, ставить штатно `iex (irm https://raw.githubusercontent.com/NousResearch/hermes-agent/main/scripts/install.ps1)` (вместо `hermes-agent.nousresearch.com/install.ps1`, который может вернуть Forbidden). Дом Hermes на Windows — `%LOCALAPPDATA%\hermes` (напр. `C:\Users\<user>\AppData\Local\hermes`), НЕ `C:\Users\<user>\.hermes`. Раскладка из payload: конфиг переходит в `config.yaml` и `profiles/default/.env` домена, `MEMORY.md`/`USER.md` → `memories/`, `jobs.json` → `cron/`, скиллы → `profiles/default/skills/`, `USERTOOLS/WorkVault/hermes-workspace` → корень профиля пользователя (`C:\Users\<user>\`). После раскладки контроль `hermes doctor`: разделы `Configuration Files` и `Memories` должны показывать наличие, число категорий скиллов — по `Get-ChildItem ... skills -Directory | Measure-Object`. `hermes doctor` про `Skills Hub`/`OpenRouter not configured` — норма (маркетплейс не нужен), не чинить.

**Питфоллы Windows-раскладки:**
- **Hermes Desktop (v0.23.x) умеет НЕСКОЛЬКО параллельных сессий-вкладок — штатный аналог топиков Telegram.** Отдельная вкладка (`new-session-tab`/`close-tab`/`compact-tab-menu`/`virtual-session-list` в `apps/desktop/src/app/chat`) = отдельный разговор по задаче, как поток группы. Это НЕ потоки Telegram с автомаршрутизацией по номеру треда: разговор разрешается по вкладке, а не по внешнему идентификатору. Для решения «работать с локала через Desktop вместо бота/Telegram» топики пригодны — вкладка на задачу, `--resume <id>` для возврата.
- **SOUL.md на приёмной машине должен называться ровно `soul.md`/`SOUL.md` в доме, а не `SOUL-R2.md` — Hermes читает строго это имя (doctor показывает `~/.../SOUL.md (persona configured)`).** Если отдаёшь персону файлом/файл приходит вложением под другим именем — цель `MEDIA`-вложения имя файла меняется, и Hermes его не подхватит; результат проверяется `hermes -z "Представься: кто ты?"` (ответ персона R2, не дефолт).
- **В PowerShell `$home` — зарезервированная read-only переменная (профиль пользователя).** `$home = Join-Path ...` падает `VariableNotWritable`, а после ошибки все копирования идут по старому значению `$home` (`C:\Users\<user>\`) — файлы «успешно» ложатся НЕ туда, и `hermes doctor` их не видит. Именовать переменную домена иначе: `$hHome` / `$target`. Проверять не только «OK» в выводе копирования, а реальный целевой путь (`Test-Path "$target\config.yaml"`).
- **Мастер установщика (Setup Wizard) после install перезаписывает конфиг** — при миграции с уже разложенным config.yaml выходить из мастера Ctrl+C, НЕ выбирать пункты (выбор генерирует свежий шаблон и затирает перенесённый провайдер/ключи).
- **Ключ провайдера может жить в `config.yaml` секции `custom_providers[].api_key`, а НЕ в `.env`.** Если `hermes -z` отвечает «not connected to any AI provider yet» при существующем `.env` — сначала проверить, что перенесённый (VM-) `config.yaml` реально лежит в `%LOCALAPPDATA%\hermes\config.yaml`, а не застрял в `C:\Users\<user>\` от предыдущей ошибочной раскладки; `doctor`'s «API key configured» относится к `.env` и не доказывает наличие custom provider.

### Как подать результат Саше
План переезда — **MD-файл в `~/WorkVault/`** (синк → легко найти в ownCloud/Obsidian), НЕ только текст в чате. В плане обязаны быть: git-ссылки на актуальный код (см. контур 1), пошаговая инструкция **простым языком** (не канбан-жаргон), таблица «инструмент → что перенести → что сделать после», этапы с критериями приёмки, развёрнутый список рисков. Когда Саша просит «вышли файл сюда» — **отправлять сам MD-файл прямо в чат** (`MEDIA:/abs/path/file.md`), не только путь/ссылку; он легко найдёт его и в хранилище. Если поправки к плану появляются по ходу разговора (новое решение/уточнение Саши) — дополнять тот же файл и перевысылать обновлённую версию.

### Открытые вопросы владельца (Q-1…Q-4): подача по одному, с рекомендацией архитектора

При полном переезде часть решений принимает ТОЛЬКО Саша (судьба смешанных БД/сессий, канал доставки секретов, корпоративный доступ Windows, режим доступности, канал связи/бот). Правила подачи:
- **По одному вопросу**, варианты нумерованные с именем и следствием (номер + название + последствие), рекомендация архитектора и обоснование. Каждое решение фиксировать в `evidence/composition-decision.json` (slug, автор, текст решения, scope, что осталось открытым) ДО freeze блока.
- **Независимые части исполнения идут параллельно**, пока архитектор считает рекомендацию в фоне: `codex exec` с ролью архитектора + `notify`, продолжать сбор фактов/экспорты, не ждать завершения рекомендации.
- **Перед вопросом о канале доставки собрать read-only факты**, на которых стоит рекомендация: `systemctl is-active sshd` + порт, `rclone listremotes`, наличие `gpg`/`openssl`/`age`/`7z`, VPN-интерфейсы. Рекомендация опирается на проверенные факты, не на предположения; что не проверено — явно пометить «не проверено».

## Разовый вызов архитектора вне DevWorkflow

«Отдай разово без dev-workflow архитектору» — НЕ `pipeline invoke-role` (без --slug/--phase молча глотает stdout). Прямой `codex exec` с моделью/effort архитектора из `~/WorkVault/Registries/EcosystemConfig.yaml` → `tools.dev_workflow.invoke.roles.architect` (model + effort). Полную механику и формат парсинга --json — в скилле `codex`, раздел «Ad-hoc ролевая консультация». Промпт собирается `write_file` (не here-doc), ответ сохраняется в `~/WorkVault/_research/<topic>/` через парс последнего `agent_message`. Правило: архитектору давать ПОЛНУЮ фактуру (пути, размеры, состав), не узкое резюме.

## Питфоллы

- **`tools/` и `installs/` в ~/.hermes — это бинарные дистрибутивы и managed-окружения, НЕ данные.** Их невольный захват раздувает архив в разы и противоречит требованию «без дистрибутивов». Отличать по имени и размеру (каталоги «имя-версия-linux-x64», venv-деревья) до tar.
- **`.env` НЕ исключать из архива.** Там токены/секреты, критичные для подключений на приёмной машине; без него агент разворачивается мёртвым. Это перенос на свою машину, а не публикация секретов наружу.
- **Живой агент пишет данные во время сборки — копировать только через `rsync -a`, НЕ `cp`-пофайлово и НЕ «инвентаризация-потом-копия».** Внутренние воркеры создают/удаляют файлы прямо во время копирования (`cron/output/*.md`, `cron/external-workers/*.stderr`); файл, исчезнувший между инвентаризацией и копией или в момент cp, роняет всю сборку `FileNotFoundError`. `rsync -a --ignore-errors` устойчив к исчезающему файлу и сам дособирает родившееся за время копии повторным проходом `--ignore-existing`.
- **Симлинк-дерево активных скиллов копировать `rsync -aL` (follow links), а не `cp -rL`:** `cp -rL ~/.hermes/profiles/default/skills/ <dst>` схлопывает дерево (в поставке оказывается 1 элемент вместо 21 категории), а `rsync -aL` корректно разворачивает symlink'и на `~/hermes-workspace/skills/*` в реальные файлы. После копирования проверять число категорий (`ls | wc -l`), а не только наличие каталога.
- **Исключать временные runtime-каталоги из `.hermes` перед копированием:** `cron/output/` и `cron/external-workers/` — это временные доставки/логи внешних воркеров, НЕ данные; канон — `jobs.json` + `*.db` (`executions/deliveries/notepad`). Включать дешёвый `jobs.json`, а не живой `output/`. Плюс старые `jobs.json.bak-*`.
- **state.db (~4.1G) снимать согласованно через sqlite `.backup` (Python backup API), а не `cp`** — иначе теряется WAL-хвост и снимок непоследователен. Снимать `.backup` ДО rsync и НЕ давать rsync перезаписывать этот файл (он уже консистентный снапшот). Размер после `.backup` может отличаться от исходного `du` — это нормально и не признак ошибки.
- **Упаковка для Windows-получателя: ZIP с AES-256 через `pyzipper` (WZ_AES), НЕ .7z через `py7zr`.** Когда нет p7zip и нет sudo, ставьте `pip install --user pyzipper` СИСТЕМНЫМ интерпретатором (`/usr/bin/python3 -m pip install --user pyzipper`) — venv-питон отказывает `--user` (`User site-packages are not visible in this virtualenv`). py7zr-файл проходит локальный encrypt→decrypt roundtrip (`MATCH: True`, magic 7z...), НО НЕ открывается штатным 7-Zip на Windows («файл повреждён») — локальный roundtrip не гарантирует совместимость с распаковщиком получателя. Рабочий формат — `pyzipper.AESZipFile(out,'w', compression=ZIP_DEFLATED, encryption=WZ_AES)` + `zf.setpassword(pw)` (открывается 7-Zip/WinZip на Windows; не передавать `compression_level` — pyzipper его не принимает). Перед гонкой гигабайтов проверять метод на **маленьком запароленном тест-файле** (340 байт достаточно), полученный тест обязан открыться у получателя через 7-Zip, а не через Проводник Windows (Explorer не умеет AES-zip и пишет «повреждён»). Пароль генерировать (`openssl rand -base64 24 | tr -d '/+=' | head -c 24`), передавать отдельным каналом (личка ТГ), файл пароля с ВМ удалять.
- **Python-скрипт с Windows-путём, который ты отдаёшь Саше запускать на ноуте: все пути через raw-строки `r"..."`, а не набирать бэк-слэши втупую.** Обычная строка `session = SessionDB(src="C:\\Users\...")` падает ещё на этапе синтаксиса (`SyntaxError (unicode error) 'unicodeescape' ... truncated \UXXXXXXXX`) — Python читает `\U` как юникод-escape. Сырая строка `r"C:\Users\lenovo\...\state.db"` убирает весь класс ошибки. Это отдельно от сигнатуры API (см. выше).
- **Проверять сигнатуру/методы Hermes-API фактически на исходной машине (`inspect.signature`) перед передачей точного скрипта Саше** — угаданный по имени аргумент (`src` вместо `db_path`) и несуществующий символ импорта (`SCHEMA_SQL`/`SessionDB` из `hermes_state_local`) дают 2–3 лишних круга «запусти → упало с TypeError/ImportError». Один read-only прогон `./hermes-agent/.venv/bin/python -c "import inspect; from hermes_state import SessionDB; print(inspect.signature(SessionDB.__init__)); print(hasattr(SessionDB,'import_sessions'))"` на ВМ закрывает оба вопроса ДО передачи скрипта.
- **Живой агент после импорта истории не „сам подтягивает“ её из лежащего рядом JSONL — надо один раз прогнать `import_sessions` в его же `state.db`, и только потом он видит старые сессии через `--resume`/`session_search`.** Файл экспорта (`sessions-export.jsonl`, 1.7 ГБ) это не база, а формат переноса; «пусть агент сам читает из архива» = импортировать этот JSONL в его SQLite. Не путать цель («уже видит историю») с действием (разовый скрипт импорта). `state.db` (4+ ГБ) — смешанное хранилище (рабочие сессии + dev-история), целиком его не тащить: выборочный штатный export/import нужных разговоров (`hermes_state_portability.py` export_session/import_sessions) либо чистая инициализация, иначе накопишь десятки ГБ мусора. Если владелец решил «всю историю» — штатный bulk `SessionDB.export_all(include_inactive=True)` → JSONL → `import_sessions` на приёмной, а НЕ бинарная копия смешанной БД. Рабочий импорт на v0.23.x: `from hermes_state import SessionDB; db = SessionDB(db_path=Path("<дом>\state.db"), read_only=False); db.import_sessions([{"session": {...поля без messages...}, "messages": [...]}])`. Сигнатура конструктора `SessionDB(db_path=None, read_only=False)` — аргумент `db_path`, НЕ `src` (передача `src=` валит `TypeError: unexpected keyword argument`). `persistence_assembly.open_persistence(...)`, на который указывает DeprecationWarning, в v0.23.3 ЕЩЁ НЕ существует — SessionDB deprecated, но единственный рабочий путь в этой версии; переходить на новый API только когда он реально есть. Полную историю honcho снимать `docker exec honcho-database-1 pg_dump -U postgres -d postgres -Fc` — имя БД берётся из `POSTGRES_DB` контейнера (`postgres`), не из имени сервиса (`honcho`); `pg_dump -d honcho` падает с `database does not exist`. Маленькие/пустые (`sessions.db`, `kanban/kanban.db`, `profiles/*/state.db` = 0 байт; `kanban.db` = 7 МБ графов ВМ) — чистая инициализация или не переносить; перенос рабочих записей из `projects.db`/`shared-state.db`/`verification_evidence.db` не обоснован без проверки штатного экспорта. У каждой распухшей БД — своя судьба в решении владельца (Q-1).
- **Не гонять несколько процессов сборки на один выходной файл параллельно** — размер/содержимое «плывут» (в прогоне один tar писался и фоновым, и ручным вызовом: размер дергался 6.6→9.5→10→6.8G). Один строитель на один `.tar.gz`, потом фиксировать финальный `sha256` и только по нему сверять с облаком.
- **Мёртвая итоговая point: контрольную сумму давать по фактическому зависшему файлу, а не по обещанию «собрано».** sol-исполнитель дважды вернул rc=0 «архив не создан / ошибка» — читать последний `agent_message`, а счёт сразу после `tar -tzf | wc -l` + `sha256sum`.
- **Пути `/home/<user>` захардкожены** в конфигах и скриптах USERTOOLS. Для переноса решать развязку через `~`/переменные окружения, иначе на новой машине пути битые.
- **Не класть старые `_backup_*`/`_bak-*`/`_Archives`** — это снапшоты прошлых состояний, мусор для свежего развёртывания.
- **Очищать staging-дерево перед пересборкой (`rm -rf`) — иначе частные копии-клоны внутри payload попадают в tar целиком.** Оставшийся от упавшего rsync `payload/home/.hermes-copy-tmp` (частичный дубликат `~/.hermes`, 14G, 83k файлов, с сокетами и `_Archives`) был бесшумно захвачен финальным `tar payload` и испортил контрольную сумму. Перед пересборкой сносить staging полностью, а итог сверять `tar -tzf <архив> | grep -c 'copy-tmp'` (и жёсткий `grep -c 'payload/home/.hermes$'` на каноничность главного пути)."

## Связанные

- `full-workvault-backup` — только ~/WorkVault, локальный tgz в VM
- `tool-handoff-package` — перенос ОДНОГО скилла/инструмента
- `hermes-managed-install` — где живёт код Hermes (дистрибутив, не переносится)
- `workvault-outbox` — доставка файла Саше через ownCloud с проверкой
