---
name: skillstore-install
description: "Use when ставишь скилл из корпоративного skillstore."
version: 1.0.0
author: sirene
license: internal
metadata:
  hermes:
    tags: [skillstore, skill-store, install, tutu]
    related_skills: [hermes-skills-discovery, skills-git-storage, tool-implementation-audit]
---

# Установка скилла из корпоративного Skill Store (skills.tutu.ru)

## When to Use

- Саша просит «установи скилл X из skillstore» / «поставь X из skills.tutu.ru».
- Нужно поставить артефакт из корпоративного каталога (не внешнего skills.sh / hermes hub — это `hermes-skills-discovery`).

## Канонический путь установки

Корпоративный каталог обслуживается MCP `skill-store-mcp` (tools `mcp__skill_store_mcp__*`). Это единственный путь получения артефакта — MCP сам пишет файлы на диск, не переносишь байты вручную.

1. `mcp__skill_store_mcp__search` — найти slug по ключевым словам (ищи как говорит Саша, потом по-английски/синонимам; каталог матчит курируемые ключи).
2. `mcp__skill_store_mcp__get_details` — посмотреть manifest: `framework_restrict`, `requires`, `files`. **Если в `files` есть `payload/*.tar.gz` + `scripts/install-*.sh` — это дистрибуция с бинарником, см. питфолл платформы ниже.**
3. `mcp__skill_store_mcp__install` (framework, scope=user) — пишет файлы. **В enum `framework` нет Hermes** (только claude-code/cursor/opencode/zed/codex/cline) — для чистой поставки бери безвредный `framework='codex'`, файлы лягут в `~/.agents/skills/<slug>/` (путь из читаем). Статусы: `conflict` (уже есть — спросить, потом `force:true`), `needs_env` (несекретные значения), `use_one_liner` (секрет — вернуть команду verbatim для реального терминала, НЕ вводить токен в чат), `no_runtime`, `installed`.
4. **`installed` ≠ скилл работает.** Проверь фактическую применимость на этом хосте (см. питфолл платформы).
5. Если скилл — чистая поставка (только SKILL.md + references/, без бинарника) — интегрировать в Hermes-дерево по `skills-git-storage` (workspace + симлинк профиля).

## После установки: анализ/адаптация скилла архитектором

Саша часто просит после установки «исследуй этот скилл с архитектором», «что в нём для нас», «адаптируй под нас». Это RESEARCH по УЖЕ локальному артефакту — архитектор (codex-бэкенд, danger-full-access) читает файлы прямо по абсолютному пути установки (`~/.agents/skills/<slug>/`), веб-доступ ему для этого не нужен:

- НЕ копировать содержимое установленного скилла в `sources/` слага и НЕ предзагружать — файлы уже на диске, искать/читать их — работа роли, а не оркестратора.
- В brief RESEARCH (по `dev-workflow-role-launch`) указать корень скилла как источник, перечислить ключевые файлы/секции (SKILL.md/README.md, `reference/workflows/`, `reference/modules/`, `scripts/`) и разрешить роль сама обойдёт структуру через `search_files` (target='files') / контентный поиск.
- Разница с веб-источником: веб требует предзагрузки в `sources/` (у роли нет гарантии сети), диск у роли есть всегда — поэтому локальный артефакт не копируют.

## Питфолл: бинарный payload привязан к платформе, а MCP пишет «installed»

Механизм: некоторые скиллы в store — не просто SKILL.md, а **дистрибуция с исполняемым бинарником** (`payload/<name>.tar.gz` + `scripts/install-<name>.sh`). Установщик жёстко проверяет платформу (`uname -s`/`uname -m`) и на несовпадении сразу выдаёт `status=unsupported`, exit 30. При этом `mcp__skill_store_mcp__install` уже успешно записал файлы и вернул `installed` — обёртка SKILL.md на месте, но сам инструмент на этом хосте не запускается.

Правило: **перед объявлением успеха проверь платформу payload против хоста**, не верь статусу `installed`:

```bash
uname -s; uname -m            # хост: напр. Linux x86_64
file <распакованный-бинарник> # payload: напр. Mach-O 64-bit arm64 (macOS)
# manifest.json внутри tar.gz несёт поле "platform": ["darwin","arm64"]
```

Если платформы не совпадают — скилл на этой машине не работает. Это **блокер**, а не «установлено». Но прежде чем докладывать Саше блокер, **активно ищи версию под нашу платформу** — Саша может ожидать, что она существует («посмотри сам дистриб и возьми его»). Не объявляй блокер, не проверив корпоративные источники:

```bash
# 1. Skill Store: другие slug-варианты / фильтр по фреймворку
mcp__skill_store_mcp__search  # по имени, по 'arc-linux', по фреймворку
# 2. Artifactory: листинг и поиск артефактов по имени
curl -fsSL "https://artifactory.tutu.ru/artifactory/api/storage/generic-tutu"   # верхний уровень
curl -fsSL "https://artifactory.tutu.ru/artifactory/api/search/artifact?name=<name>"
# 3. Stash (Bitbucket) — репозиторий автора, где собирают релизы:
#    токен ~/WorkVault/Inbox/Tokens/bitbucket-stash-vm-hermes.md, Bearer-авторизация
curl -fsSL -H "Authorization: Bearer $TOK" "https://stash.tutu.ru/rest/api/1.0/projects?limit=100"
#    перебор проектов → repos, фильтр по slug
```

Если ни в одном источнике версии под нашу платформу нет — докладывай блокер **фактом** («Linux-дистрибутива нет в store/artifactory/stash — автор публикует только macOS»), не выдумывай путь/каталог. Варианты для Саши: запросить сборку у автора / ставить на подходящую машину / взять альтернативу из каталога без бинарника. Карточку не закрывать до решения.

## Питфолл: SKILL.md бинарного скилла — только «точка входа», а не сам инструмент

У дистрибуции с бинарником SKILL.md часто выглядит как обычный промпт — НЕ верь, что скилл «просто промпт» и хватит промпт-части. Проверь файлы: если есть `payload/*.tar.gz` (+ `scripts/install-*.sh`), в архиве лежит нативный исполняемый файл (`file <распакованный>` = z.`Mach-O`), а он несёт программную логику (проверки/валидации/state), которой в промпте нет. Поэтому анализа только SKILL.md недостаточно — без бинарника функция неполна. Докладывай это Саше фактом (что в поставке есть бинарник и что именно он делает), прежде чем вести к решению о замене.

## Питфолл: репо автора на stash может 401 — не гонять auth-варианты, канал store надёжен

У токена ВМ (`bitbucket-stash-vm-hermes.md`) доступ к stash **по проектам ограничен**: даже скилл, чей репозиторий автора в store, может лежать в проекте, который токен не видит (401 на projects/repos, хотя другие проекты листит). Для источника чистого скилла не уходи в git-clone и не перебирай формы auth (x-token-auth, Bearer, basic-логины) — это упирается в скоуп токена, а канал `install` из store читает бэкенд store и не зависит от этого ограничения. Правило: **источник чистого скилла — install из store, репо автора — только если токен его видит** (проверь `repos` проекта одним запросом перед клоном).

## Питфолл: замена — предпочесть чистый скилл того же охвата, предпочтительно того же автора

Когда Саша выбирает «взять альтернативу без бинарника»: выбирай **ближайший по назначению** чистый скилл из того же каталога, по возможности жеавтора (наследник лучше чужих), проверь `get_details` на отсутствие `payload`/`requires`, установи через MCP (`installed`), затем интегрируй в Hermes по `skills-git-storage` (workspace + симлинк профиля), проверь видимость (`hermes skills list`), закоммить+push в `hermes-workspace`. После успешной установки закрыть backlog-карточку (см. `dev-workflow-manual-kanban`: idea/triage → done прямым SQLite), указав, что выбран и почему.

## Установка из zip-архива (Telegram-документ / native-inputs)

Второй канал доставки скилла — не skillstore, а присланный Сашей zip (карточка «установить скилл X из архива»). Такой документ падает в
`~/.hermes/cache/documents/native-inputs/<hash>/doc_<id>_<name>.zip`. Установка идентична финалу skillstore-пути, но артефакт берём из zip:

```bash
ARCH=~/.hermes/cache/documents/native-inputs/<hash>/doc_<id>_<name>.zip
unzip -l "$ARCH"        # ДО распаковки: увидеть структуру (SKILL.md + справочники/скрипты?)
rm -rf /tmp/<name>-install && mkdir -p /tmp/<name>-install
unzip -q "$ARCH" -d /tmp/<name>-install
head -12 .../SKILL.md   # frontmatter: name, description — имя брать ИЗ frontmatter, не выдумывать
```

Интеграция в Hermes-дерево (workspace + симлинк) — по `skills-git-storage`:

```bash
cp -r "$SRC/." ~/hermes-workspace/skills/<category>/<name>/   # категория — по назначению (productivity/research/software-development)
ln -sfn ~/hermes-workspace/skills/<category>/<name> ~/.hermes/profiles/default/skills/<category>/<name>
ln -sfn <та же цель> ~/.hermes/skills/<category>/<name>        # дублировать симлинк в общий каталог
hermes skills list | grep <name>                              # проверить enabled, не «положить и забыть»
git -C ~/hermes-workspace add skills/<category>/<name>/ && git commit && git push
```

Затем закрыть backlog-карточку (idea/triage → done прямым SQLite, см. `dev-workflow-manual-kanban`). Имя каталога скилла сохранять как в frontmatter (в т.ч. суффикс `-standalone`), а не переименовывать по смыслу.

## Питфолл: native-inputs — временный кэш, архив может исчезнуть

Telegram-документ, указанный в карточке как источник, — единственная копия и лежит во временном кэше: `native-inputs` подчищается, файл и даже родительский `<hash>`-каталог могут пропасть между созданием карточки (triage) и установкой. Порядок:

- **При получении zip сразу класть копию в постоянное место** (`~/.hermes/_Archives/`), не оставляя единственную копию в native-inputs — через неделю её может не быть.
- Перед установкой по карточке проверять факт существования файла (`ls -la <путь из карточки>`) ДО объявления плана.
- Если файла нет: нельзя «восстанавливать» или выдумывать содержимое. Сначала искать источник через `session_search` по имени файла (сессия, где документ пришёл, часто сохраняет путь в bookend), затем просить Сашу переприслать архив — одно сообщение, без долгих квестов по бэкапам.
- При переприсылке путь в `native-inputs` меняется (новый `<hash>`/`doc_<id>`), но zip-имя то же — искать по имени, не по полному старому пути.

## Питфолл: зависимость может ставиться отдельно

`requires` в manifest разрешается MCP автоматически (пишет зависимость рядом). Но «зависимость установлена» ≠ «основной артефакт рабочий» — проверяй именно основной payload по платформе.

## Связанные

- `hermes-skills-discovery` — поиск/оценка скиллов во ВНЕШНЕЙ экосистеме (skills.sh, hermes hub), не корпоративный store.
- `skills-git-storage` — куда класть установленный чистый скилл в Hermes-дереве (workspace + симлинк).
- `tool-implementation-audit` — перед «делаем» проверить, что инструмента ещё нет в проде.
