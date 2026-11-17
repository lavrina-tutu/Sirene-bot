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

## Historical source (superseded where it conflicts with SKILL.md; not current instruction)

## Питфолл 4: единая env-схема USERTOOLS и smoke-тест на нужном venv

С 20.08.2026 внедрён общий env-loader `~/.hermes/lib/usertools_env.py`:
- Бизнес-секреты (CONTACTS_ENCRYPTION_KEY, LOOP_TOKEN, FIREFLIES_API_KEY, TELEGRAM_BOT_TOKEN и др.) живут в едином `~/.config/hermes/.env`; локальные `.env` тулов держат только не-дубли (CONFLUENCE_TOKEN, OWNCLOUD_*, пути).
- Подключение в тул (паттерн пилота MoveFromLoop):
  ```python
  sys.path.insert(0, str(Path.home()/".hermes"/"lib"))
  import usertools_env
  usertools_env.load_usertools_env(local_env_path=<тул/.env>)  # локальный приоритетнее центрального
  ```
- **Loader вызывать ПЕРВЫМ в конфиге, до собственного чтения env**: loader на `os.environ.setdefault`, т.е. уже установленную переменную НЕ перезапишет. Если код тула прочитал env раньше — setdefault не сработает.
- Удаление дублей из локальных `.env`: только ключи, которые есть в `~/.config/hermes/.env`; уникальные ключи тула оставить. Бэкап локальных `.env` перед правками → `~/.hermes/_Archives/usertools-env-pilot-rollout-YYYYMMDD/`. Не звать письмо если ключ не в центральном.

**Питфолл 4а: ПОРЧЕННЫЙ секрет в центральном `.env` перекрывает валидный локальный — и это выглядит как «всё сломалось».** Не-дуп-ключ тула (напр. `CONFLUENCE_TOKEN`) может быть ДУБЛЕМ в рабочем виде также и в центральном `~/.config/hermes/.env` (если туда случайно/OverlayConfig-скриптом записали значение). Из-за паттерна бутстрапа (`load_usertools_env()` заполняет центральный env первым, а валидный локальный фоллбек срабатывает только `if key not in os.environ`) повреждённый центральный экземпляр «глушит» исправный локальный. Диагностировать смотрением НА ДЛИНУ/СОДЕРЖИМОЕ, а не «наличие ключа»: распечатать `CONFLUENCE_TOKEN` из обоих файлов и сравнить (`bad.startswith(valid)` + лишние байты = порча, часто мусор приписан в конец). Лечить по канону: не дублировать не-дуп-ключ в центральном `.env` вовсе — тогда фоллбек сам подхватит валидный локальный. **Маскирующий признак Confluence: HTTP 404 с телом `{"statusCode":404,"data":{"authorized":false,"valid":true,...}}` на КАЖДОЙ странице — это ОТКАЗ АВТОРИЗАЦИИ сломанным токеном, а не отсутствие страниц/миграция/устаревшие page_id.** Прежде чем грешить на URL/id/миграцию — пробить ту же страницу валидным токеном: если 200, виноват секрет, не страница.

**Smoke-тест — важный питфолл:** НЕ тестировать конфиг тула системным `python3` — там нет зависимостей тула (requests/exchangelib/pydantic), получишь ложный `ModuleNotFoundError`, не связанный с изменением. Берём venv самого тула (`$TOOL/venv_linux/bin/python3` или `$TOOL/.venv/bin/python3`), а тулы на exchangelib (MeetingScheduler, ExchangeMeeting) гонять через `MoveFromLoop/venv_linux` или `AnywhereContacts/venv_linux`. Минимальный smoke с чистым окружением:
```bash
env -i $TOOL/.venv/bin/python3 -c "import sys,os; sys.path.insert(0,'$TOOL'); import $pkg.config; print('OK', 'CONTACTS_ENCRYPTION_KEY' in os.environ)"
```
После удаления дублей проверить `grep -qE '^KEY=' ~/.config/hermes/.env` для каждого снятого ключа — секрет не потерян.
