---
name: mfl-mfe-urgent-contacts
description: "Управление списком срочных получателей для MoveFromLoop (MFL"
version: 1.0.1
author: Sirene
license: MIT
platforms: [linux]
tags: [mfl, mfe, urgent, contacts, loop, exchange, rules]
related_skills: [about_usr_skills, hermes-feature]
---

# MFL/MFE — управление urgent_contacts

## Когда использовать
- Саша просит изменить список срочных получателей (добавить/убрать/пересмотреть)
- Нужно посмотреть текущий список urgent_contacts
- Работа с MFL (`MoveFromLoop`) или MFE (`ExchangeMonitor`)

## Единый источник правды
Все изменения списка делаются **только** в файле:

`~/USERTOOLS/MoveFromLoop/loop_rules.yaml`

Этот файл используется обоими инструментами через общие скрипты `mfl_urgent_check.py` и `mfl_digest.py`.

## Текущий список (после обновления 03.09.2026)

```yaml
urgent_contacts:
  - alekseeva.ym  # Алексеева Юлия
  - aralov        # Аралов Александр
  - agababyan     # Агабабян Арут
  - gladkikh      # Гладких Юрий
  - khrupov       # Хрупов Дмитрий
  - kotelnikova   # Котельникова Ольга
  - malyy         # Малый Денис
  - nabieva       # Набиева Даяна
  - peretyatkova  # Перетяткова Екатерина
  - rasov         # Расов Арсений
  - tsyba         # Цыба Леонид
  - zaynullin     # Зайнуллин Ильдар
  - zhirov        # Жиров Александр
```

**История изменения:**
- 21.08.2026: добавлены руководители АиД: alekseeva.ym, kotelnikova, nabieva, peretyatkova, rasov, zhirov
- 21.08.2026: Солдатенков (soldatenkov) не добавлен по явной просьбе Саши; Середа (sereda) исключён — уволился
- 03.09.2026: добавлен zaynullin (Зайнуллин Ильдар), username подтверждён через Loop API (infrastructural engineer)

## Процедура обновления

1. Открыть `loop_rules.yaml`
2. Отредактировать секцию `urgent_contacts` (сохранять алфавитный порядок + комментарии с ФИО)
3. Обновить этот skill / reference (чтобы следующая сессия сразу видела актуальный список)
4. При необходимости — запустить `mfl_urgent_check.py` для проверки

## Связанные файлы
- `references/mfl-mfe-urgent-contacts.md` — этот документ (история + актуальный список)
- `references/exchange-monitor-pitfalls.md` — питфолы MFE: `should_skip()` глушит встречи, watermark-поведение, два пути фильтрации, реальный кейс «письмо есть, уведомления нет» (env-цепь без CONTACTS_ENCRYPTION_KEY + venv без yaml) **и принятое решение — единая env-схема USERTOOLS** через общий loader `~/.hermes/lib/usertools_env.py` (бизнес-секреты → `~/.config/hermes/.env`)
- `references/exchange-digest-filtering.md` — digest-фильтр писем (не urgent): **реализовано 26.08.2026** (категория A `is_external_sender`=внешние рассылки; категория B `confluence_filter.py`=Confluence глшится без упоминания, Jira всегда оставляем). Там же классификация отправителей за 14 дней, критичные факты (`hq@tutu.ru` в contacts.enc обходит person-check, бот-маркеры не смотрят в тему, дайджест-письма всегда `to=[мне]`), инвентаризация read-only, риски watermark
- `loop_rules.yaml` — настоящий конфиг (единственный источник)

**Правило:** Никогда не хардкодить список urgent_contacts в кронах или скриптах — всегда читать из `loop_rules.yaml`.

---
