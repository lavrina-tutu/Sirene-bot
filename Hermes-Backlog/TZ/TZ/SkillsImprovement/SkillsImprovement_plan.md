# Пофайловый план реализации SkillsImprovement (Блок 1А)

**Источник:** `TZ/SkillsImprovement/SkillsImprovement_TZ.md`
**Порядок:** волны 1→10 строго. Исполнитель (`composer-2.5` через Cursor CLI), архитектор код не пишет.
**Прогресс (чекбоксы, исполнитель отмечает у себя):**
- [ ] Волна 1 A0 digest+pack
- [ ] Волна 2 B0 section-patch+verify
- [ ] Волна 3 C0 yaml/canon
- [ ] Волна 4 A1 extract+task_pages
- [ ] Волна 5 B1 userkey batch
- [ ] Волна 6 C1 calendar CSV
- [ ] Волна 7 A2 themes in pack
- [ ] Волна 8 B2 pmo-charter-fill
- [ ] Волна 9 C2 page-to-schedule
- [ ] Волна 10 docs+manifest+restore

## Контекст диска (не менять в реализации)
- `deep-mine-project` канон: `~/hermes-workspace/skills/research/deep-mine-project/` (CLI `init|collect|refresh|digest|mine|analyze|document`, 31 тест, `pack` нет).
- `digest_io.py` пишет digest без валидации тела; `test_digest_contract.py` проверяет только frontmatter + «Источники» первым.
- `cursor_jobs.compress_leaf` после агента сразу ставит `digest_status: fresh` → валидатор ПОСЛЕ `_apply_digest_output`, до `fresh`.
- `analyze()` кормит grok весь `digest/themes` + `_index` → G/H перевести на каталог pack.
- `ProjectConfig` не знает `task_pages`; `pull_seed_tree` тянет только `root` + `pmo_seeds`.
- `tutu-confluence-jira` канон: `~/hermes-workspace/skills/productivity/tutu-confluence-jira/` (только SKILL.md + references, скриптов нет).
- Доноры B2/C2 (`charter-fill`, `project-charter-authoring`, `confluence-doc-edit-cursor`, `confluence-page-editing`) — только `~/.hermes/skills/productivity/`, в workspace нет.
- `CUSTOM_FIELDS` уже содержит `confluence_login`, `confluence_userkey` → B1 не трогает схему AnywhereContacts.
- `gantt_csv_to_gs.fmt_dur` — день/дня/дней (канон); `push_to_gs.fmt_dur` всегда «дней»; MppReader создаёт лист «Задачи». Канон длительностей — `gantt`; лист GS import-профиля — `Лист1`.
- `sync-to-hermes.sh` линкует только скиллы с SKILL.md из workspace → `profiles/default/skills`. Новые скиллы без `restore-all-skills.sh` в default не появятся.
- Overlay TrisigmaFull — боевые данные; `514903239` в MANIFEST есть, `519487958`/`519489611` — нет. Фикстуры копировать в `tests/fixtures`, live `mine` не гонять.

**Не трогать:** ConfluenceSync, MppReader (`read_mpp.py`/запись .mpp), `tz-compressor-prompt.md`, Gateway, кроны, USERTOOLS-пакеты, `CUSTOM_FIELDS` AnywhereContacts.

---

## Волна 1 — A0 P0: контракт digest + бриф + `pack --task`
**Критерий:** ТЗ 1,2,3,6. 31 теста зелёные. `pack` в `--help`. Журнал→rejected. G без заполненного чеклиста не стартует.

Файлы: `Registries/project-context-compressor-prompt.md` (modify §6-11 запрет журнала); `deep-mine-project/references/overlay-contract.md` (modify); `references/architect-brief.template.md` (create, 6 секций); `references/cli.md` (modify `pack`); `references/roles-and-prompts.md` (modify); `SKILL.md` (modify, version→0.2.0); `scripts/deepmine/digest_validate.py` (create); `digest_io.py` (modify); `cursor_jobs.py` (modify: валидатор после _apply_digest_output, fail→rejected not fresh, `build_analyze_prompt`/`analyze` по pack_dir, `assert_brief_ready`); `digest_run.py` (modify); `pack.py` (create); `cli.py` (modify subparser `pack`, `--task`); `fail.py` (modify EXIT_DIGEST=6); `paths.py` (modify ARCHITECT_BRIEF_TEMPLATE); `tests/fixtures/digest/p514903239_journal.md` + `p514903239_facts.md` (create); `tests/test_digest_contract.py` (modify); `tests/test_pack_task.py` (create); `tests/test_cli_commands.py` (modify); `tests/test_prompt_file.py` (modify).

Функции: `validate_digest_body`, `assert_brief_ready`, `run_pack`; CLI `pack --task`. Тесты unit `not live`. Live `pack --slug TrisigmaFull` — ручная приёмка волны 4.

---

## Волна 2 — B0 P0: section-patch + verify + запрет LLM→storage
**Критерий:** ТЗ 7,8,9.
Файлы (канон `~/hermes-workspace/skills/productivity/tutu-confluence-jira/`): `SKILL.md` (modify, version→1.6.0, секция «Патч секции», чеклист 7 пунктов); `references/section-patch.md` (create); `references/verify-skeleton.md` (create); `scripts/section_patch.py` (create: get/patch/put, find_section_span, без `space`, не читать storage stdin); `scripts/verify_skeleton.py` (create: 7-пунктовый чеклист); `tests/conftest.py` (create); `tests/fixtures/storage_deliveries_ok.xml` + `storage_deliveries_heading_gone.xml` (create); `tests/test_section_patch.py` + `tests/test_verify_skeleton.py` (create). Live PUT — только по явной команде.

---

## Волна 3 — C0 P0: FIELD_MAP + словарь + канон колонок + праздники
**Критерий:** ТЗ 12. `tutu-confluence-jira/scripts/` временный дом ЗАПРЕЩЁН.
Файлы (канон `~/hermes-workspace/skills/productivity/page-to-schedule/`): `SKILL.md` (create stub 0.1.0); `references/FIELD_MAP.template.yaml`; `references/complexity-map.yaml` (менее 1 нед→3, 1 нед→5, 1-2 нед→10, пусто→fail-loud); `references/gs-columns-canon.md` (import 8 кол. + export push_to_gs; лист `Лист1`); `references/rf-holidays.yaml` (2026-2028); `tests/test_c0_contracts.py`. Copировать `fmt_dur`/`fmt_date` в скилл — волна 6; волна 3 — только документ.

---

## Волна 4 — A1 P1: CSV-экстракт + `task_pages`
**Критерий:** ТЗ 4,5.
Файлы: `deep-mine-project/scripts/deepmine/table_extract.py` (create, парсер md+bs4); `project_config.py` (modify `task_pages`); `confluence_pull.py` (modify pull_seed_tree); `cli.py`+collect/refresh (modify `--extract-tables`); `pack.py` (modify резолв task, CSV в PACK, l0_has_table без CSV→fail); `refresh.py` (modify fail-loud); `references/overlay-contract.md`+`cli.md`+`SKILL.md` (modify, version→0.3.0); `Projects/TrisigmaFull/PROJECT.yaml` (modify `task_pages` только); `tests/fixtures/mini_l0/table_page/index.md` (create); `tests/test_table_extract.py`, `tests/test_task_pages.py` (create); `tests/conftest.py` (modify).

---

## Волна 5 — B1 P1: батч-резолв userkey
**Критерий:** ТЗ 10.
Файлы: `tutu-confluence-jira/scripts/userkey_resolve.py` (create: extract_userkeys, resolve с кэшем, write в contacts.enc через ContactStore, не /user/search); `SKILL.md` (modify version→1.7.0); `tests/test_userkey_resolve.py`. AnywhereContacts/schema.py НЕ менять.

---

## Волна 6 — C1 P1: complexity→duration + календарь
**Критерий:** ТЗ 13,14,16.
Файлы: `page-to-schedule/scripts/complexity_duration.py`, `working_calendar.py`, `build_import_csv.py`, `check_field_map.py` (create); `tests/test_complexity_duration.py`, `test_working_calendar.py`, `test_build_import_csv.py` (create); `SKILL.md` (modify). `fmt_dur`/`fmt_date` — копия `gantt_csv_to_gs` (день/дня/дней + `пн DD.MM.YY`).

---

## Волна 7 — A2 P2: theme-digest в pack
**Критерий:** pack кладёт релевантные themes из PROJECT.yaml.themes; theme из листьев; контракт «нет журнала».
Файлы: `pack.py` (modify themes); `cursor_jobs.py` (modify compress_theme уже валидируется волной 1); `SKILL.md`+`cli.md`+`overlay-contract.md` (modify version→0.4.0); `tests/test_pack_task.py` (modify).

---

## Волна 8 — B2 P2: `pmo-charter-fill` + консолидация
**Предусловие:** волна 2 зелёная. **Критерий:** ТЗ 11. Канон новых: `~/hermes-workspace/skills/productivity/`.
Файлы: `pmo-charter-fill/SKILL.md` (create, оркестрация 3 пачки grok + цифры скриптом + B0 вставка, version 1.0.0); `references/pro-field-catalog.md`, `invariants-checklist.md`, `architect-brief.template.md` (symlink/копия на deep-mine) (create); `scripts/fot_budget.py` (create: parse_hours, ceil, бюджет=vendor+rate×hours); `tests/test_fot_budget.py`, `test_skill_triggers.py` (create).
Redirect доноров (workspace create + `~/.hermes/skills` modify): `charter-fill`, `project-charter-authoring`, `confluence-doc-edit-cursor` → pmo-charter-fill; `confluence-page-editing` → page-edit B0 / план-график page-to-schedule. После: `restore-all-skills.sh`. Не рестартить Gateway.

---

## Волна 9 — C2 P2: скилл `page-to-schedule`
**Критерий:** ТЗ 12-16. Не пишет .mpp.
Файлы: `page-to-schedule/SKILL.md` (modify, полный пайплайн); `scripts/push_import_gs.py` (create, лист `Лист1`, reuse MppReader OAuth); `scripts/cli.py` (create, шаг 0=check_field_map); `tests/test_skill_pipeline.py` (create); `confluence-page-editing/SKILL.md` (workspace create + .hermes modify redirect).

---

## Волна 10 — документация и манифест
**Критерий:** секция-ссылка без дубля; инвентарь/манифест согласованы; скиллы в default после restore.
Файлы: `TZ/deep-mine-project/deep-mine-project_TZ.md` (modify ссылка-секция); `TZ/MAIN_TZ_INVENTORY.md` (modify); `Registries/EcosystemManifest.json` (modify skills/tools/links) + `render_manifest.py --render`/`--digest`; `~/hermes-workspace/restore-all-skills.sh` (run, not edit). Confluence не писать.

---

## Сводная таблица файлов
См. полный план в командном выводе архитектора. Ключевые create: `digest_validate.py`, `pack.py`, `architect-brief.template.md`, `section_patch.py`, `verify_skeleton.py`, `userkey_resolve.py`, `table_extract.py`, `complexity_duration.py`, `working_calendar.py`, `build_import_csv.py`, `page-to-schedule/**`, `pmo-charter-fill/**`.

**Не создавать:** USERTOOLS/SkillsImprovement, USERTOOLS/DeepMine*, USERTOOLS/CharterFill, кроны, правки ConfluenceSync/MppReader/AnywhereContacts schema.

## Порядок исполнения
Исполнитель идёт по волнам 1→10. После каждой волны — pytest скилла (`-m "not live"`) + критерий. Live Confluence/GS — только по явной команде. Мелкое отклонение (≤2 файла) — исполнитель сам; крупное — стоп, доплан архитектора.