---
name: move-from-keytalk
description: "Синхронизация записей Контур.Толк (KTalk) в WorkVault: транскрипт + саммари в Meetings/NewMeetings. Триггеры: обнови ktalk, обнови толк, синк контур.толк, синк keytalk, MoveFromKeyTalk."
version: "0.1.0"
author: Sirene
license: MIT
platforms: [linux]
tags: [ktalk, keytalk, kontur, meetings, workvault, cron]
metadata:
  hermes:
    tags: [ktalk, meetings, workvault]
    related_skills: [fireflies-transcripts, protocol-from-summary]
---

# MoveFromKeyTalk — ручной синк KTalk

## Где код

Пакет: `/home/tkachenkoav/USERTOOLS/MoveFromKeyTalk/`  
Интерпретатор (Linux): `/home/tkachenkoav/USERTOOLS/MoveFromKeyTalk/.venv/bin/python`

Крон и ErrorBus — отдельно (`bin/movefromkeytalk_sync.sh` + `error_bus_wrap.sh`); в этом скилле только вызов CLI.

## Когда использовать

- «обнови ktalk», «обнови толк», «синк контур.толк», «синк keytalk»
- Нужно догрузить одну запись или прогнать тестовое окно без правки кода

## Команды (абсолютные пути)

Тестовое окно (последние ~5 суток), без записи на диск:

```bash
/home/tkachenkoav/USERTOOLS/MoveFromKeyTalk/.venv/bin/python -m movefromkeytalk --mode test --dry-run --no-tg
```

Ручной синк с интервалом (ISO-8601 UTC):

```bash
/home/tkachenkoav/USERTOOLS/MoveFromKeyTalk/.venv/bin/python -m movefromkeytalk --mode manual --from 2026-10-01T00:00:00Z --to 2026-10-15T23:59:59Z
```

Одна запись по `recording_key`:

```bash
/home/tkachenkoav/USERTOOLS/MoveFromKeyTalk/.venv/bin/python -m movefromkeytalk --mode manual --recording-key <KEY> --no-tg
```

Крон на сервере (не через агента):

```bash
/home/tkachenkoav/USERTOOLS/MoveFromKeyTalk/bin/movefromkeytalk_sync.sh
```

## Флаги

| Флаг | Назначение |
|---|---|
| `--mode cron\|manual\|test` | Режим окна и поведения |
| `--from` / `--to` | Границы для `manual` |
| `--recording-key` | Точечная запись; `last_synced_at` не сдвигается |
| `--dry-run` | Без записи файлов и реестра |
| `--no-tg` | Без Telegram stale-алертов |

## Чего нет в скилле

Сетевая логика, вызов модели и текст промпта саммари живут только в USERTOOL. Несекреты — ключ `tools.move_from_keytalk` в EcosystemConfig; персональный ключ KTalk — shared env (ORCH).

## Ошибки конфигурации (fail-loud)

- **Exit 2**, если в конфиге нет `LOGS_PATH` / `PROMPT_PATH` / `KTALK_USER_KEY` (или иной ключ из `_MFKT_CONFIG_KEYS`): `run()` ловит `KeyError` и `RuntimeError` вокруг `load_settings()` → `Config error: Missing config key '...'` → exit 2. Не exit 1 silent — пустой крон был ошибкой, теперь виден.
- Крон `MoveFromKeyTalk — синхронизация каждые 10 мин` уже стоит (AC-011, job `4e689c13ae01`), expr `*/10 8-19 * * 1-5` (рабочие дни 08:00–19:50 МСК), второй job не ставить. Проверка появления новых встреч — **no-LLM** (только HTTP-листинг `/api/recordings`), токены не тратятся, если новых нет; частые проверки дёшевы.
- Крон `vm_movefromff` (Fireflies) — выключить отдельно по глаголу «ставь кроны» (AC-018), этим скиллом не трогать.

## Контракт API (v0.2.2, BUGFIX 20.10)

Рабочий путь пользовательского контура — **`GET /api/recordings`** (заголовок `X-Auth-Token`), НЕ интеграторский `/api/Domain/recordings/v2` (403 для персонального ключа). ТЗ §4/§7.

- Список: `GET /api/recordings` + `top`≤100 и `skip` (НЕ `start-from`/`start-to`/`page-token`); окно дат — клиент по `createdDate`.
- Поля записи: `id`, `title`, `createdDate`, `duration` (сек), `createdBy.login` (UUID), `participants[].userInfo.{firstname,surname}`.
- Детали: `GET /api/recordings/{id}` (lowercase). Транскрипт: `GET /api/recordings/{id}/transcript` → `{tracks:[{speaker.userInfo, chunks:[{text, startTimeOffsetInMillis}]}]}` (fallback на flat `sentences` сохранён). `/participants` отдельно НЕ звать (404) — состав из list/detail.
- Запреты: `/summary` (AC-015), `X-API-Key`, Domain/v2 не fallback.

## Известное ограничение (самаризация)

На длинных транскриптах LLM-саммари может не проходить валидацию секций (`summarize_error: LLM summary failed section validation`) — диагностика в работе, не связано с путём API.

## LLM-timeout (v0.2.5, CHANGE-LIGHT 20.10)
Клиентский таймаут LLM-саммари: **540с** default (env `MFKT_LLM_TIMEOUT`), `max_retries=0` — ретраи отданы pending backoff (§7). Раньше 300с (0.2.3) не хватало на пике для длинного транскрипта (< `CHUNK_CHAR_LIMIT=30000`) — живой замер «Кирилл 1-1»: 900с → ответ за **~101с**; 540 ≈ 5.3× типичной. `CHUNK_CHAR_LIMIT=30000` не менять (норма §11), чанки не резать. Self-overlap исключён non-blocking lock (`lock.py`, `LOCK_EX|LOCK_NB`) — второй прогон при живом первом завершается `lock_held` (exit 2), параллельной LLM-нагрузки нет; шум `lock_held` в ErrorBus при частых проверках допустим.

### Канон заголовков секций (v0.2.4, RC-1)

Промпт ff_summary даёт заголовок `Риски (Кто высказал /Вероятность /Влияние):`, но на диск уходит канон `Риски:` (SECTION_NAMES). `normalize_summary_section_headers` в summarizer.py после ответа LLM и ДО `validate_summary_sections` приводит `X (…):` → `X:` для всех шести секций. Валидатор строгий (не ослаблять), `ff_summary.json` read-only (§18). Если саммари не проходит `validate_summary_sections` — это либо флак модели (пустой/битый вывод), либо заголовок не из SECTION_NAMES — не «Риски (…)» (он нормализуется).
