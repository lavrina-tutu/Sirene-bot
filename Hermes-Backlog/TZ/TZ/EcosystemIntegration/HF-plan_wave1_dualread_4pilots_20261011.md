# HF:plan — Модуль 0 (OverlayConfig), волна 1 (dual_read, 4 пилота)

session_id: `20261011_182315_7d0b0d`  
cursor_conversation_id: `6a37f7c2-f031-41be-b356-c9cda286fca0`

---

План волны 1: перевести ровно 4 пилота на `dual_read` (YAML побеждает overlay/legacy), собрать пакеты улик AC-008 и посадить 4× `Q-n`. `accepted` / `unified_only` / «удаляй» в критерий готовности этой волны **не** входят. На диск ничего не записывал.

Факт диска (2026-10-11): манифест `schema_version: "0.6.0"`, `config.tools` = 46, все `migration_status=not_started`, `overlay=null`, `rollback_snapshot=null`. YAML SoT `schema_version: 0.1.0`, `shared: {}`, у всех 46 ключей только `enabled`. Схема YAML: `tool_section.additionalProperties: string`, `propertyNames` режет `TOKEN|SECRET|PASSWORD|API_KEY`. Лоадер `usertools_config.py` (13 793 б): `resolve_key` 7 слоёв, `explain_tool`, `USERTOOLS_CONFIG_MODE`. Пилоты: FF/MFF/CS — корневой `.env`; PFS — корневого `.env` нет, читает `ConfluenceSync/.env` + литералы `config.py`. `CONFLUENCE_TOKEN` в shared `.env` **отсутствует** (уникальный секрет CS). `--check-drift` сейчас exit 0. Кроны: FF — user crontab `# fireflies-autojoin` (`1-5 9-19`); MFF — `vm_movefromff`; PFS — `pfs_batch`/`pfs_notify`; CS — своего крона нет. Сегодня воскресенье: тики FF до понедельника не идут.

Инвариант runtime (иначе YAML не победит): `config.py` пилота **не** делает `load_usertools_env(local_env_path=…)` на несекреты. `setdefault` из per-tool `.env` поднимает ключ в process env (слой 1) и перекрывает YAML (слой 3). Сейчас `explain fireflies_autojoin` даёт `EXCHANGE_EMAIL source=legacy` — ожидаемо при `not_started` и пустом блоке YAML.

---

## 1. План IAC

| IAC-## | phase_from→phase_to | path | verify | depends | covers AC-### |
|---|---|---|---|---|---|
| IAC-01 | `HF:impl`→`HF:test` | `/home/tkachenkoav/WorkVault/Registries/EcosystemConfig.schema.json` | Бамп YAML-схемы **0.1.0→0.1.1**. В `definitions.tool_section.properties` и `definitions.non_secret_map` (через явные `properties` у `shared` **или** документированный allow-list в `properties` + сохранить `additionalProperties: string`, чтобы волна 2 не ломалась) появляются имена ключей волны 1 (см. §3). `enabled` остаётся boolean, остальные — string. `propertyNames` по-прежнему режет `TOKEN\|SECRET\|PASSWORD\|API_KEY`. `python3 -c 'from jsonschema import Draft7Validator; import json; from pathlib import Path; s=json.loads(Path("/home/tkachenkoav/WorkVault/Registries/EcosystemConfig.schema.json").read_text()); Draft7Validator.check_schema(s); props=s["definitions"]["tool_section"]["properties"]; assert "enabled" in props and props["enabled"]["type"]=="boolean"; assert "EXCHANGE_EMAIL" in props and "WORKVAULT_PATH" in props and "CONFLUENCE_URL" in props and "TELEGRAM_CHAT_ID" in props and "MEETINGS_DIR" in props; assert "CONFLUENCE_TOKEN" not in props and "FIREFLIES_API_KEY" not in props'` ; негатив: YAML с `FOO_TOKEN` → `Draft7Validator` бросает | — | AC-002 (схема до значений), AC-007 (ключи пилотов легальны) |
| IAC-02 | `HF:impl`→`HF:test` | `/home/tkachenkoav/WorkVault/Registries/EcosystemConfig.yaml` (`shared:` + заготовки `tools.<4 keys>`, **ещё без dual_read в манифесте**) | `schema_version: "0.1.1"`. `shared:` только реальные дубли: `WORKVAULT_PATH`, `CONFLUENCE_URL` (см. §3). 42 чужих `tools.<key>` — по-прежнему только `enabled`. `python3 -c 'import json,yaml; from jsonschema import Draft7Validator; from pathlib import Path; doc=yaml.safe_load(Path("/home/tkachenkoav/WorkVault/Registries/EcosystemConfig.yaml").read_text()); sch=json.loads(Path("/home/tkachenkoav/WorkVault/Registries/EcosystemConfig.schema.json").read_text()); Draft7Validator(sch).validate(doc); m=json.loads(Path("/home/tkachenkoav/WorkVault/Registries/EcosystemManifest.json").read_text()); assert set(doc["tools"])==set(m["tools"]); assert doc["schema_version"]=="0.1.1"; assert doc["shared"]["WORKVAULT_PATH"]=="/home/tkachenkoav/WorkVault"; assert doc["shared"]["CONFLUENCE_URL"]=="https://dom.tutu.ru"'` ; `rg -i 'TOKEN\|SECRET\|PASSWORD\|API_KEY' /home/tkachenkoav/WorkVault/Registries/EcosystemConfig.yaml` → 0 ; `rg -n 'loop_rules\|contract_rules\|translit' …/EcosystemConfig.yaml` → 0 | IAC-01 | AC-002, AC-019 |
| IAC-03 | `ORCH:shared-state`→`GATE:done` | `/home/tkachenkoav/.config/hermes/.env` — **только оркестратор** (исполнитель `.env` не пишет) | Уникальный секрет пилота: ключ `CONFLUENCE_TOKEN=` **появляется** в shared `.env` (копия из `ConfluenceSync/.env`, per-tool файл **не** удалять). Уже были и не дублировать: `FIREFLIES_API_KEY`, `LOOP_TOKEN`, `TUTU_DOMAIN_PASSWORD`, `CONTACTS_ENCRYPTION_KEY`, `TELEGRAM_BOT_TOKEN`. Verify **без печати значений**: `python3 -c 'from pathlib import Path; t=Path.home()/".config/hermes/.env"; keys={ln.split("=",1)[0].strip() for ln in t.read_text().splitlines() if ln.strip() and not ln.strip().startswith("#") and "=" in ln}; assert "CONFLUENCE_TOKEN" in keys'` ; `rg -n 'CONFLUENCE_TOKEN' /home/tkachenkoav/WorkVault/Registries/EcosystemConfig.yaml /home/tkachenkoav/WorkVault/Registries/EcosystemManifest.json /home/tkachenkoav/WorkVault/Registries/EcosystemManifest.digest.md` → 0 | IAC-02 | AC-007 (секрет `source=shared_env`), §10.8 |
| IAC-04 | `HF:impl`→`HF:test` | `/home/tkachenkoav/USERTOOLS/FirefliesAutojoin/ffjoin/config.py` + YAML `tools.fireflies_autojoin` | Пилот **по одному**. `config.py` читает несекреты через `usertools_config.load_tool_config("fireflies_autojoin", keys=[…])`. **Запрет:** `load_usertools_env(local_env_path=ROOT/".env")` на основном пути. Ветка `USERTOOLS_CONFIG_MODE=legacy` сохраняет старое чтение `.env` (AC-013). Корневой `.env` на месте. `rg -n 'load_usertools_env\(local_env_path' /home/tkachenkoav/USERTOOLS/FirefliesAutojoin/ffjoin/config.py` — только внутри `if os.environ.get("USERTOOLS_CONFIG_MODE")=="legacy"` ; `test -f /home/tkachenkoav/USERTOOLS/FirefliesAutojoin/.env` ; `python3 -c 'import yaml; from pathlib import Path; t=yaml.safe_load(Path("/home/tkachenkoav/WorkVault/Registries/EcosystemConfig.yaml").read_text())["tools"]["fireflies_autojoin"]; need=["enabled","EXCHANGE_EMAIL","EXCHANGE_SERVER","EXCHANGE_VERIFY_TLS","SKIP_PRIVATE","TIMEZONE","LANGUAGE","CRON_HOURS","CRON_DAYS","ALERT_SMTP_HOST","ALERT_SMTP_PORT"]; assert all(k in t for k in need); assert "EXCHANGE_PASSWORD" not in t and "FIREFLIES_API_KEY" not in t and "LOOP_TOKEN" not in t'` | IAC-02, IAC-03 | AC-007 (FF) |
| IAC-05 | `HF:test`→`HF:test` | смоук + pytest YAML побеждает `.env` у `fireflies_autojoin` | Живой: `python3 -c 'import sys; sys.path.insert(0,"/home/tkachenkoav/.hermes/lib"); import usertools_config as uc; r=uc.resolve_key("fireflies_autojoin","EXCHANGE_EMAIL"); assert r and r.source=="ecosystem_config" and r.value=="tkachenkoav@tutu.ru"'` (при `not_started` YAML-слой уже жив; overlay не нужен). Pytest в `test_usertools_config.py`: фикстура dual_read, `.env` содержит `EXCHANGE_EMAIL=from_env`, YAML `from_yaml` → `source=ecosystem_config` / `from_yaml`. `python3 -m pytest /home/tkachenkoav/WorkVault/Registries/test_usertools_config.py -q -k fireflies` | IAC-04 | AC-007, AC-005 (каскад на пилоте) |
| IAC-06 | `HF:impl`→`HF:test` | `/home/tkachenkoav/USERTOOLS/MoveFromFF/movefromff/config.py` + YAML `tools.move_from_ff` | Несекреты из `.env` → YAML (TOOL_DIR, CONTACTS_PATH, LOGS_PATH, PROJECT_PATH, TELEGRAM_CHAT_ID). `WORKVAULT_PATH` **не** дублировать в `tools.move_from_ff` — брать из `shared:` (reuse-first). Defaults custom-skill/retry из кода/`.env.example` → YAML, чтобы победить литерал. Секреты `FIREFLIES_API_KEY` / `TELEGRAM_BOT_TOKEN` / `CONTACTS_ENCRYPTION_KEY` не в YAML. `load_settings()` на основном пути заполняет pydantic `Settings` из `load_tool_config`; local `.env` только в ветке `legacy`. `test -f /home/tkachenkoav/USERTOOLS/MoveFromFF/.env` ; `python3 -c 'import yaml; from pathlib import Path; t=yaml.safe_load(Path("/home/tkachenkoav/WorkVault/Registries/EcosystemConfig.yaml").read_text())["tools"]["move_from_ff"]; assert "WORKVAULT_PATH" not in t; assert t["TOOL_DIR"].endswith("MoveFromFF"); assert t["TELEGRAM_CHAT_ID"]=="400307920"; assert "FIREFLIES_API_KEY" not in t and "TELEGRAM_BOT_TOKEN" not in t'` | IAC-02, IAC-03 | AC-007 (MFF) |
| IAC-07 | `HF:test`→`HF:test` | YAML побеждает `.env` у `move_from_ff` | `python3 -c 'import sys; sys.path.insert(0,"/home/tkachenkoav/.hermes/lib"); import usertools_config as uc; r=uc.resolve_key("move_from_ff","TOOL_DIR"); assert r.source=="ecosystem_config"; s=uc.resolve_key("move_from_ff","WORKVAULT_PATH"); assert s.source=="shared"'` ; pytest `-k move_from_ff` (фикстура: YAML≠`.env`) | IAC-06 | AC-007, AC-005 |
| IAC-08 | `HF:impl`→`HF:test` | `/home/tkachenkoav/USERTOOLS/ConfluenceSync/confluencesync/config.py` + YAML `tools.confluence_sync` | `CONFLUENCE_URL`/`WORKVAULT_PATH` из `shared:`; `TOOL_DIR`/`LOGS_PATH` в `tools.confluence_sync`. `CONFLUENCE_TOKEN` только shared `.env`. Основной путь: `load_tool_config("confluence_sync")`, **не** `_find_env_file()` и не `MoveFromConfluence/.env`. `_find_env_file` допустим только в ветке `legacy`. `test -f /home/tkachenkoav/USERTOOLS/ConfluenceSync/.env` ; `python3 -c 'import yaml; from pathlib import Path; t=yaml.safe_load(Path("/home/tkachenkoav/WorkVault/Registries/EcosystemConfig.yaml").read_text())["tools"]["confluence_sync"]; assert "CONFLUENCE_TOKEN" not in t and "CONFLUENCE_URL" not in t; assert t["TOOL_DIR"].endswith("ConfluenceSync")'` | IAC-02, IAC-03 | AC-007 (CS) |
| IAC-09 | `HF:test`→`HF:test` | YAML/shared побеждают `.env` у `confluence_sync` | `python3 -c 'import sys; sys.path.insert(0,"/home/tkachenkoav/.hermes/lib"); import usertools_config as uc; u=uc.resolve_key("confluence_sync","CONFLUENCE_URL"); assert u.source=="shared"; t=uc.resolve_key("confluence_sync","TOOL_DIR"); assert t.source=="ecosystem_config"'` ; pytest `-k confluence_sync` | IAC-08 | AC-007, AC-005 |
| IAC-10 | `HF:impl`→`HF:test` | `/home/tkachenkoav/USERTOOLS/ProtocolFromSummary/protocolfromsummary/config.py` + YAML `tools.protocol_from_summary` | Корневого `.env` нет — dual_read обязан взять пути/URL из YAML/shared. Снять `load_usertools_env(local_env_path=ConfluenceSync/.env)` с основного пути. Литералы путей → YAML (MEETINGS_DIR, CONTACTS_ENC, ROOMS_MD, STATE_DIR, PREPARED_PROTOCOLS_DIR, ENTITIES_REGISTRY_PATH, TELEGRAM_NOTIFY_CHAT_ID, TELEGRAM_NOTIFY_THREAD_ID, TELEGRAM_NOTIFY_TARGET). `WORKVAULT_ROOT` = alias на `shared.WORKVAULT_PATH`; `CONFLUENCE_URL` из shared. `ROUTES` по-прежнему из `entities.json`. LLM — `get_llm` / Hermes `config.yaml`, **не** копировать `LLM_FALLBACK_*` в YAML. `test ! -f /home/tkachenkoav/USERTOOLS/ProtocolFromSummary/.env` ; `python3 -c 'import yaml; from pathlib import Path; t=yaml.safe_load(Path("/home/tkachenkoav/WorkVault/Registries/EcosystemConfig.yaml").read_text())["tools"]["protocol_from_summary"]; assert "MEETINGS_DIR" in t and "TELEGRAM_NOTIFY_CHAT_ID" in t; assert "CONFLUENCE_TOKEN" not in t and "llm" not in t'` ; `rg -n 'load_usertools_env\(local_env_path=_CONFLUENCESYNC_ENV\)' …/protocolfromsummary/config.py` — только ветка `legacy` | IAC-02, IAC-03 | AC-007 (PFS) |
| IAC-11 | `HF:test`→`HF:test` | YAML побеждает литерал у `protocol_from_summary` | `python3 -c 'import sys; sys.path.insert(0,"/home/tkachenkoav/.hermes/lib"); import usertools_config as uc; r=uc.resolve_key("protocol_from_summary","MEETINGS_DIR"); assert r.source=="ecosystem_config"; u=uc.resolve_key("protocol_from_summary","CONFLUENCE_URL"); assert u.source=="shared"'` ; pytest `-k protocol_from_summary`: YAML≠литерал `config.py` | IAC-10 | AC-007, AC-005 |
| IAC-12 | `HF:test`→`HF:test` | изоляция остальных 42 | Сосед `move_from_loop` (не пилот). Снимок `explain move_from_loop` **до** IAC-04 сохранить в `/tmp/explain_neighbor_before.txt` на старте `HF:test` (или в фикстуре бэкапа). После IAC-04…11: `diff -u /tmp/explain_neighbor_before.txt <(python3 /home/tkachenkoav/.hermes/lib/usertools_config.py explain move_from_loop)` пустой (допускается только нестабильный `llm`, если менялся Hermes-конфиг — тогда сравнивать без строки `llm`). `python3 -c 'import json; from pathlib import Path; c=json.loads(Path("/home/tkachenkoav/WorkVault/Registries/EcosystemManifest.json").read_text())["config"]["tools"]; pilots={"fireflies_autojoin","move_from_ff","confluence_sync","protocol_from_summary"}; others=[k for k in c if k not in pilots]; assert len(others)==42; assert all(c[k]["migration_status"]=="not_started" for k in others); assert all(c[k].get("overlay") in (None, "null") for k in others)'` — **после** IAC-14 статус пилотов `dual_read`, 42 остаются `not_started`. До IAC-14 все 46 ещё `not_started` | IAC-04…IAC-11 | AC-007 (соседи) |
| IAC-13 | `HF:test`→`HF:test` | пакет pytest | `cd /home/tkachenkoav/WorkVault/Registries && python3 -m pytest test_usertools_config.py test_render_manifest.py -q` — exit 0. Существующие тесты волны 0 не краснеют | IAC-01…IAC-12 | AC-002, AC-005, AC-007 |
| IAC-14 | `ORCH:shared-state`→`GATE:done` | `/home/tkachenkoav/WorkVault/Registries/EcosystemManifest.json` + digest — **только оркестратор** | На 4 ключа: `migration_status: dual_read`, `overlay: null` (файлов overlay не заводим), `rollback_snapshot: null` (снимок — после accepted, AC-010). 42 остальных не трогать. Затем `python3 /home/tkachenkoav/WorkVault/Registries/render_manifest.py --digest`. Verify: `python3 -c 'import json; from pathlib import Path; m=json.loads(Path("/home/tkachenkoav/WorkVault/Registries/EcosystemManifest.json").read_text()); c=m["config"]["tools"]; p=["fireflies_autojoin","move_from_ff","confluence_sync","protocol_from_summary"]; assert all(c[k]["migration_status"]=="dual_read" for k in p); assert all(c[k].get("overlay") in (None,"null") for k in p); assert sum(1 for v in c.values() if v["migration_status"]=="not_started")==42; assert "usertools_config" not in m["tools"]'` ; `rg -n 'dual_read=4\|not_started=42' /home/tkachenkoav/WorkVault/Registries/EcosystemManifest.digest.md` ; `rg -i 'TOKEN\|SECRET\|PASSWORD\|API_KEY' …digest.md` → 0 | IAC-04…IAC-11 | AC-007 (статус), AC-006 (счётчики), §10.10 |
| IAC-15 | `HF:test`→`HF:test` | пакет улик `fireflies_autojoin` | **Ключевой набор** (не весь dump shared `.env`): `EXCHANGE_EMAIL EXCHANGE_SERVER EXCHANGE_VERIFY_TLS SKIP_PRIVATE TIMEZONE LANGUAGE CRON_HOURS CRON_DAYS ALERT_SMTP_HOST ALERT_SMTP_PORT enabled`. (a) `python3 ~/.hermes/lib/usertools_config.py explain fireflies_autojoin` — для этого набора 0× `source=legacy`/`source=overlay`; несекреты `source=ecosystem_config`; `FIREFLIES_API_KEY`/`LOOP_TOKEN`/`TUTU_DOMAIN_PASSWORD` → `source=shared_env` (если процесс уже экспортировал секрет как process env — гонять explain в чистой оболочке: `env -u FIREFLIES_API_KEY -u LOOP_TOKEN -u TUTU_DOMAIN_PASSWORD python3 … explain …`). (b) user crontab `# fireflies-autojoin`: ≥3 подряд успешных `tick` в `~/USERTOOLS/FirefliesAutojoin/logs/cron.log` **в будни 9–19** **или** 1 рабочий день. Сегодня вс — тиков нет до пн; не ставить новый крон. (c) ErrorBus: `python3 -c 'import sqlite3; from pathlib import Path; con=sqlite3.connect(Path.home()/".hermes/error_bus/events.db"); print(con.execute("select count(*) from errors where tool in (\"FirefliesAutojoin\",\"fireflies_autojoin\",\"ffjoin\") and last_seen>=? and (lower(message) like \"%config%\" or lower(message) like \"%env%\" or lower(message) like \"%yaml%\" or lower(message) like \"%missing%\")", ("<ISO-start-window>",)).fetchone()[0])'` → 0. Артефакт: `TZ/EcosystemIntegration/evidence_wave1_fireflies_autojoin.md` (stdout explain + хвост cron.log + count ErrorBus) | IAC-14 | AC-008 (FF) |
| IAC-16 | `HF:test`→`HF:test` | пакет улик `move_from_ff` | Ключи: `TOOL_DIR PROJECT_PATH CONTACTS_PATH LOGS_PATH TELEGRAM_CHAT_ID` + `WORKVAULT_PATH source=shared` + секреты `FIREFLIES_API_KEY`/`TELEGRAM_BOT_TOKEN` → `shared_env`. (b) `~/.hermes/cron/output/vm_movefromff/` — ≥3 подряд `last_status=ok` job `vm_movefromff` **или** 1 рабочий день. (c) ErrorBus `tool in ("MoveFromFF","move_from_ff","vm_movefromff")` без новых config/env/yaml/missing. Артефакт `evidence_wave1_move_from_ff.md` | IAC-14 | AC-008 (MFF) |
| IAC-17 | `HF:test`→`HF:test` | пакет улик `confluence_sync` | Ключи: `TOOL_DIR LOGS_PATH` + `CONFLUENCE_URL`/`WORKVAULT_PATH` `source=shared` + `CONFLUENCE_TOKEN source=shared_env`. Своего крона нет — **не создавать**. (b) по §10.6: ≥1 реальный CLI-вызов (`confluencesync log --tail 5` недостаточен как цикл; допустим идемпотентный `confluencesync pull` уже известной страницы **или** 1 рабочий день тишины ErrorBus после dual_read). (c) ErrorBus `tool in ("ConfluenceSync","confluence_sync")` → 0 новых config/env/yaml. Артефакт `evidence_wave1_confluence_sync.md` | IAC-14 | AC-008 (CS) |
| IAC-18 | `HF:test`→`HF:test` | пакет улик `protocol_from_summary` | Ключи YAML-набора PFS + `CONFLUENCE_URL`/`WORKVAULT_PATH` `source=shared` + `CONFLUENCE_TOKEN`/`CONTACTS_ENCRYPTION_KEY` `source=shared_env`. (b) job `a6e62d06249f` (`pfs_batch`) и/или `21255143c523` (`pfs_notify`): ≥3 подряд ok **или** 1 рабочий день. Логи: `~/.hermes/cron/output/a6e62d06249f/`, `…/21255143c523/`. (c) ErrorBus `tool in ("ProtocolFromSummary","protocol_from_summary","a6e62d06249f","21255143c523")` без новых config/env/yaml/missing. Артефакт `evidence_wave1_protocol_from_summary.md` | IAC-14 | AC-008 (PFS) |
| IAC-19 | `ORCH:shared-state`→`GATE:done` | body карточки(ек) `ORCH:shared-state` — **оркестратор**, не исполнитель | После зелёных IAC-15…18, **не** раньше: на каждый пилот `Q-n` + `tool_key: <key>` + «принять / не принять» + `depends: operator:answer:Q-n`. Четыре пилота → четыре `Q-n` (если в графе одна карточка ORCH — `Q-1`…`Q-4` с уникальным `n` на этой карточке; identity `(card_id, n)`). **Не** писать `accepted`. Verify: body содержит четыре пары `Q-n`/`tool_key`. Снятие hold — вне этой волны (см. §5) | IAC-15…IAC-18 | AC-009 (посадка вопроса, не ответ) |
| IAC-20 | `HF:test`→`HF:test` | откат dual_read, соседи целы | На каждом из 4: `USERTOOLS_CONFIG_MODE=legacy python3 ~/.hermes/lib/usertools_config.py explain <pilot>` — мигрированные ключи, которые ещё живут в `.env`/литералах, дают `source=legacy` (PFS: литералы/`ConfluenceSync/.env` в ветке legacy). Без переменной `explain move_from_loop` bit-identical со снимком IAC-12. Overlay-файл **не** обязателен (AC-013: mode **или** overlay). `test ! -f /home/tkachenkoav/USERTOOLS/FirefliesAutojoin/config.overlay.yaml && test ! -f /home/tkachenkoav/USERTOOLS/MoveFromFF/config.overlay.yaml && test ! -f /home/tkachenkoav/USERTOOLS/ConfluenceSync/config.overlay.yaml && test ! -f /home/tkachenkoav/USERTOOLS/ProtocolFromSummary/config.overlay.yaml` | IAC-14 | AC-013 |
| IAC-21 | `HF:test`→`GATE:done` | `/home/tkachenkoav/WorkVault/Registries/render_manifest.py --check-drift` | `python3 /home/tkachenkoav/WorkVault/Registries/render_manifest.py --check-drift` — exit 0 (базовая линия уже 0; новых drift_type про второй SoT конфига нет). Per-tool `.env` пилотов **не** считать вторым SoT на dual_read. `rg -n 'MAIN_TZ_INVENTORY' /home/tkachenkoav/WorkVault/Registries/render_manifest.py` → 0. Не добавлять второй YAML-канон | IAC-02, IAC-14 | AC-017 |
| IAC-22 | `HF:test`→`GATE:done` | бизнес-YAML пилотов | `find /home/tkachenkoav/USERTOOLS/FirefliesAutojoin /home/tkachenkoav/USERTOOLS/MoveFromFF /home/tkachenkoav/USERTOOLS/ConfluenceSync /home/tkachenkoav/USERTOOLS/ProtocolFromSummary \( -name 'loop_rules.yaml' -o -name 'contract_rules.yaml' -o -name 'translit.yaml' \)` — снимок до/после `HF:impl` совпадает (сейчас 0 файлов — 0 удалений). `rg -n 'loop_rules.yaml\|contract_rules.yaml\|translit.yaml' /home/tkachenkoav/WorkVault/Registries/EcosystemConfig.yaml /home/tkachenkoav/WorkVault/Registries/EcosystemConfig.schema.json` → 0. `ROUTES`/entities.json PFS не переносить в YAML | IAC-10 | AC-019 |
| IAC-23 | `HF:test`→`GATE:done` | негатив волны 1: не accepted, legacy на диске, fallback в лоадере | `test -f /home/tkachenkoav/USERTOOLS/FirefliesAutojoin/.env && test -f /home/tkachenkoav/USERTOOLS/MoveFromFF/.env && test -f /home/tkachenkoav/USERTOOLS/ConfluenceSync/.env && test ! -f /home/tkachenkoav/USERTOOLS/ProtocolFromSummary/.env` ; `python3 -c 'import json; from pathlib import Path; c=json.loads(Path("/home/tkachenkoav/WorkVault/Registries/EcosystemManifest.json").read_text())["config"]["tools"]; p=["fireflies_autojoin","move_from_ff","confluence_sync","protocol_from_summary"]; assert all(c[k]["migration_status"]=="dual_read" for k in p); assert all(c[k].get("rollback_snapshot") in (None,"null") for k in p)'` ; `rg -n 'USERTOOLS_CONFIG_MODE' /home/tkachenkoav/.hermes/lib/usertools_config.py` — ветка **есть** | IAC-14 | AC-009 (не писать accepted), AC-011 (pre: не удалять), AC-015 (pre: не вырезать) |
| IAC-24 | `ORCH:shared-state`→`GATE:done` **после реплики, не критерий §10.11.7** | `config.tools.<key>.rollback_snapshot` + `accepted` | После `operator-done: answer:Q-n` + evidence: оркестратор пишет `accepted` и путь `~/.hermes/_Archives/ecosystem-config/<tool>/<timestamp>.yaml`. `test -f "$(python3 -c 'import json;from pathlib import Path; m=json.loads(Path("/home/tkachenkoav/WorkVault/Registries/EcosystemManifest.json").read_text()); print(m["config"]["tools"]["<key>"]["rollback_snapshot"])')"`. Соседей не трогать. **Не исполнять в этом HF:impl** | IAC-19 | AC-010 |
| IAC-25 | `HF:impl`→`HF:test` **после accepted + императив «удаляй»** | overlay / per-tool `.env` / литералы этого tool | Запуск: отдельный императив Саши «работает, удаляй legacy» → `depends: operator:удаляй`. Без `operator-done: удаляй` + evidence файлы не сносить. После: `.env` пилота нет (пустой не оставлять), overlay нет, уникальные секреты уже в shared `.env`, тонкая оболочка `config.py` допустима, затем ORCH → `unified_only`. **Не исполнять в волне 1** | IAC-24 | AC-011 |
| IAC-26 | `HF:test`→`HF:test` **после accepted** | лоадер на already-accepted tool | `python3 ~/.hermes/lib/usertools_config.py explain <tool> \| rg 'source=(overlay\|legacy)'` → 0 ; нет ключа → exit ≠ 0 даже если старый `.env` ещё на диске до IAC-25 ; `enabled: false` стопает tool. **Не исполнять в волне 1** | IAC-24 | AC-012 |
| IAC-27 | `HF:test`→`HF:test` **после accepted** | restore из `rollback_snapshot` | Restore поднимает несекретную секцию этого tool; ветки `local_env_path` для него нет. **Не исполнять в волне 1** | IAC-24, IAC-25 | AC-014 |

Этот `HF:impl` / `HF:test` исполняет **IAC-01, IAC-02, IAC-04…IAC-13, IAC-15…IAC-18, IAC-20…IAC-23**. Живой манифест, digest, shared `.env` (`CONFLUENCE_TOKEN`, IAC-03) и посадка `Q-n` — **IAC-03, IAC-14, IAC-19** на `ORCH:shared-state`. IAC-24…IAC-27 — поштучно после реплики Саши, вне ready-критерия §10.11.7.

`HF:backup` до `HF:impl`: `~/.hermes/_Archives/hermes-backup-YYYYMMDD-HHMMSS/` (`usertools_config.py`, `usertools_env.py`, `EcosystemConfig.yaml`, схема, 4× `config.py`, 4× `.env` где есть, **не** коммитить секреты в git). G3: git-worktree есть у `USERTOOLS/MoveFromFF` и `USERTOOLS/ProtocolFromSummary` — исполнитель коммитит их `config.py`; FirefliesAutojoin, ConfluenceSync, `Registries/`, `~/.hermes/lib` — не git, достаточно наличия на диске.

---

## 2. Кто пишет какие файлы

### Исполнитель (`HF:impl` / `HF:test`)

| path | что делает |
|---|---|
| `Registries/EcosystemConfig.schema.json` | бамп 0.1.1 + имена ключей волны 1 |
| `Registries/EcosystemConfig.yaml` | `shared:` + значения 4 пилотов; 42 чужих блока не расширять |
| `USERTOOLS/FirefliesAutojoin/ffjoin/config.py` | dual_read через лоадер + ветка `legacy` |
| `USERTOOLS/MoveFromFF/movefromff/config.py` | то же |
| `USERTOOLS/ConfluenceSync/confluencesync/config.py` | то же; убрать боевой `_find_env_file` |
| `USERTOOLS/ProtocolFromSummary/protocolfromsummary/config.py` | то же; не читать `ConfluenceSync/.env` на основном пути |
| `Registries/test_usertools_config.py` | YAML-win на 4 ключах + isolation neighbor |
| `TZ/EcosystemIntegration/evidence_wave1_*.md` | 4 пакета улик |
| `~/.hermes/lib/usertools_config.py` | **только если** понадобится фильтр explain по ключам tool; API `explain`/`resolve_key`/`USERTOOLS_CONFIG_MODE` не вырезать |

Не пишет: `EcosystemManifest.json`, `EcosystemManifest.digest.md`, `jobs.json`, `~/.config/hermes/.env`, чужие master-ТЗ, 42 чужих `config.py`/`.env`.

**Секвенсинг CONFLUENCE_TOKEN (AC-008 улики):** `Config.py`-код пилотов исполнитель пишет на IAC-08/IAC-10 без ожидания ORCH. Но улика `CONFLUENCE_TOKEN source=shared_env` (IAC-17/18) становится зелёной только после того, как ORCH добавит ключ в shared `.env` (IAC-03). До этого `resolve_key` вернёт `source=legacy` (ключ есть в `ConfluenceSync/.env`, layer 7). Поэтому:
- исполнитель: IAC-08/IAC-10 = код; улики по CS/PFS по секрету `CONFLUENCE_TOKEN` собрать после ORCH (в `HF:docs-handoff`/следующем окне) — не останавливать dual_read этой волны на этом;
- оркестратор IAC-03 — предусловие для факта `source=shared_env` в evidence CS/PFS.

### Только оркестратор (`ORCH:shared-state`)

| path | что делает |
|---|---|
| `Registries/EcosystemManifest.json` | 4× `config.tools.<key>.migration_status=dual_read`, `overlay=null`; 42 не трогать; секреты не писать |
| `Registries/EcosystemManifest.digest.md` | только через `render_manifest.py --digest` (`dual_read=4 not_started=42`) |
| `~/.config/hermes/.env` | добавить ключ `CONFLUENCE_TOKEN` (копия из `ConfluenceSync/.env`; per-tool `.env` не удалять), IAC-03 |
| body карточки ORCH | IAC-19: 4× `Q-n` + `tool_key` |

---

## 3. Что кладётся в EcosystemConfig.yaml

`shared:` (reuse-first, только реальные дубли на диске):

```yaml
shared:
  WORKVAULT_PATH: /home/tkachenkoav/WorkVault
  CONFLUENCE_URL: https://dom.tutu.ru
```

Не выдумывать `logs_root`. Не класть `TOOL_DIR`/`LOGS_PATH` в shared (разные у MFF и CS).

`tools.fireflies_autojoin`: `enabled: true` + `EXCHANGE_EMAIL`, `EXCHANGE_SERVER`, `EXCHANGE_VERIFY_TLS`, `SKIP_PRIVATE`, `TIMEZONE`, `LANGUAGE`, `CRON_HOURS`, `CRON_DAYS`, `ALERT_SMTP_HOST`, `ALERT_SMTP_PORT`. Секреты (`FIREFLIES_API_KEY`, `LOOP_TOKEN`, пароль Exchange = `TUTU_DOMAIN_PASSWORD`) — не здесь. `LOOP_URL` в YAML не тащить (код-дефолт, нет в `.env`).

`tools.move_from_ff`: `enabled: true` + `TOOL_DIR`, `PROJECT_PATH`, `CONTACTS_PATH`, `LOGS_PATH`, `TELEGRAM_CHAT_ID`, `FF_CUSTOM_SKILL_APP_ID`, `FF_CUSTOM_SKILL_TITLE`, `MFF_CUSTOM_SKILL_RETRY_COUNT`, `MFF_CUSTOM_SKILL_RETRY_DELAYS`, `MFF_CUSTOM_SKILL_RETRY_MAX_PER_RUN`. Без `WORKVAULT_PATH` (shared). Без `FIREFLIES_API_KEY` / `TELEGRAM_BOT_TOKEN` / `CONTACTS_ENCRYPTION_KEY`.

`tools.confluence_sync`: `enabled: true` + `TOOL_DIR`, `LOGS_PATH`. URL и vault — shared. Без `CONFLUENCE_TOKEN`.

`tools.protocol_from_summary`: `enabled: true` + `MEETINGS_DIR`, `CONTACTS_ENC`, `ROOMS_MD`, `STATE_DIR`, `PREPARED_PROTOCOLS_DIR`, `ENTITIES_REGISTRY_PATH`, `TELEGRAM_NOTIFY_CHAT_ID`, `TELEGRAM_NOTIFY_THREAD_ID`, `TELEGRAM_NOTIFY_TARGET`. URL/vault — shared. **Не** класть: `ROUTES`, `PLAYGROUND_PAGE_ID`, `DEFAULT_CONFLUENCE_SPACE`, entity-slugs, `LLM_FALLBACK_*`, `PFS_POST_SWITCH`.

Остальные 42: только `enabled`.

### Новые ключи → схема (IAC-01)

В `tool_section.properties` (все `type: string`, кроме уже существующего `enabled`):  
`EXCHANGE_EMAIL`, `EXCHANGE_SERVER`, `EXCHANGE_VERIFY_TLS`, `SKIP_PRIVATE`, `TIMEZONE`, `LANGUAGE`, `CRON_HOURS`, `CRON_DAYS`, `ALERT_SMTP_HOST`, `ALERT_SMTP_PORT`, `TOOL_DIR`, `PROJECT_PATH`, `CONTACTS_PATH`, `LOGS_PATH`, `TELEGRAM_CHAT_ID`, `FF_CUSTOM_SKILL_APP_ID`, `FF_CUSTOM_SKILL_TITLE`, `MFF_CUSTOM_SKILL_RETRY_COUNT`, `MFF_CUSTOM_SKILL_RETRY_DELAYS`, `MFF_CUSTOM_SKILL_RETRY_MAX_PER_RUN`, `MEETINGS_DIR`, `CONTACTS_ENC`, `ROOMS_MD`, `STATE_DIR`, `PREPARED_PROTOCOLS_DIR`, `ENTITIES_REGISTRY_PATH`, `TELEGRAM_NOTIFY_CHAT_ID`, `TELEGRAM_NOTIFY_THREAD_ID`, `TELEGRAM_NOTIFY_TARGET`, `WORKVAULT_PATH`, `CONFLUENCE_URL`.

`additionalProperties: string` **оставить** (волна 2). Бамп YAML `0.1.0` → `0.1.1`. Секретных имён в `properties` нет.

---

## 4. Open-questions

Не задаю Саше напрямую. Оркестратор закрывает на `GATE:plan-approve` (рекомендация = default исполнителя). **Ни один Q не блокирует dual_read IAC-01…13.**

**Q-1.** Как закрывать AC-008(b) в воскресенье (тики FF `CRON_DAYS=1-5`, сегодня 2026-10-11)?  
Рекомендация: IAC-15(a)+(c) сразу; (b) — ≥3 `tick` в ближайшее окно пн 9–19 **или** 1 рабочий день. Новый крон не ставить. Критерий §10.11.7 включает пакет улик — `GATE:done` этой волны ждёт (b), а не ответ Саши на `Q-n`.

**Q-2.** AC-008 «ноль `source=legacy`» на полном stdout `explain` vs бизнес-ALLCAPS в PFS `config.py` (AST-литералы `PLAYGROUND_PAGE_ID`, `LLM_FALLBACK_*`).  
**Зафиксированное решение (как Q-2 волны 0):** не открытый блокер. Проверять **мигрированный набор ключей** IAC-15…18. Весь dump shared `.env` в `explain` — шум лоадера волны 0, не дефект волны 1. Не тащить бизнес-константы и LLM-fallback в YAML (AC-019 / SoT Hermes).

**Q-3.** Заводить ли `config.overlay.yaml` на пилотах?  
Рекомендация: **нет**, `overlay: null`. Откат dual_read — `USERTOOLS_CONFIG_MODE=legacy` (AC-013). Меньше файлов к «удаляй».

**Q-4.** Четыре карточки ORCH vs одна в текущем графе?  
Рекомендация: архитектор граф не строит. На существующей карточке `ORCH:shared-state` — IAC-14 (4× `dual_read`) и IAC-19 (`Q-1`…`Q-4` с четырьмя `tool_key`). Не один пакетный «принять всех». `accepted` только после ответа на **этот** `Q-n`.

**Q-5.** Когда сажать `Q-n`?  
Рекомендация: **после** зелёного пакета AC-008 этого пилота, не в момент записи `dual_read`. Без улик вопрос не ставить (§10.11.4).

---

## 5. AC-класса O (приёмка Вариант 1)

Durable operator-holds. **Не краснят `GATE:done` волны 1**, потому что §10.11.7 = `dual_read` ×4 + пакеты AC-008 + посаженные `Q-n` + `--check-drift` без новых дублей. `accepted` / `unified_only` в ready-критерий не входят. Не ставить `operator-done` без факта.

| AC | class | verb | Когда hold живой | Что должен сделать Саша | Снятие | Краснит GATE:done **этой** волны? |
|---|---|---|---|---|---|---|
| **AC-009** | O | `answer:Q-n` | После IAC-19, поштучно на каждый пилот | Явная реплика «принять / не принять» по `Q-n` (`tool_key:` в body) | `operator-done: answer:Q-n` + `evidence:` (ISO + цитата) на `GATE:done`/корне **эпика/последующего графа** → затем `accepted` | **нет** для `DEV/eco-config-w1` |
| **AC-011** | O | `удаляй` | Уже `accepted` пилот, отдельный императив | «Работает, удаляй legacy» | `operator-done: удаляй` + evidence путей. Секреты в shared `.env` **до** сноса | **нет** |
| **AC-016** | O | `удаляй` | Волна 4, не эта | Осиротевшие `.env` | как в плане волны 0 | **нет** |

Остальные AC этой волны — класс **S**: AC-007, AC-008, AC-010 (фиксация после ответа — оркестратор, поезд волны 1 не ждёт), AC-012…014 (после accepted), AC-017, AC-019. AC-008 улики собирает исполнитель; перевод в `accepted` без AC-009 не делается.

Как запускается AC-011: не из этого `HF:impl`. После IAC-24 оркестратор держит hold `удаляй`; исполнитель следующего хвоста сносит файлы только при `operator-done: удаляй`.

---

## 6. Критерий готовности волны 1 (чеклист §10.11.7)

- [ ] IAC-01…IAC-13: схема 0.1.1, YAML+shared, 4 `config.py` на лоадере, pytest зелёный, 42 не тронуты
- [ ] IAC-03: `CONFLUENCE_TOKEN` в shared `.env`, не в YAML/манифесте/digest
- [ ] IAC-14: 4× `dual_read`, digest `dual_read=4 not_started=42`, overlay нет
- [ ] IAC-05/07/09/11: YAML побеждает `.env`/литерал на совпадающем ключе
- [ ] IAC-15…18: 4 пакета улик (explain + тики/день/реальный вызов + ErrorBus)
- [ ] IAC-19: 4× `Q-n` посажены
- [ ] IAC-20: `USERTOOLS_CONFIG_MODE=legacy` откатывает пилот, сосед bit-identical
- [ ] IAC-21: `--check-drift` exit 0, без новых дублей SoT
- [ ] IAC-22: бизнес-YAML не тронуты
- [ ] IAC-23: `.env` пилотов на месте, не `accepted`, fallback лоадера жив
- [ ] Кроны не создавались, Gateway не рестартовали, OverlayConfig не в `tools{}`

Не входит в готовность: IAC-24…27 (`accepted` / snapshot / «удаляй» / fail-loud / restore).

---

context-used:
  card: t_45d90257
  root: DEV/eco-config-w1: OverlayConfig волна 1
  phase: HF:plan
  tz_version: 0.6.0
  tz_mtime: 2026-10-11T15:20:17Z
  emitted_at: 2026-10-11T15:24:42Z