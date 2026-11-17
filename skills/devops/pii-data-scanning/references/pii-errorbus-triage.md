# SUPERSEDED — historical triage only

Current scope, whitelist and instructions are in ../SKILL.md and pii-rule-20260909.md. Conflicting instructions below are historical and must not be followed.

# Триаж находок PIIScan в ErrorBus (из расследования 2026-09-09, архитектор cursor-grok-4.6-high, read-only)

> **УСТАРЕЛО (09.09.2026):** правила зон/политика ниже перекрыты решением 09.09 —см. `references/pii-rule-20260909.md` (канон) и реализацию v1.1.0 в `PIIScan_TZ.md`. Оставляется как историческая запись расследования 647 open-строк. Фиксы РЕАЛИЗОВАНЫ и закрыты 09.09 (HF:impl→HF:test PASS, 26 pytest зелёные, CHANGE-карточка DEV/PIIScan-pii-hygiene): детектор (INTERNAL_LOGIN/PHONE/SECRET_ASSIGNMENT/Miro), whitelist+3, JSON-контекст по полю, маскирование на записи (redact.py/gateway/MFL/ExchangeMonitor/error_bus_cli), TTL 5д (TaskRefresh/llm-anomaly-audits). `pfs_batch` НЕ менялся (решение 09.09).

## Главный вывод
Открытые строки ErrorBus (`status='open' AND tool='PIIScan'`) — это **инкремент за последний прогон**, а НЕ все утечки. Baseline (12 093+ известных находок на 27.08) знает в разы больше; open — только новые ключи. Поэтому «647 строк» ≠ «647 утечек»: ~70–80% строк — штатная рабочая база, ~10–15% — ложные срабатывания детектора, ~10% — реальные каналы утечки формата, креды — единично.

## Классы ложных срабатываний (по 647 open, 1561 count, critical 1254 / error 307)
| Класс | Доля | Причина |
|---|---|---|
| Легитимная рабочая база (уставы/минутки/ТЗ/встречи/TaskRefresh) | ~75–80% | ФИО+должность/логин+@mention в док-ах; whitelist узкий (только Contacts/Entities/Inbox/UserManuals) |
| Сканерные ложные позитивы | ~10–15% | баги паттернов (см. ниже) |
| Копии живой переписки (logs + cron/output) | ~10–12% | реальный канал утечки формата |
| Креды | <1% | `boardAccessToken=` в URL Miro — НЕ API-ключ |

## Два подтверждённых бага детектора (`~/.hermes/pii_scan/patterns.py`)
1. **`INTERNAL_LOGIN`** матчит `файл.md`, `config.yaml`, `tutu.ru`, `dom.tutu` как «логин».
2. **`PHONE`** ветка `\d{10,15}` матчит Telegram-chat id (`-100…` 13 цифр), unix-время, длинные id. Почти все «телефоны» в логах — `bare_digits`, не `+7`/`8`.

## Severity раздувает сама шина
PIIScan шлёт `--severity critical`; ErrorBus при повторном хите за 24ч переклассифицирует через `classify()` (порог count≥5 → critical, иначе error). Т.е. `critical=1254` — шум шины, а не оценка ФЗ-152. Не читать severities как реальную картину риска.

## Смежные подводные камни
- **Path с пробелами ломает разбор `message`** — разбирать находки только из структурированного `detail`, не из `message`.
- **`~/.hermes/logs/gateway.log` хранит живую переписку**: `inbound message: ... msg='<текст TG>'` — канал утечки формата.
- **`/cron/output/2865cc674493`** — MoveFromLoop-дайджест (`mfl_digest.py`), пишет тела Loop-сообщений с `@handles` на диск.
- **`llm_anomaly_scan.sh`** сохраняет полный agent-JSON в `~/WorkVault_backup/llm-anomaly-audits/*.json` — утечка формата хранения (лучше краткое резюме).
- **TaskRefresh `session/history/*.json`** — рабочий кэш с ФИО исполнителей (126 файлов, ~1.2 МБ/10 256 строк), НЕ дыра; расширять whitelist, а не чистить.
- **24 open-строки** ссылались на уже удалённые cron-файлы — авто-резолв не сработал, закроются следующим инкрементальным прогоном.
- **Расхождение ErrorBus 647 vs baseline `status=open` 1634** — схлопывание по одинаковому `message` (совпавшие маски) + пересчёт `count`.

## Согласованная политика зон с Сашей (финал 2026-09-09)
| Зона | Решение |
|---|---|
| `WorkVault/Confluence` (уставы/минутки) | **в исключения** (whitelist, не сканировать) |
| `WorkVault/Projects/*` (весь, вкл. TrisigmaFull) | **в исключения** (финальное решение Саши 09.09: весь Projects/) |
| `WorkVault/Meetings/*transcript.md` | **в исключения** |
| `Hermes-Backlog/TZ/*` | рабочая база: логины в ТЗ голые+мусор-заглушки (`subject`, `Имя Фамилия`), реальных связок мало → понизить severity / skip |
| `~/.hermes/cron/output/`, `~/.hermes/logs/` | канал утечки формата: **не писать ФИО, только логины** (доработать mfl_digest / pfs_batch / `inbound msg=`) |
| `WorkVault/Tools/TaskRefresh/session/history/*.json` | **TTL 5 дней** для завершённых сессий; `current.json` — только актуальный; это рабочий кэш карточек, ФИО ожидаемы |
| `WorkVault_backup/llm-anomaly-audits/*.json` | **TTL 5 дней** + не писать сырой agent-JSON (только резюме) |
| Креды Miro `boardAccessToken` (3 файла) | убрать токен из URL точечно; это НЕ пароль Hermes, а query-параметр embed-доступа к доске |

Пути к 3 Miro-cred файлам (2026-09-09): `Projects/TrisigmaFull/digest/leaves/p493480590.md` + 2 Confluence `.../Архитектура на прод Trisigma/index.md` и `.../Архитектура и оценка PoC в облаке/index.md`. В файлах это `miro.com/app/live-embed/...?boardAccessToken=...`. Реальный источник: Miro-макрос → страница проекта → выгрузка в WorkVault → digest-лист.

## Направления фикса (когда пойдёт в реализацию)
1. Сузить `INTERNAL_LOGIN` (не `файл.ext`/домен), `PHONE` (только `+7`/`8` с маской), не считать `token=` внутри query-string.
2. Для `.json` контекст = одно строковое поле, не весь файл.
3. Зонировать severity: `+position` в документах → info/skip; `+email/+phone` в logs/cron → critical; креды → только ключи/PEM/Bearer.
4. Расширить whitelist: `Tools/TaskRefresh/session/`, `Meetings/`, `Hermes-Backlog/TZ`, `error_bus/tests/`.
5. Маскировать на записи (gateway.inbound msg, MFL-дайджест, agent-JSON), не чистить vault.
6. Убрать `boardAccessToken` из трёх Confluence/Trisigma Miro-страниц.