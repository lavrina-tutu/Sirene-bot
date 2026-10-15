---
name: FirefliesAutojoin
tool: FirefliesAutojoin
version: 1.0.0
date: 2026-08-21
status: active
author: Sirene
license: MIT
upstream: "data-science/fireflies-autojoin (Stash: https://stash.tutu.ru/projects/DATA-SCIENCE/repos/fireflies-autojoin, v0.2.1)"
---

# FirefliesAutojoin — автоприглашение Fred на Zoom-встречи Саши

Версия: 1.0.0 (документация уже развёрнутой системы; версия кода на диске — `0.2.1+sirene1`)

## 1. Цель

Гарантированно приглашать Fireflies-бота Fred на Zoom-встречи Саши из календаря Outlook ровно в момент их старта, вызывая API Fireflies `addToLiveMeeting` по прямой join-ссылке — в обход почтового инвайта боту, который падает на платформенных ограничениях Zoom/Exchange.

## 2. Назначение и место в экосистеме

`FirefliesAutojoin` — адаптированный форк внутреннего инструмента ТУТУ (`data-science/fireflies-autojoin`, апстрим v0.2.1), развёрнутый как собственный инструмент Сирени на ВМ. Решает узкую задачу: **довести бота до комнаты**, ничего не транскрибирует и не анализирует сам.

Место в цепочке встреч:

| Инструмент | Роль | Связь с FirefliesAutojoin |
|---|---|---|
| `ExchangeMonitor` | общий мониторинг почты/календаря Outlook (EWS) | Независимый инструмент; оба ходят в один Exchange (cas.tutu.ru) под одним аккаунтом, но разными сессиями EWS. Не делят состояние. |
| `FirefliesAutojoin` (этот) | читает Zoom-встречи, зовёт бота в момент старта | — |
| Fireflies (app.fireflies.ai) | запись + черновая транскрипция встречи | Получает бота через `addToLiveMeeting`, дальше работает автономно от Сирени |
| `fireflies-transcripts` (скилл, отдельный) | забирает готовую транскрипцию/саммари из Fireflies | Начинает работу **после** того, как встреча завершена и Fireflies обработал запись; не знает, как бот попал в комнату |
| `MeetingScheduler` | планирование/организация встреч Саши | Источник данных — тот же календарь Outlook, но `MeetingScheduler` пишет/меняет события, `FirefliesAutojoin` только читает |

Причина существования как отдельного инструмента, а не почтового инвайта: инвайт боту по email упирается в комбинацию Zoom waiting-room / host-not-in-room, требование точного совпадения времени и календарного ID — на практике ненадёжно. Прямой вызов `addToLiveMeeting` с извлечённой join-ссылкой устраняет эту зависимость.

## 3. Архитектура

Двухтактный цикл, разнесённый по системному crontab (НЕ Hermes cron — отдельный механизм с отдельным маркером в crontab пользователя):

```
tick (раз/30 мин, часы 9-19 пн-пт)
  EWS (cas.tutu.ru, NTLM, перебор 3 вариантов username)
    → события календаря Саши
    → фильтр: cancelled / all-day / declined / private (SKIP_PRIVATE)
    → извлечение Zoom-ссылки+пароля из subject/location/body
    → атомарная запись state/plan.json

fire (каждую минуту, часы 9-19 пн-пт)
  читает ТОЛЬКО state/plan.json (не ходит в Exchange)
    → при now >= start (не раньше!) и в пределах fire-окна
    → Fireflies GraphQL addToLiveMeeting(meeting_link, password, duration, language)
    → флаг в state/invites.json (дедуп)
```

Разделение tick/fire намеренное: исключает двойное приглашение одного бота от двух параллельно читающих Exchange процессов и позволяет `fire` работать с секундной точностью без нагрузки на EWS каждую минуту.

Точки входа:

- `bin/run.sh {tick|fire|status|dry-run}` — обёртка, выбирает venv (`venv_linux`), выставляет `PYTHONPATH`, запускает `python -m ffjoin`.
- Оба крон-вызова обёрнуты в `flock -n` на отдельные лок-файлы (`state/tick.lock`, `state/fire.lock`) — защита от наложения запусков.

Кредлоадер: `ffjoin/config.py::load_env()` подключает `~/.hermes/lib/usertools_env.py` (`load_usertools_env`), который через `os.environ.setdefault` сначала грузит общий `~/.config/hermes/.env`, затем локальный `.env` инструмента поверх (не переопределяя уже выставленные переменные). Секреты никогда не дублируются в код инструмента.

## 4. Функциональные блоки

### 4.1 Календарь (`calendar_ews.py`)
- Подключение к Exchange (`cas.tutu.ru`) через `exchangelib`, NTLM-аутентификация.
- Перебор до 3 вариантов username при подключении (устойчивость к разным форматам логина в NTLM).
- Выборка событий в окне `[now - FIRE_WINDOW_MIN, now + POLL_LOOKAHEAD_HOURS]` (дефолт `POLL_LOOKAHEAD_HOURS=12`).
- Фильтрация: отменённые встречи, all-day события, встречи со статусом "declined", встречи с пометкой Private/Confidential (если `SKIP_PRIVATE=true`).
- Извлечение Zoom join-ссылки и пароля из полей subject / location / body события регулярными выражениями.

### 4.2 План (`plan.py`, `state.py`)
- Атомарная запись/чтение `state/plan.json` — единственный источник данных для `fire`.
- `PLAN_HORIZON_MIN` (дефолт 40 мин) — горизонт, на который план считается актуальным; должен превышать интервал между `tick` (30 мин) с запасом. Также используется в `status` для отчёта о "протухании" плана.
- Дедупликация приглашений в `state/invites.json`: первичный ключ `calendar_item_id|start_iso`, вторичный — по Zoom-room-id + точному времени старта (переживает смену calendar_item_id со стороны Exchange).

### 4.3 Приглашение (`fireflies.py`, `tick.py`)
- Вызов GraphQL-мутации Fireflies `addToLiveMeeting(meeting_link, password, duration, language)`.
- `fire` вызывает Fireflies не раньше фактического старта встречи (`now >= start`) — комната Zoom часто открывается лишь на старте, более ранний вызов бесполезен.
- Окно допустимого вызова после старта: `FIRE_WINDOW_MIN` (дефолт 15 мин) — покрывает случай пропущенного `tick`.
- Rate-limit: локальный трекер `state/rate.json`, не более `MAX_ATTEMPTS` (дефолт 3, равно реальной квоте Fireflies) вызовов за 20-минутное окно.
- Ретраи: `RETRY_GAP_SEC` (дефолт 300 сек) между попытками для одной встречи; таймаут Fireflies (`UnconfirmedInvite`) считается финальным и НЕ ретраится — риск второго бота в комнате важнее риска пропущенной записи.
- `dry-run` — та же логика без реального вызова Fireflies, для диагностики "кого бы позвали сейчас".

### 4.4 Алерты (`notify.py`)
- Best-effort, независимые каналы, пробуются по очереди:
  1. SMTP-relay (`ALERT_SMTP_HOST`/`ALERT_SMTP_PORT`, дефолт `relay-corp.infra.tutu.ru:25`, без аутентификации) — не зависит от состояния EWS-сессии, переживает сбой Exchange.
  2. EWS fallback — отправка письма через тот же Exchange-аккаунт, если relay недоступен.
  3. Loop DM — прямое сообщение через `LOOP_URL`/`LOOP_TOKEN` (Mattermost-совместимый API `/api/v4`).
- Триггер: `ALERT_AFTER_FAILURES` (дефолт 2) подряд неудачных `tick`.
- Адресат: `ALERT_EMAIL`, по умолчанию — тот же `EXCHANGE_EMAIL`, который опрашивается.

## 5. Креды и конфигурация

Секреты **не хранятся** в `.env` инструмента — переиспользуются из общего `~/.config/hermes/.env` через `usertools_env.load_usertools_env()`:

| Переменная | Источник | Назначение |
|---|---|---|
| `TUTU_DOMAIN_PASSWORD` | `~/.config/hermes/.env` | пароль Exchange (или `EXCHANGE_PASSWORD` как явный override) |
| `FIREFLIES_API_KEY` | `~/.config/hermes/.env` | GraphQL API Fireflies |
| `LOOP_TOKEN` | `~/.config/hermes/.env` | fallback-канал алертов |

Локальный `.env` инструмента (`~/USERTOOLS/FirefliesAutojoin/.env`, mode 600) содержит только настройки, не секреты:

```dotenv
EXCHANGE_EMAIL=tkachenkoav@tutu.ru
EXCHANGE_SERVER=cas.tutu.ru
EXCHANGE_VERIFY_TLS=true
SKIP_PRIVATE=true
TIMEZONE=Europe/Moscow
LANGUAGE=ru
CRON_HOURS=9-19
CRON_DAYS=1-5
ALERT_SMTP_HOST=relay-corp.infra.tutu.ru
ALERT_SMTP_PORT=25
```

Прочие переменные конфигурации имеют дефолты в коде (`config.py`) и переопределяются через `.env` или окружение при необходимости: `POLL_LOOKAHEAD_HOURS=12`, `PLAN_HORIZON_MIN=40`, `FIRE_WINDOW_MIN=15`, `RETRY_GAP_SEC=300`, `MAX_ATTEMPTS=3`, `ALERT_AFTER_FAILURES=2`, `LOOP_URL=https://loop.tutu.ru`.

`TIMEZONE` используется только для отображения в логах/статусе — сравнения времени внутри `fire` timezone-aware и от неё не зависят (см. раздел 7, ограничения по расписанию).

## 6. Развёртывание

- Путь: `~/USERTOOLS/FirefliesAutojoin/` (mode 700 на `state/` и `logs/`, `.env` — mode 600; каталог намеренно вне ownCloud/WorkVault).
- Структура: `ffjoin/` (8 модулей: `config.py`, `calendar_ews.py`, `fireflies.py`, `notify.py`, `plan.py`, `state.py`, `tick.py`, `__main__.py`), `bin/run.sh`, `scripts/install-cron.sh`, `install.sh`, `uninstall.sh`, `tests/` (2 файла, 22 теста), `.env.example`, `pyproject.toml`, `requirements.txt`, `requirements-dev.txt`.
- venv: `venv_linux` (не системный python) — зависимости: `exchangelib`, `requests`.
- Установка одной командой: `./install.sh` — проверяет наличие `python3`/`crontab`/`flock`, предупреждает об отсутствующих ключах в `~/.config/hermes/.env`, создаёт `.env` из `.env.example` при первом запуске, ставит venv, гоняет `./bin/run.sh status` как проверку конфигурации **до** установки крона (чтобы неудачный конфиг не оставил битые cron-задачи), затем вызывает `scripts/install-cron.sh`.
- Cron — **системный crontab пользователя**, НЕ Hermes cron (`~/.hermes/cron/jobs.json`). Записи маркированы `# fireflies-autojoin`, `scripts/install-cron.sh` идемпотентен (сначала вычищает старые записи по маркеру, затем добавляет новые):

```
*/30 9-19 * * 1-5 flock -n ".../state/tick.lock" ".../bin/run.sh" tick >> ".../logs/cron.log" 2>&1 # fireflies-autojoin
* 9-19 * * 1-5 flock -n ".../state/fire.lock" ".../bin/run.sh" fire >> ".../logs/cron.log" 2>&1 # fireflies-autojoin
```

- Скилл Hermes: `~/hermes-workspace/skills/productivity/fireflies-autojoin/SKILL.md` (описание, когда использовать, диагностика) — см. раздел 10 про расхождение копий.

## 7. Тестирование

- `venv_linux/bin/pytest -q` — 22 теста проходят (`tests/`), покрывают фильтрацию событий, извлечение Zoom-ссылок, дедуп, rate-limit.
- `venv_linux/bin/ruff check .` — чисто (линт настроен в `pyproject.toml`: `select = ["E", "F", "I", "UP", "B"]`, `target-version = py310`).
- `./bin/run.sh status` — JSON-отчёт: доступность `fireflies_key`, состояние подключения к `exchange`, `plan_age_min` (свежесть плана), `last_tick_error`.
- `./bin/run.sh dry-run` — показывает, кого бы позвали прямо сейчас, без реального вызова Fireflies API — безопасный способ проверить логику без риска рейт-лимита или лишнего бота в реальной встрече.
- `./bin/run.sh tick` — ручной опрос календаря вне расписания (для отладки).
- E2E-проверка "живого" сценария — только наблюдением: дождаться реальной Zoom-встречи Саши и проверить, что Fred зашёл (журнал `app.fireflies.ai` + `logs/cron.log`).

## 8. Ограничения и риски

- **Только Zoom.** Teams- и Meet-ссылки не распознаются и не обрабатываются — встречи в этих сервисах бот не посещает.
- **Rate-limit Fireflies: 3 live-invite за 20 минут.** При плотном расписании (>3 Zoom-встреч подряд в 20-минутном окне) часть ботов не будет вызвана вовремя; `MAX_ATTEMPTS=3` в конфиге намеренно совпадает с реальной квотой API.
- **План обновляется раз в 30 минут (`tick`).** Встреча, добавленная или отменённая "на ходу" (после последнего `tick`, до следующего), может быть пропущена (не позвана) либо — реже — бот может быть позван на уже отменённую встречу, если отмена произошла в узком окне между `tick` и `fire`.
- **Не делает саммари/транскрипцию.** Инструмент только добавляет бота в комнату; сама запись и обработка появляются в `app.fireflies.ai`, дальнейшая работа с расшифровкой — зона ответственности отдельного скилла `fireflies-transcripts`.
- **Расписание cron — по времени сервера**, не по `TIMEZONE` из `.env`. `TIMEZONE` влияет только на отображение времени в логах/статусе; фактическое окно работы (`CRON_HOURS=9-19`, `CRON_DAYS=1-5`) интерпретируется в локальной таймзоне сервера (проверяется через `timedatectl`). Если сервер и Саша в разных часовых поясах — окно работы `tick`/`fire` может не совпадать с ожидаемым рабочим днём.
- **Приватные встречи.** С `SKIP_PRIVATE=true` (дефолт) события с пометкой Private/Confidential полностью игнорируются, бот на них не зовётся — намеренное поведение, не баг.
- **EWS-зависимость.** Вся логика `tick` держится на доступности `cas.tutu.ru` и валидности `TUTU_DOMAIN_PASSWORD`; при смене корпоративного пароля инструмент останавливается молча, пока не сработает алерт (см. `ALERT_AFTER_FAILURES`).

## 9. Откат

- **Полная остановка без удаления кода:** `./uninstall.sh` — вычищает из системного crontab только записи с маркером `# fireflies-autojoin`, файлы проекта не трогает. Идемпотентен, безопасен для повторного запуска.
- **Kill-switch без правки crontab:** удалить/переименовать `venv_linux` или сделать `bin/run.sh` не исполняемым — оба запуска (`tick`/`fire`) начнут падать с ошибкой в `logs/cron.log`, приглашений не будет; это временная мера, предпочтителен `uninstall.sh`.
- **Частичная остановка:** закомментировать одну из двух строк в crontab (например, оставить только `tick`, но не `fire`) — план будет обновляться, но приглашения не полетят.
- Полное удаление (код+state+cron): `./uninstall.sh` + `rm -rf ~/USERTOOLS/FirefliesAutojoin`. Данные в `state/*.json` при этом теряются безвозвратно (не архивируются автоматически).

## 10. Что НЕ трогать

- **Общий `~/.config/hermes/.env`** — правки ключей `TUTU_DOMAIN_PASSWORD`, `FIREFLIES_API_KEY`, `LOOP_TOKEN` затрагивают все инструменты Сирени, использующие `usertools_env`, не только `FirefliesAutojoin`. Менять только с осознанием общего эффекта и с бэкапом.
- **Апстрим-логика разделения tick/fire.** Двухтактная архитектура — осознанное решение апстрима (ТУТУ, `data-science/fireflies-autojoin`) для исключения гонки и минимизации нагрузки на EWS; сливать `tick` и `fire` в один процесс или менять их периодичность без понимания последствий для дедупа и rate-limit — не делать.
- **Механизм подключения к Fireflies (`fireflies.py`)** — GraphQL-схема `addToLiveMeeting` принадлежит внешнему API Fireflies, менять сигнатуру вызова без сверки с их документацией нельзя.
- **`~/.hermes/lib/usertools_env.py`** — общий для всех USERTOOLS кредлоадер; изменения в нём влияют на остальные инструменты (`ExchangeMonitor` и др.), которые тоже его используют.
- **Hermes Gateway** — инструмент не взаимодействует с Gateway напрямую (только системный cron + прямые HTTP/EWS вызовы), рестарт/реконфигурация Gateway не относится к работе `FirefliesAutojoin` и не требуется для его обслуживания.

## 11. Открытые вопросы

1. **Расхождение копий SKILL.md.** `~/.hermes/skills/productivity/fireflies-autojoin/SKILL.md` (6308 байт, mode 600) содержит подробное описание архитектуры, репозитория и алгоритма; `~/hermes-workspace/skills/productivity/fireflies-autojoin/SKILL.md` (4730 байт) — сокращённая версия с другим frontmatter (`version: 1.0.0` без кавычек, иной `description`, нет `tags`, другой список `related_skills`). Между каталогами нет симлинка — это разные файлы, синхронизация вручную. По конвенции проекта скиллы должны синхронизироваться через `restore-all-skills.sh`; требуется решить, какая копия — эталон, и либо синхронизировать вручную, либо восстановить симлинк.
2. **`NOTIFY_ON_SUCCESS` не реализован.** В коде (`config.py`, `notify.py`) есть только алерты на сбой (`ALERT_AFTER_FAILURES`, `ALERT_SMTP_HOST`, `LOOP_TOKEN`); подтверждения об успешном приглашении бота не отправляются ни по одному каналу. Нужно решение: требуется ли уведомление об успехе (например, в Loop) или молчаливая работа "по умолчанию всё ок" — приемлема.
3. **Реальная доступность `ALERT_SMTP_HOST` не подтверждена в этом ТЗ.** `relay-corp.infra.tutu.ru:25` указан как дефолт в `.env`, но факт успешной доставки алерта через этот relay с текущей ВМ Сирени не проверялся в рамках этой работы — при первом реальном сбое `tick`/`fire` стоит перепроверить, что письмо доходит (иначе единственным рабочим каналом алертов останется Loop DM).

## Приложения к ТЗ

Нет.
