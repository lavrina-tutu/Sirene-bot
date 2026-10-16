---
name: MppReader
tool: MppReader
version: 1.0.0
date: 2026-09-04
status: active
author: архитектор (Cursor CLI, по заданию Саши Ткаченко)
last-section-added: 2026-09-04 — master-ТЗ: ретрофит .mpp/gantt + роадмап-вход + токен + права
---

# MppReader — ТЗ

Автор: архитектор (Cursor CLI). Канал: скилл `read-mpp` + пакет `~/USERTOOLS/MppReader/`. Новый скилл/пакет не заводится.

## Цель

По запросу Саши в чате собрать **новый** Google Sheets документ в формате плана MS Project из одного из трёх входов (.mpp, Gantt CSV, GS-роадмап) и вернуть ссылку с правами writer на два фиксированных email.

## Место в экосистеме

- Класс: on-demand конвертер планов, **не** крон.
- Скилл: `productivity/read-mpp` (канон: `~/hermes-workspace/skills/productivity/read-mpp/SKILL.md`).
- Код: `~/USERTOOLS/MppReader/`.
- Соседи: `deep-mine-project` вызывает **только** `read_mpp.py` (CSV в overlay, **не** скилл `read-mpp`); `page-to-schedule` reuse `get_services` / `fmt_date` / `fmt_dur` и пишет **свой** профиль import (8 колонок) — этот ТЗ его не меняет.
- Приложение: Google Sheets/Drive (OAuth `~/.hermes/google_token.json`).

## Входы

| # | Вход | Триггер (скилл) | Скрипт | Профиль колонок результата |
|---|---|---|---|---|
| 1 | файл `.mpp` (через `.zip` в Telegram) | «прочитай mpp», «конвертируй mpp в gs» | `read_mpp.py` → `push_to_gs.py` | **export** 16 колонок |
| 2 | Gantt CSV `gantt-chart-export_*.csv` | «залей gantt csv» | `gantt_csv_to_gs.py` | близкий к export (без Текст2–6) |
| 3 | Google Sheets **роадмап** (URL) | «план из роадмапа», «план MS Project в GS из роадмапа» | `roadmap_gs_to_gs.py` | **гибрид** 10 колонок (канон разового прогона 04.09) |

Каждый вход → **отдельный новый** GS-документ (не вкладка в существующем). Имя занято → суффикс `-2`, `-3`.

### Вход 3 — колонки исходного роадмапа

`Инициатива | Описание | Статус (Internal/SaaS) | Ожидаемый релиз SaaS | Ожидаемый релиз On premise (VPC) | Комментарий (на дату) | Ссылка на версию вендора`

Эталон источника (11 инициатив, 04.09): `https://docs.google.com/spreadsheets/d/1JFOpXzva0L-gkGbliS34effsQSMZ5lgZuGoIqtgQZyQ/`. Заголовок «Комментарий (…)» матчится по префиксу `Комментарий`. Колонка ссылки вендора **игнорируется**. Пустая «Инициатива» → строка пропускается.

## Маппинг (вход 3, канон 04.09)

| Колонка плана | Источник |
|---|---|
| No | порядковый номер, с 1 |
| Название задачи | Инициатива |
| % выполнения | Статус: `Done`=100, `In progress`=50, `Backlog`=0 (без знака `%`, как в документе `1Hl9morTJC…`) |
| Длительность | пусто (не задавать вручную) |
| Названия ресурсов | пусто |
| Текст1 | Описание |
| Текст2 | Комментарий |
| Начало | Ожидаемый релиз SaaS → календарная точка |
| Окончание | Ожидаемый релиз On premise (VPC) → календарная точка |
| Предшественники | пусто |

Плоский список: без WBS, без summary-строк, без связей. Неизвестный статус → ошибка (fail-loud, не угадывать).

## Квартальные метки

Каждая метка в ячейке → **одна** календарная дата (не интервал «с 1-го по последнее»).

| Метка | Дата |
|---|---|
| `early YYQn` | последний день 1-го месяца квартала |
| `mid YYQn` | последний день 2-го месяца квартала |
| `end YYQn` или `YYQn` без модификатора | последний день квартала |
| диапазон `A - B` в одной ячейке | для **этой** колонки берётся конец периода **B** |
| `-` (и пустая ячейка) | дата пустая |
| `Deprioritized` | **max** среди уже разобранных дат **всего плана** (и для Начала, и для Окончания). Это не константа. Если в плане нет ни одной обычной даты — ошибка |

Кварталы: Q1=янв–мар, Q2=апр–июн, Q3=июл–сен, Q4=окт–дек. Год двузначный (`26` → 2026). Последний день месяца — `calendar.monthrange` (високосные учитываются).

Примеры (2026, не високосный): `26Q3` → 30.09.26; `mid 26Q4` → 30.11.26; `early 26Q4` → 31.10.26; `end 26Q3 - early 26Q4` → 31.10.26.

Формат даты в ячейке плана: `пн DD.MM.YY` (день недели укороченный русский: пн вт ср чт пт сб вс). Тот же `fmt_date`, что в `push_to_gs.py`.

Эталон результата 04.09: `https://docs.google.com/spreadsheets/d/1Hl9morTJCaf4kQVXtQWKkzz3TFu0pTyEM3aTcqCA2ro/` — Semantic Layer 30.11/31.12 50%; Admin API 30.09/30.09 100%; self-observability старт пустой / окончание 31.10; MDEv2 = max даты плана.

## Профиль колонок

Три профиля **не смешивать в одном листе**.

**Гибрид (роадмап → GS)** — 10 колонок, канон этого ТЗ для входа 3:

`No | Название задачи | % выполнения | Длительность | Названия ресурсов | Текст1 | Текст2 | Начало | Окончание | Предшественники`

**export (.mpp → GS)** — 16 колонок `push_to_gs.py`:

`№ | % завершения | Название задачи | Длительность | Названия ресурсов | Предшественники | Начало | Окончание | Отклонение окончания | Базовое окончание | Текст1 | Текст2 | Текст3 | Текст4 | Текст5 | Текст6`

**import (страница → GS, владелец `page-to-schedule`)** — 8 колонок. Этот ТЗ **не** владеет им и не меняет.

Вёрстка выдачи MppReader: лист `Задачи`; Calibri 11; заголовок Arial 9, фон `#DFE3E8`; freeze row 1. Для .mpp дополнительно: summary bold, outline 1 = Calibri 16, цвет фона из MPP.

## Права

Константа `SHARE_EMAILS`: `tkachenkoav@tutu.ru`, `i.alex.tkachenko@gmail.com`, роль `writer`, без notification email.

**Не** `--share anyone`. Вчерашний разовой прогон `.mpp` с `anyone/writer` в этот ТЗ **не** входит.

## Токен

Default: `~/.hermes/google_token.json`.

Порядок: `GOOGLE_TOKEN_PATH` (если задан) → `HERMES_HOME/google_token.json` (если `HERMES_HOME` задан) → `~/.hermes/google_token.json`.

Устаревший fallback `~/.hermes/profiles/anthropic/google_token.json` **запрещён** (профиль декомиссован).

Scopes: Drive + Sheets. Аккаунт: `tkachenkoav@tutu.ru`.

## Реализация-файлы

### Создать

| Файл | Назначение |
|---|---|
| `TZ/MppReader/MppReader_TZ.md` | этот master-файл |
| `USERTOOLS/MppReader/quarter_labels.py` | чистый парсер меток |
| `USERTOOLS/MppReader/roadmap_gs_to_gs.py` | GS/CSV роадмап → гибрид-строки → reuse create/format/share |
| `USERTOOLS/MppReader/tests/test_quarter_labels.py` | фикстуры меток 04.09 |
| `USERTOOLS/MppReader/tests/test_roadmap_map.py` | 11 инициатив, без сети |
| `USERTOOLS/MppReader/tests/fixtures/roadmap_sample.csv` | срез эталонного роадмапа |

### Изменить

| Файл | Что |
|---|---|
| `MAIN_TZ_INVENTORY.md` | строка MppReader |
| `hermes-workspace/skills/productivity/read-mpp/SKILL.md` | третий триггер; путь токена; не звать для deep-mine |
| `USERTOOLS/MppReader/push_to_gs.py` | default токена; общая функция create/format/share |
| `USERTOOLS/MppReader/gantt_csv_to_gs.py` | тот же default токена |
| `USERTOOLS/MppReader/README.md` | третий вход |
| `WorkVault/Registries/EcosystemManifest.json` | tool `mpp_reader`, skill `read-mpp`, скрипт `roadmap_gs_to_gs.py` |

CLI входа 3:

```bash
python3 ~/USERTOOLS/MppReader/roadmap_gs_to_gs.py <GS-URL-или-ID> [--title "…"]
python3 ~/USERTOOLS/MppReader/roadmap_gs_to_gs.py --from-csv <path.csv> [--title "…"]  # без чтения Google; запись GS всё ещё live
```

Юнит-тесты вызывают маппер напрямую по CSV, Google не трогают.

## Что не трогать

- `read_mpp.py` (чтение .mpp / mpxj / JVM).
- Запись .mpp (`read_write_mpp_com.py` и любой COM-путь).
- Скилл и скрипты `page-to-schedule` (профиль import, FIELD_MAP, календарь).
- `ConfluenceSync`, `deep-mine-project` (включая правило «скилл `read-mpp` не вызывать для бурения»).
- `record-mobile-notes`.
- Кроны — не создавать. Gateway — не рестартовать.
- `--share anyone` — не добавлять в этом ТЗ.

## Связи с существующими инструментами

| Инструмент | Связь |
|---|---|
| `deep-mine-project` | читает `read_mpp.py` → CSV; скилл `read-mpp` **не** вызывать |
| `page-to-schedule` | reuse OAuth/`fmt_*`; пишет import-профиль сам; не роадмап |
| `google-workspace` (`google_api.py`) | тот же токен `~/.hermes/google_token.json`; роадмап-вход **не** ходит в CLI google_api — Sheets API из `get_services()` |
| `SkillsImprovement` C0 | канон export/import; гибрид 10 колонок — **третий** профиль, только вход 3 |

Reuse-first: новый пакет USERTOOLS и новый скилл **не** предлагаются (решение Саши 04.09).

## Связи с инфраструктурой Hermes

- OAuth-файл в `~/.hermes/`, не в профиле.
- Скилл в `hermes-workspace` + sync в default.
- Java 17 + mpxj только для входа 1; входы 2 и 3 Java не требуют.
- Крон/ErrorBus для MppReader не подключаются (on-demand).

## Критерии успеха

- Команда «сделай план MS Project в GS из роадмапа `<url>`» без уточнений по уже закрытым правилам → ссылка `https://docs.google.com/spreadsheets/d/<ID>/edit`.
- 11 инициатив эталона: Semantic Layer `пн 30.11.26` / `чт 31.12.26` / 50; Admin API `ср 30.09.26` / `ср 30.09.26` / 100; self-observability Начало пустое, Окончание `сб 31.10.26`; MDEv2 обе даты = max плана.
- Права только на два email, не anyone.
- `pytest -m "not live"` в `USERTOOLS/MppReader/` зелёный. Live Google — только по отдельной команде.
- `read_mpp.py` без diff.

## Открытые вопросы

Нет. Решения брифа 04.09 закрыты (канал = `read-mpp`; гибрид 10 колонок; токен `~/.hermes/google_token.json`; не anyone). Запрос 03.09 «всем по ссылке» отложен, в этот ТЗ не входит.

## Приложения к ТЗ

Пока нет (`appendix_*.md` не создавались). Эталонные CSV — в `USERTOOLS/MppReader/tests/fixtures/` (runtime, не TZ).

---

## История доработок

- **2026-09-04** — v1.0.0. Ретрофит существующих входов .mpp/gantt + вход «роадмап GS → план GS». Правила кварталов/%/Deprioritized зафиксированы по разовому прогону 04.09, который Саша не оспорил.

---

## Контракты экосистемы

### Источник истины

- Владелец записи плана в Google Sheets: MppReader (новый документ на каждый прогон).
- Владелец исходного роадмапа: внешний GS (не этот инструмент).
- Владелец CSV из .mpp: `read_mpp.py` (не меняется этим ТЗ).

### Входные контракты

| Поле | Тип | Обязательность | Источник (кто отдаёт) | Формат/enum |
|---|---|---|---|---|
| roadmap_url | str | optional | Пользователь / скилл read-mpp | URL Google Sheets или spreadsheetId |
| initiative | str | required | исходный GS-роадмап | текст названия инициативы |
| description | str | optional | исходный GS-роадмап | Текст1 |
| status | enum[Done, In progress, Backlog] | required | исходный GS-роадмап | → 100/50/0 |
| saas_release | str | optional | исходный GS-роадмап | квартальная метка / `-` / `Deprioritized` |
| vpc_release | str | optional | исходный GS-роадмап | квартальная метка / `-` / `Deprioritized` |
| comment | str | optional | исходный GS-роадмап | Текст2 |
| google_token_path | str | optional | env `GOOGLE_TOKEN_PATH` / `HERMES_HOME` | путь к OAuth JSON |

### Выходные контракты

| Поле | Тип | Потребитель (кто получает) | Формат/enum |
|---|---|---|---|
| spreadsheet_url | str | LLM-сессия / Саша | `https://docs.google.com/spreadsheets/d/<id>/edit` |
| No | int | Google Sheets (гибрид) | 1-based порядковый номер |
| Название задачи | str | Google Sheets (гибрид) | = initiative |
| % выполнения | int | Google Sheets (гибрид) | 100 / 50 / 0 |
| Начало | str | Google Sheets (гибрид) | `пн DD.MM.YY` или пусто |
| Окончание | str | Google Sheets (гибрид) | `пн DD.MM.YY` или пусто |
| tasks_csv | str | deep-mine-project | `{stem}__tasks.csv` из `read_mpp.py` (вход 1) |

### Зависимости

- Получает от: [Google Sheets API (роадмап), файл .mpp (вход 1), Gantt CSV (вход 2)]
- Отдаёт: [Саша в чате (ссылка GS), deep-mine-project (только CSV `read_mpp.py`), page-to-schedule (reuse `get_services`/`fmt_date`/`fmt_dur`)]

### Breaking changes policy

- Версионирование формата: semver на поле `schema_version` не используется (нет внутреннего JSON-store). Стабильны: имена 10 колонок гибрида, правила кварталов, `SHARE_EMAILS`.
- При breaking change колонок: бамп версии ТЗ, обновить скилл `read-mpp` и тесты `test_roadmap_map.py`, уведомить потребителей из «Отдаёт».

### Границы («что НЕ трогать»)

- Не менять `read_mpp.py` и не писать .mpp.
- Не менять профиль import `page-to-schedule` и не звать `read-mpp` из `deep-mine-project`.
- Не раздавать документ как `anyone`.
- Не хардкодить путь `profiles/anthropic/google_token.json`.
