# HF:plan — Модуль 0 (OverlayConfig), волна 0

session_id: eeb21085-6681-455d-9069-c5caf2b49e78

---

Читаю полный канон и входные артефакты волны 0 — без обрезки и без записи на диск.Читаю схему манифеста, живой JSON, env-лоадер и постановку модуля 0 — без обрезки.Достаю ключи `tools{}`, путь `render_manifest.py` и чеклисты скиллов — без записи на диск.План волны 0: каркас OverlayConfig (схема `config` 0.6.0, YAML+схема, лоадер dual-read/`explain`, все `tools{}` → `not_started`). Код и тесты — этот `HF-TAIL`; AC-007…017 закрываются волнами 1–4. На диск ничего не записывал.

Факт диска (2026-09-30): манифест `schema_version: "0.5.0"`, top-level `config` нет, `tools{}` = 46 ключей; `EcosystemConfig.yaml` / `.schema.json` / `usertools_config.py` отсутствуют; `usertools_env.py` — только shared+local `.env` через `setdefault`, без YAML. `jsonschema` 4.26.0 и `yaml` 6.0.3 уже импортируются. `render_manifest.py --digest` считает tools/entities/applications, конфиг не печатает. Пилоты волны 1: у FirefliesAutojoin / MoveFromFF / ConfluenceSync есть корневой `.env` и пакетный `config.py`; у ProtocolFromSummary — `config.py`, корневого `.env` нет. Новый ключ в `tools{}` не заводится (reuse-first: расширяется `usertools_env.py`).

---

## 1. План IAC

| IAC-## | phase_from→phase_to | path | verify | depends | covers AC-### |
|---|---|---|---|---|---|
| IAC-01 | `HF:impl`→`HF:test` | `/home/tkachenkoav/WorkVault/Registries/EcosystemManifest.schema.json` | Аддитивный enum `status` в `EcosystemManifest.schema.json` расширяется до `["active","draft","paused","archived","completed","released"]` при бампе 0.5.0→0.6.0. Причина: живой `tools{}` содержит EditPlanConfluence (`edit_plan_confluence`) со `status="released"`, иначе IAC-08 / Draft7Validator упадёт на валидации. `python3 -c 'from jsonschema import Draft7Validator; import json; from pathlib import Path; s=json.loads(Path("/home/tkachenkoav/WorkVault/Registries/EcosystemManifest.schema.json").read_text()); Draft7Validator.check_schema(s); assert "config" in s["required"]; assert s.get("additionalProperties") is False; assert set(["path","schema_path","tools"]).issubset(s["properties"]["config"]["properties"]); assert "migration_status" in json.dumps(s); assert s["definitions"]["tool"]["properties"]["status"]["enum"]==["active","draft","paused","archived","completed","released"]'` ; `rg -n '"0\.4\.0"' /home/tkachenkoav/WorkVault/Hermes-Backlog/TZ/EcosystemIntegration/EcosystemIntegration_TZ.md` — исторический H2 на месте, не этот diff | — | AC-001 (схема) |
| IAC-02 | `HF:impl`→`HF:test` | `/home/tkachenkoav/WorkVault/Registries/EcosystemConfig.schema.json` | `python3 -c 'from jsonschema import Draft7Validator; import json; from pathlib import Path; s=json.loads(Path("/home/tkachenkoav/WorkVault/Registries/EcosystemConfig.schema.json").read_text()); Draft7Validator.check_schema(s); assert "shared" in s["required"] and "tools" in s["required"]'` ; негатив: YAML с ключом `FOO_TOKEN` / `*SECRET*` / `*PASSWORD*` / `*API_KEY*` → `Draft7Validator(schema).validate(doc)` бросает | IAC-01 | AC-002 (схема YAML), AC-019 (бизнес-YAML не в required) |
| IAC-03 | `HF:impl`→`HF:test` | `/home/tkachenkoav/WorkVault/Registries/EcosystemConfig.yaml` | `python3 -c 'import json,yaml; from jsonschema import Draft7Validator; from pathlib import Path; doc=yaml.safe_load(Path("/home/tkachenkoav/WorkVault/Registries/EcosystemConfig.yaml").read_text()); sch=json.loads(Path("/home/tkachenkoav/WorkVault/Registries/EcosystemConfig.schema.json").read_text()); Draft7Validator(sch).validate(doc); m=json.loads(Path("/home/tkachenkoav/WorkVault/Registries/EcosystemManifest.json").read_text()); assert set(doc["tools"])==set(m["tools"]); assert all("enabled" in v for v in doc["tools"].values())'` ; `rg -i 'TOKEN\|SECRET\|PASSWORD\|API_KEY' /home/tkachenkoav/WorkVault/Registries/EcosystemConfig.yaml` → 0; `rg -n 'loop_rules\|contract_rules\|translit' /home/tkachenkoav/WorkVault/Registries/EcosystemConfig.yaml` → 0 | IAC-02 | AC-002 (SoT), AC-019 |
| IAC-04 | `HF:impl`→`HF:test` | `/home/tkachenkoav/.hermes/lib/usertools_config.py` (+ импорт `/home/tkachenkoav/.hermes/lib/usertools_env.py`, **без** замены API env-лоадера) | `python3 -c 'import ast,pathlib; p=pathlib.Path("/home/tkachenkoav/.hermes/lib/usertools_config.py"); t=ast.parse(p.read_text()); assert p.exists(); src=p.read_text(); assert "usertools_env" in src and "get_llm" in src'` ; `python3 /home/tkachenkoav/.hermes/lib/usertools_config.py explain fireflies_autojoin` — каждая строка содержит `source=` ∈ `{process_env,overlay,ecosystem_config,shared,hermes_llm,tool_llm,shared_env,legacy}` ; `python3 /home/tkachenkoav/.hermes/lib/usertools_config.py explain protocol_from_summary` — есть `enabled` с `source=ecosystem_config` (корневого `.env` нет) ; `python3 -m pytest /home/tkachenkoav/WorkVault/Registries/test_usertools_config.py -q` — каскад на **фикстуре** `dual_read` (process env > overlay > `tools.<key>` > `shared` > Hermes LLM / `tools.<key>.llm` > shared `.env` > legacy); соседний tool без overlay не меняется; секреты в stdout `explain` не печатаются | IAC-03 | AC-003, AC-004, AC-005 |
| IAC-05 | `HF:impl`→`HF:test` | `/home/tkachenkoav/WorkVault/Registries/render_manifest.py` (`render_digest`) + `/home/tkachenkoav/WorkVault/Registries/test_render_manifest.py` | `python3 -m pytest /home/tkachenkoav/WorkVault/Registries/test_render_manifest.py -q -k digest` ; фикстура digest содержит путь `EcosystemConfig.yaml` и счётчики `not_started`/`dual_read`/`accepted`/`unified_only`; `rg -i 'TOKEN\|SECRET\|PASSWORD\|API_KEY\|sk-\|Bearer ' /tmp/digest-fixture.md` → 0; значений YAML-ключей в digest нет | IAC-01, IAC-04 | AC-006 |
| IAC-06 | `HF:test`→`HF:test` | пакет тестов: `test_usertools_config.py` + расширение `test_render_manifest.py` + валидация схем | `cd /home/tkachenkoav/WorkVault/Registries && python3 -m pytest test_usertools_config.py test_render_manifest.py -q` — exit 0 | IAC-01…IAC-05 | AC-001…AC-006 |
| IAC-07 | `HF:docs-handoff`→`ORCH:shared-state` | `/home/tkachenkoav/hermes-workspace/skills/devops/tz-workflow/SKILL.md` (`## Verification Checklist`) и `/home/tkachenkoav/hermes-workspace/skills/devops/hermes-feature/SKILL.md` (тот же раздел); bump frontmatter | `rg -n 'EcosystemConfig.yaml' /home/tkachenkoav/hermes-workspace/skills/devops/tz-workflow/SKILL.md /home/tkachenkoav/hermes-workspace/skills/devops/hermes-feature/SKILL.md` ; пункт: новый конфиг-ключ только в YAML+схеме; литерал пути/модели/токена и новый per-tool `.env` = дефект; dual-read запрещён для **новых** tools ; после записи — `restore-all-skills.sh` на `ORCH:shared-state` | IAC-04 | AC-018 |
| IAC-08 | `ORCH:shared-state`→`GATE:done` | `/home/tkachenkoav/WorkVault/Registries/EcosystemManifest.json` — **только оркестратор** (`schema_version: "0.6.0"` + `config.path` / `config.schema_path` / `config.tools.<key>` на **все 46** ключей `tools{}`: `migration_status: not_started`, `overlay: null`, `rollback_snapshot: null`) | `python3 -c 'import json; from jsonschema import Draft7Validator; from pathlib import Path; m=json.loads(Path("/home/tkachenkoav/WorkVault/Registries/EcosystemManifest.json").read_text()); s=json.loads(Path("/home/tkachenkoav/WorkVault/Registries/EcosystemManifest.schema.json").read_text()); Draft7Validator(s).validate(m); assert m["schema_version"]=="0.6.0"; assert set(m["config"]["tools"])==set(m["tools"]); assert all(v["migration_status"]=="not_started" for v in m["config"]["tools"].values()); assert "usertools_config" not in m["tools"] and "overlay_config" not in m["tools"]'` | IAC-01, IAC-03 | AC-001 (живой JSON), AC-003 (нет USERTOOL) |
| IAC-09 | `ORCH:shared-state`→`GATE:done` | `/home/tkachenkoav/WorkVault/Registries/EcosystemManifest.digest.md` (генерация, не ручная правка) | `python3 /home/tkachenkoav/WorkVault/Registries/render_manifest.py --digest` ; `rg -n 'EcosystemConfig.yaml\|not_started=' /home/tkachenkoav/WorkVault/Registries/EcosystemManifest.digest.md` ; `rg -i 'TOKEN\|SECRET\|PASSWORD\|API_KEY' /home/tkachenkoav/WorkVault/Registries/EcosystemManifest.digest.md` → 0 | IAC-05, IAC-08 | AC-006 (боевой digest) |
| IAC-10 | `HF:test`→`GATE:done` | негатив волны 0: legacy на месте, пилоты не `dual_read` | `test -f /home/tkachenkoav/USERTOOLS/FirefliesAutojoin/.env && test -f /home/tkachenkoav/USERTOOLS/MoveFromFF/.env && test -f /home/tkachenkoav/USERTOOLS/ConfluenceSync/.env` ; `python3 -c 'import json; from pathlib import Path; c=json.loads(Path("/home/tkachenkoav/WorkVault/Registries/EcosystemManifest.json").read_text())["config"]["tools"]; keys=["fireflies_autojoin","move_from_ff","confluence_sync","protocol_from_summary"]; assert all(c[k]["migration_status"]=="not_started" for k in keys)'` ; `rg -n 'USERTOOLS_CONFIG_MODE' /home/tkachenkoav/.hermes/lib/usertools_config.py` — ветка **есть** (вырез — волна 4) | IAC-08 | AC-007 (pre: ещё не dual_read), AC-011 (pre: не удалять) |
| IAC-11 | `HF:test`→`HF:test` | бизнес-YAML вне OverlayConfig | `find /home/tkachenkoav/USERTOOLS -name 'loop_rules.yaml' -o -name 'contract_rules.yaml' -o -name 'translit.yaml'` — снимок путей до/после `HF:impl` совпадает (0 удалений); `rg -n 'loop_rules.yaml\|contract_rules.yaml\|translit.yaml' /home/tkachenkoav/WorkVault/Registries/EcosystemConfig.schema.json` → 0 в `required` | IAC-03 | AC-019 |
| IAC-12 | `HF:test`→`GATE:done` | master-ТЗ §10 якоря (код не трогает §§1–9) | `rg -n '### AC-0(0[1-9]\|1[0-9]\|20) ' /home/tkachenkoav/WorkVault/Hermes-Backlog/TZ/EcosystemIntegration/EcosystemIntegration_TZ.md` — 20 якорей; `rg -n '^\*\*I1\.\*\*\|^\*\*I2 \(каскад\)\.\*\*' /home/tkachenkoav/WorkVault/Hermes-Backlog/TZ/EcosystemIntegration/EcosystemIntegration_TZ.md` ; `rg -n 'schema_version.*0\.4\.0' /home/tkachenkoav/WorkVault/Hermes-Backlog/TZ/EcosystemIntegration/EcosystemIntegration_TZ.md` в блоке `## Контракты экосистемы` после §8 — без diff этого пакета | — | AC-020 |
| IAC-13 | `HF:impl`→`HF:test` **волна 1** (не этот `HF:impl`) | runtime пилотов: `~/USERTOOLS/{FirefliesAutojoin,MoveFromFF,ConfluenceSync,ProtocolFromSummary}` + YAML `tools.<key>` + `config.tools.<key>.migration_status=dual_read` | `python3 ~/.hermes/lib/usertools_config.py explain <pilot>` — на совпадающем ключе YAML побеждает литерал/`.env`; сосед без overlay неизменен ; `python3 -c '… assert status=="dual_read" for four keys'` | IAC-08…IAC-10 | AC-007 |
| IAC-14 | `HF:test`→`ORCH:shared-state` **волны 1–2 (per-tool), волна 3 пакет** | улики accepted: stdout `explain` + cron `~/.hermes/cron/output/<job_id>/` или дневной прогон + ErrorBus | (a) `explain` без `source=legacy`/`source=overlay` ; (b) ≥3 подряд успешных тика **или** 1 рабочий день ; (c) нет новых ErrorBus-событий tool про config/env/missing key/YAML parse. Артефакт: файл улик + job_id | IAC-13 | AC-008 |
| IAC-15 | `ORCH:shared-state`→`GATE:done` **после реплики** | `EcosystemManifest.json` `config.tools.<key>.migration_status` ; body карточки `ORCH:shared-state` | Наблюдаемо 1:1: body содержит `Q-n` + `tool_key:` или `package_keys:` ; на `GATE:done`/корне `operator-done: answer:Q-n` + `evidence:` (ISO + цитата) ; **только после этого** статус `accepted`. **O `answer:Q-n`** | IAC-14 | AC-009 |
| IAC-16 | `ORCH:shared-state`→`GATE:done` | `config.tools.<key>.rollback_snapshot` → `~/.hermes/_Archives/ecosystem-config/<tool>/<timestamp>.yaml` | `test -f "$(python3 -c 'import json;from pathlib import Path; m=json.loads(Path("/home/tkachenkoav/WorkVault/Registries/EcosystemManifest.json").read_text()); print(m["config"]["tools"]["<key>"]["rollback_snapshot"])')"` | IAC-15 | AC-010 |
| IAC-17 | `HF:impl`→`HF:test` **после accepted** | overlay / per-tool `.env` / литералы в `config.py` этого tool | **O `удаляй`**: без `operator-done: удаляй` + evidence файлы не сносить ; после императива: overlay нет, пустой `.env` нет, уникальные секреты уже в `~/.config/hermes/.env`, тонкая оболочка `config.py` допустима ; `rg -n 'TOKEN\|model.*=\|Path\("/home' <tool>/config.py` без секретов/литералов путей | IAC-15, IAC-16 | AC-011 |
| IAC-18 | `HF:test`→`HF:test` | лоадер на already-accepted tool | `python3 ~/.hermes/lib/usertools_config.py explain <tool> \| rg 'source=(overlay\|legacy)'` → 0 ; отсутствующий ключ → exit ≠ 0 (даже если старый файл ещё на диске до IAC-17) ; `enabled: false` останавливает tool без restore | IAC-15 | AC-012 |
| IAC-19 | `HF:test`→`HF:test` **пока dual_read** | process env `USERTOOLS_CONFIG_MODE=legacy` **или** overlay одного tool | `USERTOOLS_CONFIG_MODE=legacy python3 ~/.hermes/lib/usertools_config.py explain <tool>` возвращает legacy ; без переменной `explain <neighbor>` bit-identical с контрольным снятием до теста | IAC-13 | AC-013 |
| IAC-20 | `HF:test`→`HF:test` **после accepted** | restore секции YAML из `rollback_snapshot` | restore поднимает несекретные ключи этого tool ; `rg 'local_env_path\|source=legacy' ` ветки чтения старого `.env` **для этого tool** нет | IAC-16, IAC-17 | AC-014 |
| IAC-21 | `HF:impl`→`HF:test` **волна 4** | `usertools_config.py` | Когда все `active`/`draft`/`paused` = `unified_only`: `rg -n 'overlay\|legacy\|USERTOOLS_CONFIG_MODE' /home/tkachenkoav/.hermes/lib/usertools_config.py` → 0 по веткам чтения ; нет ключа → fail loud ; digest `unified_only=` = число таких tools | IAC-17 (все живые tools) | AC-015 |
| IAC-22 | `HF:impl`→`HF:test` **волна 4** | осиротевшие per-tool `.env` и ссылки в коде/скиллах | **O `удаляй`**: `find ~/USERTOOLS -name '.env' -empty` → 0 боевых ; `rg -n 'USERTOOLS/.*/\.env' ~/.hermes/skills ~/hermes-workspace/skills` без мёртвых ссылок ; IAC-11 (бизнес-YAML) зелёный | IAC-21 | AC-016 |
| IAC-23 | `HF:test`→`GATE:done` **волна 4** | `/home/tkachenkoav/WorkVault/Registries/render_manifest.py --check-drift` | `python3 /home/tkachenkoav/WorkVault/Registries/render_manifest.py --check-drift` — нет drift «второй SoT конфига» ; `rg -n 'MAIN_TZ_INVENTORY' /home/tkachenkoav/WorkVault/Registries/render_manifest.py` в `check_drift` → 0 чтений инвентаря (§9.4) | IAC-21 | AC-017 |

Этот `HF:impl` / `HF:test` исполняет **IAC-01…IAC-07, IAC-10…IAC-12**. Живой манифест и боевой digest — **IAC-08…IAC-09** на `ORCH:shared-state`. IAC-13…IAC-23 — волны 1–4, в covers модуля 0, не в объёме текущей волны 0.

`HF:backup` до `HF:impl`: `~/.hermes/_Archives/hermes-backup-YYYYMMDD-HHMMSS/` (схема, `render_manifest.py`, `usertools_env.py`, скиллы). G3: пути из `HF:impl`, лежащие в git-worktree (`hermes-workspace/skills`, при наличии git у `Registries`), коммитятся исполнителем; `~/.hermes/lib` — наличие на диске, если дерево не git.

---

## 1.1 Подтверждённый риск (Q-2 закрыт)

**Q-2.** Live `Draft7Validator` на текущем `EcosystemManifest.json` может упасть на **предсуществующих** расхождениях 0.5.0 (не модуль 0): `updated_at` = `2026-09-30T13:22:30Z` при `"format": "date"`; в схеме `status` enum без `released`, если такой статус есть на диске.

**Зафиксированное решение (REV:plan `t_cc070a0d`):** не открытый вопрос. (1) Аддитивный enum `status` в `EcosystemManifest.schema.json` при бампе 0.5.0→0.6.0 = `["active","draft","paused","archived","completed","released"]` — строка IAC-01; живой `tools.edit_plan_confluence.status="released"` (EditPlanConfluence) не править на `ORCH:shared-state`. (2) Полный документ валидировать **без** format-checker (`Draft7Validator(s).validate(m)` без `format_checker=` в IAC-08). Не ретрофитить H2 `"0.4.0"`. Не переписывать §§1–9.

---

## 2. Open-questions

Не задаю Саше напрямую. Оркестратор закрывает на `GATE:plan-approve` (рекомендация = default исполнителя, пока нет иного решения).

**Q-1.** `GATE:done` графа `DEV/eco-config` закрывает только волну 0 (IAC-01…12, AC-001…006/018…020) или весь модуль 0 до волны 4?  
Рекомендация: **только волна 0**. Иначе preflight `GATE:done` упрётся в O-holds AC-009/011/016 по десяткам tools. Волны 1–4 — отдельные графы того же эпика (или поздние `HF:impl` после явного расширения оркестратором).

**Q-3.** Что класть в `shared:` на волне 0?  
Рекомендация: **`shared: {}`**. Не выдумывать `logs_root` и новые пути (reuse-first). Ключи `shared` — когда появится реальный общий несекретный факт на волне 1+.

**Q-4.** `enabled` для `archived`/`completed` на волне 0?  
Рекомендация: `enabled: false` для `archived`/`completed`, `true` для остальных; `migration_status: not_started` у **всех 46** ключей `tools{}` (включая archived) — как «все существующие tools» в §10.7.

**Q-5.** Semver YAML-схемы?  
Рекомендация: **`0.1.0`** в `EcosystemConfig.yaml` / `EcosystemConfig.schema.json` (независим от манифеста 0.6.0).

---

## 3. AC-класса O (приёмка Вариант 1)

Durable operator-holds. **Не исполняются на волне 0.** Не ставить `operator-done` без факта. Словарь глаголов закрытый.

| AC | class | verb | Когда hold живой | Что должен сделать Саша | Снятие |
|---|---|---|---|---|---|
| **AC-009** | O | `answer:Q-n` | Волны 1–2: каждый пилот/остальной tool; волна 3: одна пакетная реплика на `package_keys` | Явная реплика «принять / не принять» по `Q-n` на карточке `ORCH:shared-state` (body: `Q-n` + `tool_key:` или `package_keys:`) | `operator-done: answer:Q-n` + `evidence:` (ISO + цитата) на `GATE:done` или корне → **затем** `migration_status: accepted`. Без реплики статус не менять, legacy не удалять |
| **AC-011** | O | `удаляй` | Уже `accepted` tool, отдельный императив | «Работает, удаляй legacy» (overlay / пустой `.env` / литералы этого tool) | `operator-done: удаляй` + evidence (какие пути снесены, ISO). Уникальные секреты в shared `.env` **до** удаления |
| **AC-016** | O | `удаляй` | Волна 4, после IAC-21 | Снести осиротевшие пустые `.env` и мёртвые ссылки | `operator-done: удаляй` + evidence. Бизнес-YAML не в этом императиве (AC-019) |

Остальные AC модуля 0 — класс **S** (поезд не ждёт Сашу): AC-001…008, 010, 012…015, 017…020. AC-008 улики собирает исполнитель; перевод в `accepted` без AC-009 не делается.

На волне 0 **нет** `Q-n` приёмки и **нет** `удаляй`: IAC-10 это проверяет. Hold AC-009/011/016 не должен краснить `GATE:done` волны 0, если Q-1 принят как «волна 0 only» (иначе — Q-1).

---

context-used:
  card: t_e315e706
  root: DEV/eco-config: Единый конфиг экосистемы (модуль 0)
  phase: HF:plan
  tz_version: 0.5.1
  tz_mtime: 2026-09-30T17:55:40Z
  emitted_at: 2026-09-30T18:42:51Z