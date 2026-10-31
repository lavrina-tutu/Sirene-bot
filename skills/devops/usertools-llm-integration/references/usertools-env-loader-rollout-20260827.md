# Раскатка единой env-схемы USERTOOLS — проверно 2026-08-27

## Пилот (MoveFromLoop)
- Крон `f61b26cbbdf5`, скрипт `~/.hermes/scripts/mfl_urgent_check.py`.
- Прогон: `env -i ~/USERTOOLS/MoveFromLoop/venv_linux/bin/python3 ~/.hermes/scripts/mfl_urgent_check.py`
- Нормальный вывод — `[urgency_checker] Username 'arut' not found in contacts.enc... Run MoveFromLoop v1 sync first.` (exit 0) — это ЛОГИЧЕСКАЯ заглушка (контакт не найден), НЕ env/yaml-сбой. Не путать с ошибкой.
- Проверка инцидентов за неделю: `grep -rlE "Exchange FAIL|ModuleNotFoundError|CONTACTS_ENCRYPTION_KEY|LOOP_TOKEN" ~/.hermes/cron/output/<job_id>/` → 0 совпадений = чисто. Статусы крона файлов: `silent`/`Run Time`, без error.

## Раскатка на 11 тулов (Cursor composer-2.5)
Тулы: ConfluenceSync, SRTool, MoveFromFF, ProtocolFromSummary, TaskRefresh, MoveFromJira, MeetingScheduler, ExchangeMeeting, MoveFromZulip, AnywhereContacts, MarkObjectsFromSummary.
- Изменялись `config.py`/точки входа (loader вызывается до чтения env); у `MoveFromFF/Anywhere/Protocol/SRTool/MoveFromZulip/MarkObjects/MoveFromJira` заменены `load_dotenv`/`env_file` из pydantic на `load_usertools_env()`.
- Снятые дубли секретов: MoveFromFF (FIREFLIES_API_KEY, TELEGRAM_BOT_TOKEN, CONTACTS_ENCRYPTION_KEY), MoveFromZulip (CONTACTS_ENCRYPTION_KEY), AnywhereContacts (CONTACTS_ENCRYPTION_KEY), MarkObjects (CONTACTS_ENCRYPTION_KEY). Бэкап: `~/.hermes/_Archives/usertools-env-pilot-rollout-20260827/`.
- Уникальные ключи не трогать: CONFLUENCE_TOKEN, OWNCLOUD_*, пути (TOOL_DIR/WORKVAULT_PATH/LOGS_PATH) остаются локально.
- Не в скоупе раскатки: MoveFromLoop, ExchangeMonitor, FirefliesAutojoin (уже мигрированы/вне).

## Smoke-тесты — правильные интерпретаторы
| Тул | venv |
|---|---|
| ConfluenceSync | ConfluenceSync/.venv |
| SRTool | SRTool/.venv |
| MoveFromFF | MoveFromFF/.venv |
| ProtocolFromSummary | ProtocolFromSummary/.venv |
| MoveFromJira | MoveFromJira/venv_linux |
| MeetingScheduler / ExchangeMeeting (exchangelib) | MoveFromLoop/venv_linux ИЛИ AnywhereContacts/venv_linux |
| MoveFromZulip | MoveFromZulip/venv_linux (+PYTHONPATH=AnywhereContacts т.к. зависит) |
| MarkObjectsFromSummary | ProtocolFromSummary/.venv (там установлен пакет mofs) |

Маркер «нет своих exchangelib-venv» → гонять через MoveFromLoop/AnywhereContacts venv_linux (exchangelib ставится туда).