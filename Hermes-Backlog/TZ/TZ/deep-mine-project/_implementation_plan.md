---
name: deep-mine-project-implementation-plan
version: 0.1.0
date: 2026-09-02
status: draft-plan
phase: hermes-feature-1A
source_tz: TZ/deep-mine-project/deep-mine-project_TZ.md
source_tz_version: 0.2.0
author: архитектор (cursor-grok-4.6-high, Cursor CLI)
---

# Пофайловый план реализации deep-mine-project (Блок 1А)

Источник истины: `~/WorkVault/Hermes-Backlog/TZ/deep-mine-project/deep-mine-project_TZ.md` v0.2.0. Решения Саши (бриф 02.09) не переоткрывать. Реализацию не начинать до «берём в работу».

Рекомендация: принять этот план as-is. Исполнитель (composer-2.5) идёт сверху вниз по волнам 0→7. Промежуточные точки — молча.

## Зафиксированные факты (проверены 2026-09-02)

Не проектировать заново:

| Факт | Значение |
|---|---|
| Overlay P0 | `~/WorkVault/Projects/TrisigmaFull/{MANIFEST.json,TREE.md,SOURCES.md}` — 33 ключа pageId |
| `content_sha256` P0 | 16 hex, не полный sha256 → волна 1 пересчитывает |
| L0 `children` | ConfluenceSync всегда пишет `children: []`; `parent` заполнен. TREE строить **инверсией `parent`**, не ждать children |
| Root / PMO | `493477568` / Бриф `490166551` / Устав `490167911` |
| ConfluenceSync | `get_page(expand=version)`, `get_attachments`, `attachment_download_url`, `get_children`, `ping` — уже есть. `get_attachments` глотает `RequestException` → `[]`. Не патчить: в B сначала `ping()`, 401/403 = fail-loud |
| MppReader | `~/USERTOOLS/MppReader/read_mpp.py --format both --out-dir` |
| MofsIndex | `search_meetings` default `limit=50`; для ~91 встреч передавать `limit=500` |
| Venv | `~/hermes-agent/.venv` (A и C) |
| Черновик скилла | `~/.hermes/skills/devops/project-context-digest/` — **не** в hermes-workspace, триггеры пересекаются с ТЗ. Заменить, не дублировать |
| Сущность | `Entities/trisigma/{card,context,risks,contract_vendor,status_snapshot,protocol}.md` + `Pages/`; aliases в `entities.json` только `["trisigma"]` |

## Новые сущности

- `~/WorkVault/Registries/project-context-compressor-prompt.md` — **согласовано Сашей 02.09**, создавать в волне 0.
- Скилл `deep-mine-project` + скрипты внутри скилла — это сам инструмент ТЗ, не отдельный USERTOOLS-пакет.

Не предлагать и не заводить (уже закрыто ТЗ): USERTOOLS/DeepMineProject, `--with-attachments` в ConfluenceSync, таблицы `Projects/` в mofs-index, крон refresh, правка `tz-compressor-prompt.md`.

---

## 0. Карта артефактов

Канонический корень скилла (писать сюда, затем `restore-all-skills.sh`):

`~/hermes-workspace/skills/research/deep-mine-project/`

Категория `research/` — рядом с `workvault-rag`. Не класть в `devops/`: там черновик `project-context-digest`, смешение с hermes-feature.

CLI (Python, высокая автоматизация) — команды брифа, плюс алиасы ТЗ:

```text
~/hermes-agent/.venv/bin/python3 \
  ~/hermes-workspace/skills/research/deep-mine-project/scripts/deep_mine.py \
  <init|collect|refresh|digest|mine|analyze|document> --slug TrisigmaFull [flags]
```

| CLI | Шаги ТЗ | LLM? |
|---|---|---|
| `init` | пререквизит E (скелет overlay + `PROJECT.yaml`) | нет |
| `collect` | A→B→C(CSV)→D→E (+ указатель сущности) | нет (`plan.md` не здесь) |
| `refresh` | алгоритм refresh 1–8, затем E, пометка stale | нет (`--dry-run` = критерий 6) |
| `digest` | C(`plan.md`) + F | да, `composer-2.5`, по одному листу |
| `mine` | алиас ТЗ: `collect` + `digest` | смешанный оркестратор |
| `analyze` | G | да, `cursor-grok-4.6-high` |
| `document` | H | да, `composer-2.5` |

Скилл мапит фразы When to Use на эти команды. Кроны не ставит.

---

## 1. Какие файлы создать / изменить

### Создать

| # | Абсолютный путь | Шаг ТЗ | Действие |
|---|---|---|---|
| 1 | `~/hermes-workspace/skills/research/deep-mine-project/SKILL.md` | оркестрация A–I | новый скилл |
| 2 | `.../references/cli.md` | команды скилла | канон CLI, флаги, exit codes |
| 3 | `.../references/overlay-contract.md` | E, модель digest | MANIFEST 1.0, slug, frontmatter, граф |
| 4 | `.../references/roles-and-prompts.md` | F, G, H | шаблоны `agent -p`, одна модель на вызов |
| 5 | `.../references/trisigma-defaults.md` | первый проект | root/PMO/entity, ожидания 33 / ~91 / MPP |
| 6 | `.../scripts/deep_mine.py` | entry-point | тонкий `if __name__` → `cli.main()` |
| 7 | `.../scripts/deepmine/__init__.py` | — | пакет, `__version__ = "0.1.0"` |
| 8 | `.../scripts/deepmine/cli.py` | команды | argparse: init/collect/refresh/digest/mine/analyze/document |
| 9 | `.../scripts/deepmine/paths.py` | overlay | `WorkVault`, overlay-dirs, константы |
| 10 | `.../scripts/deepmine/project_config.py` | init | load/validate `PROJECT.yaml` |
| 11 | `.../scripts/deepmine/l0.py` | E, stale | frontmatter L0, полный sha256 тела |
| 12 | `.../scripts/deepmine/confluence_pull.py` | **A** | subprocess `confluencesync pull`; fail-loud |
| 13 | `.../scripts/deepmine/attachments.py` | **B** | whitelist, REST, HTTP GET → `attachments/` |
| 14 | `.../scripts/deepmine/mpp_run.py` | **C** (CSV) | subprocess `read_mpp.py --format both` |
| 15 | `.../scripts/deepmine/meetings.py` | **D** | `search_meetings` → `pointers/meetings.md` |
| 16 | `.../scripts/deepmine/entity.py` | указатель | `pointers/entity.md` без копий тел |
| 17 | `.../scripts/deepmine/manifest.py` | **E** | миграция P0 → schema 1.0, пересборка |
| 18 | `.../scripts/deepmine/tree_sources.py` | **E** | иерархический `TREE.md`, таблица `SOURCES.md` |
| 19 | `.../scripts/deepmine/graph.py` | E/F связи | `links.md`, backlinks, `related_unresolved` |
| 20 | `.../scripts/deepmine/digest_io.py` | **F** механика | шапка, «Источники», `_history/`, status |
| 21 | `.../scripts/deepmine/refresh.py` | refresh | poll version, skip/pull, missing_remote, stale |
| 22 | `.../scripts/deepmine/cursor_jobs.py` | **C plan / F / G / H** | сборка промпта, `agent -p`, парсинг json |
| 23 | `.../scripts/deepmine/fail.py` | A/B/refresh | fail-loud 401/403/VPN, не маркировать fresh |
| 24 | `.../tests/conftest.py` | тесты | `tmp_path` mini-overlay, без сети |
| 25 | `.../tests/fixtures/mini_l0/` | тесты | 3 фейковых `index.md` (root+child+pmo) |
| 26 | `.../tests/test_*.py` | см. §6 | pytest, маркер `live_confluence` не гонять |
| 27 | `~/WorkVault/Registries/project-context-compressor-prompt.md` | **F** | промпт компрессора (согласован) |
| 28 | `~/WorkVault/Projects/TrisigmaFull/PROJECT.yaml` | init | параметры бурения из ТЗ |
| 29 | overlay-dirs при `init` | каталог overlay | `attachments/ mpp/ pointers/ digest/{leaves,themes,_history} docs/_inbox/` |

### Изменить (только свои артефакты overlay / замена черновика)

| # | Абсолютный путь | Шаг | Действие |
|---|---|---|---|
| 30 | `~/WorkVault/Projects/TrisigmaFull/MANIFEST.json` | E | обернуть плоские ключи в `pages`, `schema_version`, полный sha256, `parent`/`children` из инверсии, `kind`, digest-указатели |
| 31 | `~/WorkVault/Projects/TrisigmaFull/TREE.md` | E | пересобрать иерархию parent→children (P0 плоский — регрессия критерия 3) |
| 32 | `~/WorkVault/Projects/TrisigmaFull/SOURCES.md` | E | таблица pageId → title → version → local_path → wiki |
| 33 | `~/.hermes/skills/devops/project-context-digest/` | гигиена триггеров | **удалить каталог** после появления нового скилла (не в workspace). Перенести полезное из `references/trisigma-archive-2026.md` в `references/trisigma-defaults.md` |

После записи скилла в workspace — `~/hermes-workspace/restore-all-skills.sh` (синк в default). Не трогать чужие профили.

### Не создавать в v0.1

- `~/USERTOOLS/DeepMineProject/`
- записи в `~/.hermes/cron/jobs.json`
- правки ConfluenceSync / MppReader / `tz-compressor-prompt.md`
- индекс overlay в mofs-index
- `docs/*.md` проектных документов (это шаг H по запросу Саши, не mine)

---

## 2. Python: модули, функции, CLI

Entry-point: `scripts/deep_mine.py` → `deepmine.cli.main()`.

Инвариант: нет нового USERTOOLS-пакета. Несколько файлов в `scripts/deepmine/` (каждый ≤ ~200 строк) — это скрипты скилла, не приложение.

### `cli.py`

```
main() -> int
cmd_init(args)
cmd_collect(args)      # A B C-csv D entity E
cmd_refresh(args)      # --dry-run
cmd_digest(args)       # --only SLUG | --all-stale | --plan-only
cmd_mine(args)         # collect + digest
cmd_analyze(args)      # G, не кормить Confluence/
cmd_document(args)     # H, только после architect-plan.md
```

Флаги общие: `--slug`, `--workvault` (default `~/WorkVault`), `--dry-run`, `--json` (машиночитаемый итог).

Exit codes: `0` ok; `2` валидация/`PROJECT.yaml`; `3` Confluence недоступен / 401/403; `4` MPP/Java; `5` индекс встреч недоступен.

### Ключевые функции по шагам

**A — `confluence_pull.py`**

- `run_pull(page_id: str, *, depth: int | None, recursive: bool, resync: bool) -> PullResult`
- `pull_seed_tree(cfg) -> None` — root `--depth 6 --resync --to-file`; каждый pmo_seed `--no-recursive --resync --to-file`
- subprocess: `~/hermes-agent/.venv/bin/python3 -m confluencesync pull ...`, cwd `~/USERTOOLS/ConfluenceSync`
- ненулевой exit / «401» / «403» / connection → `fail.confluence_down()`, пайплайн стоп

**B — `attachments.py`**

- `WHITELIST_EXT = {".mpp", ".mpx", ".xml"}` + имена из `cfg.mpp.expected_name`
- `list_whitelist(page_id, client) -> list[AttachmentMeta]`
- `download_attachment(meta, dest_dir) -> local_path` — `client.session.get(client.attachment_download_url(...), stream=True)`; 401/403 raise
- `is_ole2_or_zip(path) -> str` — сигнатура; `.zip` не распаковывать наугад
- `sync_attachments(cfg, manifest) -> dict` — пишет `MANIFEST.attachments[]` с filename, page_id, download_url, local_path, sha256, filesize, synced_at
- Перед циклом: `client.ping()`; false → fail-loud (обход silent `[]` у `get_attachments`)
- Клиент: `get_settings()` + `ConfluenceClient(base_url, token)` из пакета ConfluenceSync **без правок пакета**

**C — `mpp_run.py` + кусок `cursor_jobs.py`**

- `export_csv(mpp_path, out_dir) -> CsvTriple` — `read_mpp.py <file> --format both --out-dir mpp/`
- `register_mpp_in_manifest(...)`
- `plan.md` **не** из CSV руками: `cursor_jobs.compress_plan(csv_dir)` = один `agent -p --model composer-2.5`

**D — `meetings.py`**

- `index_meetings(project_slugs: list[str]) -> list[MeetingRow]`
- `from mofs_index import search_meetings, get_meeting` (`sys.path` → `~/USERTOOLS/MofsIndex`)
- Вызов: `search_meetings(query=None, slugs={"projects": project_slugs}, slug_mode="any", limit=500)`
- Писать только `pointers/meetings.md`: дата, meeting_id, title, wiki-ссылка на summary, `transcript_present`
- Запрет: не читать/не копировать transcript; `get_meeting_body` — только на шаге F внутри компрессора по требованию

**E — `manifest.py`, `tree_sources.py`, `l0.py`**

- `parse_l0_page(path) -> L0Record` (frontmatter + `content_sha256` = sha256 тела **без** YAML)
- `migrate_manifest_p0(raw: dict) -> Manifest` — если нет `schema_version`/`pages`: все ключи → `pages`, сохранить поля
- `rebuild_children(pages) -> None` — инверсия `parent` (L0 `children: []` — норма ConfluenceSync, не баг скилла)
- `rebuild_all(overlay) -> Manifest` — идемпотентно; не плодить дубли ключей
- `write_tree_md(manifest, path)` — вложенный список, не группировка по space
- `write_sources_md(manifest, path)` — таблица
- После A/B/refresh вызывать `rebuild_all` целиком

**Граф — `graph.py`**

- `extract_outbound_page_ids(md_body) -> set[str]` — `viewpage?pageId=` / wiki-ссылки; не pull в v0.1
- `recompute_backlinks(digests) -> None` — механика, не LLM
- `write_links_md(edges)` — CSV-таблица `from,to,edge` ∈ parent|child|related|backlink
- Невалидный `related` → `related_unresolved`, в пробелы G

**F механика — `digest_io.py`**

- `leaf_slug_page(page_id) -> "p{pageId}"`
- `write_digest(path, fm, body)` — блок «Источники» обязан быть первым в теле
- `mark_stale(slug)` / `archive_history(slug, version, source_sha8)`
- `list_stale(manifest) -> list[str]`
- Компрессор не пишет backlinks и не правит чужие листья

**Refresh — `refresh.py`**

- `poll_version(client, page_id) -> int | None` — `get_page(id, expand="version")`, без body
- `refresh_pages(cfg, manifest, *, dry_run) -> RefreshReport`
  1. remote == local → skip
  2. remote > local → pull `--no-recursive --resync --to-file` (в dry-run только пометить)
  3. 404/gone → `digest_status=missing_remote`, L0 не удалять
  4. новые children известных родителей (через `get_children`, не через пустой frontmatter) → pull + MANIFEST
  5. исходящие вне seed → только граф `related_unresolved`
  6. вложения: filesize/version metadata изменилась → скачать
  7. sha MPP изменился → C целиком, stale `mpp-plan`
  8. встречи: перезапрос; stale `m-index` только если набор id или mtime summary изменился
- dry-run: **не** pull, **не** compress; только отчёт stale

**F/G/H — `cursor_jobs.py`**

- `run_agent(prompt: str, model: str, cwd: Path) -> AgentResult` — ровно один `--model`
- `compress_leaf(slug)` / `compress_theme(slug)` / `compress_plan()` / `write_diff(stale_slugs)`
- `analyze()` — вход: `_index.md` + themes + `docs/_inbox/diff.md`; **запрет** прикладывать файлы `Confluence/**/index.md`
- `document()` — вход: `architect-plan.md` + указанные digest'ы → `docs/*.md` со `status: draft`
- Промпт F всегда включает текст/путь `project-context-compressor-prompt.md`. Путь `tz-compressor-prompt.md` в коде не упоминать

---

## 3. `PROJECT.yaml` (TrisigmaFull) — создать как есть в ТЗ

Путь: `~/WorkVault/Projects/TrisigmaFull/PROJECT.yaml`

Поля из ТЗ (schema_version 1.0): slug, display_name, entity_slug, confluence.root_page_id / root_title / space_primary / pmo_seeds / follow_outbound=`pmo-from-root`, mpp.expected_name / project_title, meetings.project_slugs=`[trisigma]`.

Стартовые themes (дефолт ТЗ, вопрос 3 не блокирует): `pmo, architecture, poc-criteria, full-rollout, security, plan, meetings`. Тема без листьев не создаётся.

`init --slug TrisigmaFull` на уже существующем overlay: дописать YAML и каталоги, **не** затирать MANIFEST.

---

## 4. Промпт компрессора — структура файла

Путь: `~/WorkVault/Registries/project-context-compressor-prompt.md`

**Не** копировать `tz-compressor-prompt.md`. Отличия, которые файл обязан явно зафиксировать:

| tz-compressor | project-context-compressor |
|---|---|
| модель Gemini, запрет composer | модель **composer-2.5**, запрет grok на сжатие |
| экстракт не сохранять | экстракт **сохраняется** в overlay digest |
| 3–5 КБ CLI/ENV/cron | 30–40% исходного MD (или полный перенос если L0 < 2 КБ) |
| спецификация инструмента | факты проектной страницы/встреч/плана |

Обязательные секции файла:

1. **Модель и режим** — `composer-2.5`; один `agent -p` = один лист или одна тема; кэш не нужен между вызовами.
2. **Роль** — компрессор проектного контекста, не архитектор и не исполнитель документов.
3. **Вход** — ровно один источник: L0 `index.md` **или** набор summary через meeting_id **или** CSV/`plan.md`; плюс `PROJECT.yaml` (slug, themes); плюс список существующих digest-slug для `related`.
4. **Выход — файл overlay** (не stdout-only): полный MD digest с YAML-шапкой ТЗ (`schema_version, kind, slug, title, source_kind, page_id, confluence_url, local_path, version, source_sha, parent, children, related, backlinks, status, generated_at, generated_by`). `backlinks: []` на выходе компрессора — скрипт пересчитает.
5. **Блок «Источники»** — первый в теле; local MD + живой Confluence URL + `[[slug]]`.
6. **Full-coverage** — решения, цифры, даты, имена, ID, статусы, SLA, милестоуны, pageId, version. Запрет выкидывать «мелочи».
7. **Объём** — ориентир 30–40% L0; страница <2 КБ — перенос почти целиком. Не цель «3–5 КБ».
8. **Встречи** — дефолт один лист `m-index` (хронология + решения/риски/поручения + meeting_id). Тематические `m-{theme}` только если черновик листа > 8 КБ. Transcript целиком запрещён; сниппеты только с цитатой и meeting_id.
9. **Связи** — можно предложить `related` (pageId/JIRA/theme). Не выдумывать `backlinks`. Не редактировать чужие листья.
10. **Процесс** — инвентарь именованных сущностей → сжатие → самопроверка инвентаря.
11. **Запреты** — не писать в L0; не вызывать ConfluenceSync; не использовать tz-compressor; не анализировать «что делать проекту» (это G).
12. **Вызов** — пример `cd ~/WorkVault/Projects/<Slug> && agent -p "$(cat ~/WorkVault/Registries/project-context-compressor-prompt.md)\n---\nСожми источник: ..."` `--model composer-2.5`.

---

## 5. SKILL.md — что содержит

Файл: `~/hermes-workspace/skills/research/deep-mine-project/SKILL.md`  
Ориентир: ≤ 200 строк / < 15 КБ. Процедуры на английском, цитаты Саши — `> Context (RU):`.

**Frontmatter**

- `name: deep-mine-project`
- `description:` триггеры ТЗ в ≤1024 символов: глубокий анализ проекта, глубокое бурение, собери/обнови архив проекта, deep-mine refresh, digest проекта, проектная документация полного внедрения. Контр-триггеры: не для точечного вопроса (workvault-rag), не sync одной страницы (ConfluenceSync), не компрессия ТЗ (`tz-compressor-prompt`).
- `version: 0.1.0`, `platforms: [linux]`
- `related_skills: [workvault-rag, hermes-feature, tutu-confluence-jira, read-mpp]` — `read-mpp` упомянуть как **не вызывать** для бурения (CSV+MD overlay, не GS)

**Тело**

1. **When to Use** + Don't use (из ТЗ).
2. **Prerequisites** — VPN/on-prem, `CONFLUENCE_TOKEN`, venv `~/hermes-agent/.venv`, Java 17 для C, Cursor CLI `agent`, MofsIndex построен.
3. **How to Run** — таблица фраз Саши → CLI (`mine` / `refresh` / `digest` / `analyze` / `document`). Явно: кроны не ставить.
4. **Procedure** — шаги A–I с completion criterion на шаг (ссылка на `references/cli.md` для флагов).
5. **Overlay invariant** — L0 не копировать; удаление overlay не трогает канон.
6. **Roles** — один `agent -p` = одна модель; компрессор composer, архитектор grok, исполнитель composer.
7. **Pitfalls** (коротко, детали в references): VPN fail-loud; вложение ≠ ссылка; `children: []`; усечённый sha P0; pagetree-макрос; ab_platforma ≠ trisigma; не кормить G сырым L0; Java/mpxj; не крон; не tz-compressor; `get_attachments` silent empty → ping; `search_meetings` limit 50.
8. **Verification** — чеклист критериев успеха 1–14 как команды (grep overlay, schema, TREE не плоский, ping digest_path, backlinks, dry-run stale, meetings без transcript, MPP csv+plan.md, лог одной модели).

Сирень исполняет скилл: вызывает CLI на A–E/refresh, батчит F. Не смешивает модели.

---

## 6. Тесты — какие и где

Корень: `~/hermes-workspace/skills/research/deep-mine-project/tests/`  
Запуск: `~/hermes-agent/.venv/bin/python3 -m pytest ~/hermes-workspace/skills/research/deep-mine-project/tests -q -m "not live"`

Без сети, без записи в реальный `Projects/TrisigmaFull` (только `tmp_path` + фикстуры). Опциональный `@pytest.mark.live` не гонять в Блоке 3 по умолчанию.

| Файл | Что доказывает | Критерий ТЗ |
|---|---|---|
| `test_migrate_manifest.py` | P0 плоская карта → `pages` + schema 1.0; поля не потеряны; повторный migrate идемпотентен | 11, 8 (sha) |
| `test_l0_sha256.py` | sha тела без frontmatter = 64 hex; 16-символьный P0 не сравнивается as-is | питфолл 8 |
| `test_tree_hierarchy.py` | из трёх страниц (root, child, pmo с parent=None) TREE вложенный, не «по space» | 3 |
| `test_rebuild_children.py` | children в MANIFEST = инверсия parent, даже если L0 `children: []` | E |
| `test_attachments_whitelist.py` | качает только .mpp/.mpx/.xml + expected_name; прочие skip; zip не unzip | B, 8 |
| `test_fail_loud.py` | ping false / 403 → exit 3, status не fresh | A/B |
| `test_meetings_pointer.py` | md содержит id/дату/ссылку; нет блока transcript; `limit>=91` в вызове (mock) | 7 |
| `test_entity_pointer.py` | только пути на `Entities/trisigma/*`, тел файлов нет | 1 |
| `test_digest_contract.py` | slug `p{id}`; шапка; «Источники» первым; history path | 4 |
| `test_graph_backlinks.py` | backlinks = обращение related+children; unresolved не в related | 5 |
| `test_stale_dry_run.py` | bump version в фикстуре L0 → `refresh --dry-run` помечает **ровно** эту запись stale, compress не вызван | 6 |
| `test_l0_not_copied.py` | после collect в overlay нет `confluence_id:` в телах кроме digest/SOURCES/pointers | 1 |
| `test_cursor_jobs_models.py` | compress → composer-2.5; analyze → grok-4.6-high; в промпте G нет содержимого `Confluence/` | 9, 10 |
| `test_cli_commands.py` | init/collect/refresh/digest существуют; нет подкоманды cron | 14 |
| `test_prompt_file.py` | compressor path существует **после волны 0**; grep репо скилла: нет `tz-compressor-prompt` | 13 |
| `test_no_usertools_package.py` | в плане/скилле нет создания `USERTOOLS/DeepMineProject` | 12 |

Интеграционный smoke (волна 7, на реальном TrisigmaFull, сеть): `collect --skip-a` (L0 уже есть) → E → покрытие ≥33 pageId с существующим `local_path`. Отдельно, с VPN: B+C. Не часть unit-гейта.

---

## 7. Промежуточные точки проверки

Исполнитель проходит молча. ✅/❌ по критерию.

| Точка | После волны | Критерий (проверяемо) |
|---|---|---|
| T0 | 0 | Существуют SKILL.md, `project-context-compressor-prompt.md`, `PROJECT.yaml`. `tz-compressor-prompt.md` `git/status` без diff. Нет записей cron от скилла. `project-context-digest` удалён, триггер `deep-mine` резолвится в новый скилл |
| T1 | 1 | `python3 ... deep_mine.py init --slug TrisigmaFull` идемпотентен. `MANIFEST.schema_version=="1.0"`, 33 ключа в `pages`, sha 64 hex. `TREE.md` вложен от `493477568`, PMO seed на верхнем уровне (не дети DPAN). Повторный E не меняет sha страниц |
| T2 | 2 | `collect --skip-a --skip-b --skip-c` пишет `pointers/meetings.md` (≥1, ориентир ~91) и `pointers/entity.md`. Под `Projects/TrisigmaFull/` нет ` - transcript.md`. Grep `confluence_id` в overlay — только указатели/SOURCES/будущие digest, не полные тела |
| T3 | 3 | При наличии VPN: whitelist-файл в `attachments/`, три CSV в `mpp/`. Код ConfluenceSync и MppReader без diff. Нет Java → exit 4, overlay status не «готово» |
| T4 | 4 | Для 1 фикстурной страницы: файл `digest/leaves/pNNNN.md`, шапка валидна, блок Источники, `status: fresh`. `links.md` и `_index.md` с тем же `generated_at`. Компрессор вызван с composer-2.5 и путём project-compressor |
| T5 | 5 | Искусственный bump `version` одной L0 + `refresh --dry-run`: stale ровно 1 slug, остальные fresh, compress не запускался. Документ `docs/_inbox/diff.md` на реальном refresh (не dry-run) содержит old→new |
| T6 | 6 | Промпт G (собранный `cursor_jobs.analyze`) содержит `_index` + themes + diff, не содержит текст `Confluence/**/index.md`. `analyze`/`document` не вызываются из `mine` |
| T7 | 7 | pytest `-m "not live"` зелёный. Критерии успеха ТЗ 1–14 закрыты или явно отложены с причиной (MPP без VPN = T3 skip с пометкой). `restore-all-skills.sh` выполнен |

Готово по плану = все T0–T7 ✅. Статус «completed» на весь план ставит только Саша.

---

## 8. Порядок реализации (волны)

Не параллелить волны, которые делят MANIFEST. Тесты волны писать сразу, не в конце.

**Волна 0 — каркас (без сети)**  
Файлы 1–5, 6–10, 23, 27, 28, скелет тестов 24. Удаление черновика скилла (33) в конце волны, когда новый SKILL.md уже на месте.  
→ **T0**

**Волна 1 — E на существующем P0 (без сети, без pull)**  
Файлы 11, 17, 18, 19 (минимально: TREE/SOURCES/migrate/sha). `rebuild_all` по 33 L0.  
→ **T1**  (критерии 2 частично, 3, 11)

**Волна 2 — D + entity + collect-скелет**  
Файлы 15, 16, cli `collect --skip-*`.  
→ **T2**  (критерии 1, 7)

**Волна 3 — A + B + C(CSV)**  
Файлы 12, 13, 14, 21 (poll ещё не полный). Live smoke только если VPN.  
→ **T3**  (критерии 8, 12)

**Волна 4 — F**  
Файлы 20, 22 (compress_leaf/theme/plan), themes из YAML, `_index`, history. Батч Сирень: один лист = один agent. Первый прогон на Trisigma: можно начать с root + 2 PMO, не обязательно все 33 в той же сессии — но критерий 4 требует все pages до приёмки v0.1.  
→ **T4**  (критерии 4, 5, 13)

**Волна 5 — refresh**  
Файл 21 полностью + digest stale + `docs/_inbox/diff.md`.  
→ **T5**  (критерии 6, 14)

**Волна 6 — G/H в скилле**  
`cursor_jobs.analyze/document` + секции SKILL Procedure. Не запускать H без фразы «проектная документация».  
→ **T6**  (критерии 9, 10)

**Волна 7 — гейт**  
Дописать тесты §6, прогнать pytest, `restore-all-skills.sh`, сверить критерии 1–14. EcosystemManifest / MAIN_TZ_INVENTORY — **не** в этой реализации (механика координатора после приёмки, Блок 4 hermes-feature по отдельной команде).  
→ **T7**

Шаг I (приёмка Саши) — не автоматизируется.

---

## 9. Что НЕ трогать

Жёсткий список (исполнитель стопится, если «надо чуть поправить»):

- `~/USERTOOLS/ConfluenceSync/**` (код, ТЗ, `--with-attachments`)
- `~/USERTOOLS/MppReader/**`
- `~/WorkVault/Registries/tz-compressor-prompt.md`
- `~/WorkVault/Confluence/**` — не переносить, не переименовывать, не дублировать в overlay; pull только через существующий CLI
- `~/WorkVault/Meetings/NewMeetings/**` — не копировать transcript в overlay
- `~/WorkVault/Entities/**`, `~/WorkVault/Registries/entities.json`
- `~/WorkVault/Registries/EcosystemManifest.json` и `MAIN_TZ_INVENTORY.md` в этом плане (после приёмки — координатор)
- `TZ/<другой Tool>/`
- `~/.hermes/cron/jobs.json` — кроны не создавать
- `~/.hermes/config.yaml`, Gateway — не рестартить
- чужие профили Hermes (tz-dev декомиссован)
- `compression.threshold`
- скилл `read-mpp` (не вызывать для бурения)
- mofs-index схема / `docs_fts` для `Projects/`
- `ConfluenceSync push` в шагах A–H

Reuse-first: A/C/D = существующие CLI/API; B = скрипт скилла на клиенте ConfluenceSync.

---

## 10. Риски реализации (не открытые вопросы Саше)

1. L0 `children: []` — TREE только инверсией `parent`; новые дети на refresh — через `ConfluenceClient.get_children`, не через frontmatter.
2. `get_attachments` возвращает `[]` при сетевой ошибке — обязателен `ping()` / raise на HTTP GET.
3. `search_meetings(..., limit=50)` обрежет ~91 встречу — в коде `limit=500`.
4. P0 sha 16 hex — миграция пересчитывает, иначе refresh ложно-stale/fresh.
5. Объём F на 33 листа — батч, не один agent на архив; критерий 4 закрывается до приёмки, не обязательно в одном вызове Cursor.
6. Навык `project-context-digest` пересекается по триггерам — удалить в T0, иначе Сирень загрузит оба.
7. skill-authoring «scripts ≤200 строк иначе USERTOOLS» vs ТЗ «не USERTOOLS-пакет»: решение ТЗ — пакет модулей внутри `scripts/deepmine/`, каждый файл короткий. Разрастание в USERTOOLS — только новый вопрос Саше, не v0.1.

Открытые вопросы ТЗ 3–7 (themes, meeting-granularity, dual-store MPP, манифест экосистемы, обогащение) — дефолты ТЗ, не блокируют.

---

## Прогресс выполнения

- [ ] Волна 0 — каркас скилла, промпт, PROJECT.yaml, CLI-скелет (T0)
- [ ] Волна 1 — миграция MANIFEST + иерархический TREE/SOURCES (T1)
- [ ] Волна 2 — указатели встреч и сущности (T2)
- [ ] Волна 3 — pull A, вложения B, MPP CSV C (T3)
- [ ] Волна 4 — digest F + граф (T4)
- [ ] Волна 5 — refresh + stale + diff (T5)
- [ ] Волна 6 — analyze G / document H (T6)
- [ ] Волна 7 — pytest + restore-all-skills + критерии 1–14 (T7)

Статус «completed» ставит только Саша.
