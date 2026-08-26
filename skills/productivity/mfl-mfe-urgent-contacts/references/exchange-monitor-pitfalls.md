# ExchangeMonitor — питфолы MFE-уведомлений

## should_skip() — молчаливое подавление встреч

**Файл:** `movefromloop/exchange_urgent.py`, строка 70

```python
if is_urgent_sender and should_skip(msg):
    new_seen.append(msg.id)
    continue  # письмо отброшено БЕЗ уведомления
```

**Поведение:** `should_skip()` определяет, является ли письмо принятием/отклонением/изменением встречи. Если да И отправитель из `exchange_urgent_contacts` — письмо молча пропускается, записывается в `seen` и больше никогда не всплывёт.

**Причина:** не спамить уведомлениями типа «Встреча принята» от срочных контактов.

**Симптом:** письмо от срочного контакта есть в Exchange, но Hermes не прислал уведомление.

**Диагностика:**
1. Проверить `message_class` письма — если содержит `IPM.Schedule.Meeting` → это встреча.
2. Письмо уже попало в `state/watermark.json` как `seen` — повторно не проверится.
3. Это не баг фильтрации по email — отправитель прошёл `is_urgent_sender`, но был отброшен `should_skip()`.

**Решение (если нужно):** изменить логику `should_skip()` в `exchange_urgent.py` — убрать или сузить критерий подавления встреч.

## Фильтрация: два пути

1. **По отправителю** — `exchange_urgent_contacts` (фолбэк из `urgent_contacts` в `loop_rules.yaml`). Поиск по substring в email и имени.
2. **По ключевым словам** — `exchange_urgent_keywords` в теле письма (полное совпадение подстроки, регистронезависимо).

Если ни один путь не сработал → письмо не считается срочным.

## no_agent=true — stderr не доставляется (КРИТИЧНО)

Крон `MoveFromLoop — срочные сообщения` работает в режиме `no_agent=true`:
- **stdout** → Telegram (если пустой — тишина, пользователь ничего не видит)
- **stderr** → **НЕ доставляется**, только пишется в лог выполнения
- **exit code 0** (ошибка поймана в try/except) → Hermes считает тик успешным

**Проявление:** ImportError (`No module named 'yaml'`, `No module named 'ruamel'`), ошибка EWS, timeout — всё уходит в stderr. Пользователь видит «тишина» и думает «нет новых писем», а скрипт падает на каждом тике.

**Диагностика:** запустить вручную из правильного venv:
```bash
/home/tkachenkoav/USERTOOLS/MoveFromLoop/venv_linux/bin/python \
  /home/tkachenkoav/.hermes/scripts/mfl_urgent_check.py 2>&1
```
Если stderr содержит `ERROR` или `FATAL` — причина найдена.

**Признак в state:** `exchange_urgent_last_ts` застыл на старой дате (не обновляется) — крон не доходит до строки обновления watermark из-за падения.

## Watermark

- Ключ: `exchange_urgent_last_ts` (не `_last_dt` — имя зависит от ветки) в `state/watermark.json`
- После каждого запуска обновляется до max `datetime_received` из выборки
- Если ветка падает — watermark НЕ обновляется, письма за период пропускаются
- Письма до watermark НЕ проверяются повторно

## ⚠️ Реальный кейс (20.08.2026): поздняя дата начала — письмо уже не перепроверится

Даже после фикса auth/env позднее письмо окажется **старше** `exchange_urgent_last_ts` и фильтр `fetch_inbox_since(account, wm)` его не поднимет. Так watermarked-письмо не вернётся автоматически.

**Решение:** перед прогоном фикса либо вручную сбросить `exchange_urgent_last_ts` в `state/watermark.json` (или `watermark.json`) на дату до письма, либо вручную доставить письмо через fetch по конкретному id/интервалу. Не полагаться на автоматическое восстановление после обрыва.

## ⚠️ Реальный кейс (20.08.2026): срочное письмо от urgent-контакта есть в Exchange, но уведомления НЕТ

**Ситуация:** Арут-отклонение встречи от `aralov@tutu.tech` (19.08 22:24 МСК) не доставлено. Письмо на месте в Inbox, message_class `IPM.Schedule.Meeting.Resp.Neg` (отклонение — должно пересылаться, НЕ `should_skip`).

**Причина — цепь из 2 поломок, обе «тихие» в `no_agent=true` cron:**

1. **env-цепь не тянет CONTACTS_ENCRYPTION_KEY** → `urgent_emails` пуст.
   `mfl_urgent_check.py` грузит только `.hermes/profiles/default/.env` и `~/.config/hermes/.env`. Но `CONTACTS_ENCRYPTION_KEY` лежит ТОЛЬКО в `~/USERTOOLS/AnywhereContacts/.env`. Без него `contacts.enc` не расшифровывается → `_resolve_urgent_emails` возвращает пустой набор → письмо от Арабора не «срочное», единственный keyword-фильтр (`ADD-613444`) не совпадает → молча отброшено.
   *Проверка:* запустить `mfl_urgent_check.py` — в логе `[exchange_urgent] Ни один urgent_contact не резолвится в email` и/или `urgent_emails` пуст.
   *Фикс (band-aid, устарел):* добавить `load_dotenv(\"/home/tkachenkoav/USERTOOLS/AnywhereContacts/.env\")` в chain скрипта.
   *Правильный фикс (принят 20.08.2026):* общий loader `~/.hermes/lib/usertools_env.py` (см. ниже), а не ещё один per-tool load_dotenv.

2. **venv крона не имеет `yaml`** → весь Exchange-блок падает `ModuleNotFoundError: No module named 'yaml'` (модуль `exchangemonitor.config` импортирует `yaml`). В `MoveFromLoop/venv_linux` есть только `ruamel`, системный `python3.11` не имеет ни `yaml`, ни `exchangelib`.
   *Резолв venv для ручного теста:* `/home/tkachenkoav/hermes-agent/.venv` содержит `yaml` (pyyaml 6.0.3), а `MoveFromLoop/venv_linux` содержит `exchangelib`. Для запуска `exchangemonitor` вручную оба каталога на `sys.path`:
   ```python
   sys.path.insert(0, '/home/tkachenkoav/USERTOOLS/MoveFromLoop/venv_linux/lib/python3.11/site-packages')
   sys.path.insert(0, '/home/tkachenkoav/hermes-agent/.venv/lib/python3.11/site-packages')
   ```
   *Фикс:* установить `pyyaml` в `MoveFromLoop/venv_linux` (сделано 20.08.2026: `pip install pyyaml` → pyyaml 6.0.3) — крон не падает больше на каждый тик.

## ✅ Принятое решение (20.08.2026): единая схема env для USERTOOLS

Корень проблемы — 4 независимых конвенции хранения env. Принятый вариант (анализ архитектора Sonnet, `hermes-feature`):

- **Hermes-core секреты** (LLM-провайдеры, мессенджеры, дашборд) — остаются в `~/.hermes/.env`. Не трогать.
- **Бизнес-секреты USERTOOLS** (`CONTACTS_ENCRYPTION_KEY`, `LOOP_TOKEN`, `CONFLUENCE_*`, `JIRA_*`, `ZULIP_*`, доменные пароли) — ЕДИНЫЙ файл `~/.config/hermes/.env`.
- **Не-секретные локальные пути тула** (`TOOL_DIR`, `LOGS_PATH`, `CONTACTS_PATH`) — остаются в `<tool>/.env`.
- **Общий loader** `~/.hermes/lib/usertools_env.py`: `load_usertools_env(local_env_path=None)` — парсит `~/.config/hermes/.env`, применяет через `os.environ.setdefault` (никогда не перетирает уже выставленное), плюс опционально локальный `.env`. Без внешних зависимостей (не `python-dotenv` — свой построчный парсер, как в `MoveFromJira/config.py`/`exchange_client.py`). Точки входа подключают через `sys.path.insert(0, "/home/tkachenkoav/.hermes/lib")`.
- **Правило:** замена любого креда = правка ОДНОГО файла `~/.config/hermes/.env`, ни один крон больше не трогаем.

**⚠️ `profiles/default/.env` — НЕ мёртвый профиль (важная находка):** default-профиль по докам Hermes = сам `~/.hermes`, но папка `~/.hermes/profiles/default/.env` реально используется — launcher команды `agent -p --profile default` автоматически инжектит её в процесс, и `LOOP_TOKEN` / `JIRA_TOKEN` жили только там. Не удалять как мусор без проверки потребителей. При миграции на единый файл — сначала перенести секреты в `~/.config/hermes/.env`, подождать наблюдение, потом чистить.

**Связанное:** генеральное решение консолидировать TODминадлежит скиллу `usertools-llm-integration` (env/LLM/cron-отладка USERTOOLS).

2. **venv крона не имеет `yaml`** → весь Exchange-блок падает `ModuleNotFoundError: No module named 'yaml'` (модуль `exchangemonitor.config` импортирует `yaml`). В `MoveFromLoop/venv_linux` есть только `ruamel`, системный `python3.11` не имеет ни `yaml`, ни `exchangelib`.
   *Резолв venv для ручного теста:* `/home/tkachenkoav/hermes-agent/.venv` содержит `yaml` (pyyaml 6.0.3), а `MoveFromLoop/venv_linux` содержит `exchangelib`. Для запуска `exchangemonitor` вручную оба каталога на `sys.path`:
   ```python
   sys.path.insert(0, '/home/tkachenkoav/USERTOOLS/MoveFromLoop/venv_linux/lib/python3.11/site-packages')
   sys.path.insert(0, '/home/tkachenkoav/hermes-agent/.venv/lib/python3.11/site-packages')
   ```
   *Фикс:* установить `pyyaml` в `MoveFromLoop/venv_linux` (или перевести импорт на `ruamel.yaml`), чтобы крон не падал на каждый тик.

**Порядок диагностики «письмо есть, уведомления нет»:**
1. Запустить `mfl_urgent_check.py` вручную `2>&1` из правильного venv — увидеть `Exchange FAIL` / `No module named 'yaml'` / `не резолвится`.
2. Проверить `message_class` письма (если `Resp.Neg`/`Resp.Tent`/`Counter` — должно пересылаться; `Resp.Pos` — `should_skip` глушит намеренно).
3. Проверить, пуст ли `urgent_emails` (веренка ключа шифрования контактов).
4. Учесть watermark: если письмо старше `exchange_urgent_last_wm` — даже после фикса не перепроверится.

**Признак в state:** `exchange_urgent_last_ts` НЕ застыл (обновился сегодня), но письмо не доставлено → значит крон доходит до завершения, но фильтр по отправителю пуст (причина 1) или Exchange-блок упал без обновления watermark (причина 2).