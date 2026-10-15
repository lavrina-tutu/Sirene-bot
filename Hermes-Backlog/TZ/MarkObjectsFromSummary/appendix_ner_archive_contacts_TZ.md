---
appendix_of: MarkObjectsFromSummary_TZ.md
title: NER-прогон contacts по старому архиву встреч (до июля 2026)
status: active
version: 0.2
author: Opus (черновик для брифа с Сашей)
created: 2026-07-22
last-section-added: 2026-07-22 — решения Q11.1-Q11.8 зафиксированы; добавлен §12 План реализации
scope: разовая (или периодическая) backfill-операция; НЕ меняет штатный ежедневный пайплайн MOFS
depends_on:
  - MOFS v0.8.0 (matcher_contacts.py v0.2, text_extractor.py, mofs rematch)
  - AnywhereContacts v0.1.0 (ContactStore.get_contact_by_email, find_contacts)
  - MoveFromFF (старые файлы формата "MoveFromFF-style" в NewMeetings/)
---

# Приложение к ТЗ MOFS — NER contacts по архивным встречам

## 1. Цель

За один backfill-прогон дозаполнить `contacts:` в frontmatter старых `*-summary.md` (до 2026-07), где явной секции «Участники» нет, но участников можно надёжно извлечь из парного transcript и/или тела summary, — без ручной разметки и без переписывания архива.

## 2. Scope

**Что подпадает** (замер на 22.07.2026):

| Метрика | Значение |
|---|---|
| Всего `*-summary.md` в `NewMeetings/` | 575 |
| Файлов датированных `2025-*` или `2026-0[1-6]-*` | **514** (89%) |
| Из них имеют парный `*-transcript.md` | **513** (99.8%) |
| Файлов с явной секцией «Участники» в теле summary | 0 |
| Файлов с текущим непустым `contacts:` во frontmatter | ~0 (MOFS v0.1 не бежал) |

**Критерий «старого формата»**: файл `*-summary.md` в `NewMeetings/`, у которого `frontmatter.contacts` пуст ИЛИ отсутствует, И в теле нет распознаваемой секции «Участники» (по действующим правилам `text_extractor._extract_section("Участники")`).

Фактически совпадает с "все `*-summary.md` датой ≤ 2026-06-30". Верхняя граница scope — параметр `--to` пайплайна, по умолчанию `2026-06-30`.

**Что НЕ подпадает:**

- Файлы, где `contacts:` уже заполнен (`mofs rematch --force-empty` НЕ используется).
- Файлы без парного transcript, если тело summary не даёт ни одного кандидата.
- Файлы вне `NewMeetings/` (архивы, backup).

## 3. Источники ФИО — приоритетный порядок

Приоритет от самого дешёвого и точного к самому дорогому. На каждый файл источники обходятся по очереди; если источник i дал матч по контакту c, источники > i для того же c не пересматривают решение (но их находки добавляются к общему множеству).

| # | Источник | Как выглядит | Покрытие архива | Точность | Стоимость |
|---|---|---|---|---|---|
| **S1** | Header транскрипта, поле `**Участники:**` со списком email | `**Участники:** lyakutin@tutu.tech, tkachenkoav@tutu.ru, gribov@tutu.tech, …` | **≈85%** транскриптов (460/539 замер) | ~99% (детерминизм: email → login) | O(1), regex + `ContactStore.get_contact_by_email` |
| **S2** | Метки спикеров в теле транскрипта | `[00:12] **Лякутин Валентин:** привет.` | ≈78% транскриптов (422/539) — уникальные ФИО-спикеры | ~95% (Fireflies-разметка ФИО как «Фамилия Имя», иногда «Speaker N») | O(N speakers) × `ContactStore.find_contacts` |
| **S3** | Тело summary, свободный текст | «Александр Ткаченко отметил…», «Денис Покрасенко предложил…» | 100% файлов, но много ложных срабатываний (объектные словосочетания) | ~70% без LLM, ~90% с LLM | regex→N кандидатов; LLM — стоимость см. §7 |
| **S4** | `Action items` / `Action Items` (маркер задачи) | `- Иванов Иван: сделать X` | В старом формате MoveFromFF пункты action items **не начинаются с ФИО** (замер: 0 совпадений regex `^- Имя Фамилия:`). Источник почти всегда пуст. | — | — |
| **S5** | Имя файла | `2025-10-06 10-00-00 Кирилл 1-1 - summary.md` → «Кирилл» | ≈40% файлов имеют человекочитаемое имя; ~30% из них — однозначное ФИО | ~50% (одно имя без фамилии → неоднозначность) | regex + `find_contacts` |

**Обоснование порядка:**

- **S1 — доминирует.** Email — уникальный ключ ContactStore, никакой омонимии. Один regex по первым 1–2 KB транскрипта покрывает 85% архива детерминированно и бесплатно. Любая NER-архитектура должна начинаться с S1, иначе она платит за то, что можно взять даром.
- **S2 — почти бесплатный добор.** Транскрипты Fireflies помечают спикеров нормализованным «Фамилия Имя» — тот же формат, который уже парсит `text_extractor` в MOFS v0.8. Собираем уникальные метки, режем «Speaker N», прогоняем через `find_contacts`. Даёт +5–10% сверх S1 (случаи, когда участник говорит, но не попал в header — гости, поздние подключения).
- **S3 — LLM-этаж.** Тело summary — единственный источник для файлов без транскрипта (1 из 514 в текущем архиве) и для докручивания упомянутых, но не говоривших. Регекс `[А-ЯЁ][а-яё]+ [А-ЯЁ][а-яё]+` даёт 200+ уникальных биграмм на архив, из них ~половина — не ФИО («Такой подход», «Это позволит»). Здесь имеет смысл Haiku.
- **S4** — пустой в старом формате, оставлен как заглушка на случай если в новых файлах, куда пайплайн однажды доедет, появятся именные action items.
- **S5** — fallback для файлов совсем без спикеров и без транскрипта. Только для дополнения, не как основной источник.

## 4. Архитектура NER — три варианта

### Вар. A — детерминизм (S1 + S2 + S5)

Полностью на regex + существующем `matcher_contacts.py`. Никакого LLM.

- Извлечь email из header транскрипта → `get_contact_by_email` → `ContactHit`.
- Извлечь `**Фамилия Имя:**`-метки → `find_contacts(query)` (та же логика неоднозначности, что в matcher_contacts v0.2: 0 → unmatched, 1 → match, >1 → unmatched + WARN).
- Из имени файла — токен после даты-времени → `find_contacts` (только если ни S1 ни S2 не дали ни одного матча).

**Оценка покрытия:** ~90% файлов получат ≥1 контакт; ~75% файлов получат полный список участников встречи с точностью, сравнимой с Fireflies-разметкой.

### Вар. B — LLM по summary (S1 + S2 + Haiku по телу summary + S5)

К варианту A добавляется вызов Haiku 3.5 на тело summary с промптом: «Извлеки список ФИО реальных людей, упомянутых как участники или действующие лица встречи. Верни JSON-массив строк формата "Имя Фамилия". Не включай названия компаний, продуктов, ролей.»

- Вход: `## Bullet points` + `## Notes` (первые ~3000 токенов; остальное режется).
- Выход: JSON-list ФИО → каждое через `find_contacts`.
- Дедуп с результатами S1/S2 по login.

**Ценность:** ловит людей, упомянутых как «Юлия Соколова подчеркнула…», но не говоривших в транскрипте (частый паттерн саммари).

### Вар. C — LLM по транскрипту (S1 + Haiku по transcript + S5)

Вместо parsing спикер-меток regex-ом — Haiku читает первые ~5–10 KB транскрипта и возвращает участников с ролями (говорил / упомянут). Точнее S2 в случаях, когда Fireflies поставил «Speaker 1» вместо ФИО, но модель может по контексту («— Валентин, ты готов?») восстановить.

**Проблема:** транскрипты 20-минутной встречи — 20–40 KB; часовой — 100+ KB. Даже с обрезкой это ×3–×10 токенов по сравнению с B.

### Сравнение

| Критерий | A (детерминизм) | B (Haiku по summary) | C (Haiku по transcript) |
|---|---|---|---|
| Покрытие участников | 90% | 95% | 97% |
| Точность (доля корректных матчей от всех записанных) | 95% | 90% | 88% |
| Ложные срабатывания | очень мало (regex строгий) | средне (модель может выдумать ФИО) | средне |
| Ловит «упомянутых, но не говоривших» | нет | **да** | да |
| Стоимость на 514 файлов | **$0** | ~$0.5–1.5 | ~$5–15 |
| Время на 514 файлов | <1 мин | ~15–30 мин | ~1–2 ч |
| Воспроизводимость | 100% | зависит от температуры | зависит от температуры |
| Отладка | пошаговая (matcher уже покрыт тестами) | нужен снапшот-тест на промпт | то же + разброс входов больше |

### Рекомендация Opus

**Гибрид A + B, в два прохода:**

1. Первым проходом — только A. Ожидаемо покрывает 90% файлов и 100% файлов с header-email-ом. Стоимость ноль, риски ноль, результат сразу пишется в frontmatter (dry-run → apply).
2. Вторым проходом — B, но только для файлов, где после прохода 1: (a) `len(contacts) < 2`, ИЛИ (b) явно ожидались упомянутые лица (эвристика: в теле summary встречается ≥3 биграмм «Имя Фамилия», не совпадающих с уже найденными). Прогоняем Haiku только на этом подмножестве — по оценке ~100–150 файлов, а не 514.

Вар. C — не берём: экономически не оправдан на этом архиве. Оставить как «если понадобится позже, для встреч с плохой Fireflies-разметкой (Speaker 1/2/3)» — это ~72 файла, отдельное решение.

## 5. Матчинг в contacts.enc

**Без нового кода.** Переиспользуется `matcher_contacts.py v0.2`:

- Для S1 — новая тонкая обёртка `resolve_contacts_by_emails(emails, store) -> list[ContactHit]`, каждый email через `store.get_contact_by_email`. Логика ContactHit та же (`login/display/slug/fio_query`), `fio_query` = email (для логов).
- Для S2/S3/S5 — существующий `resolve_contacts(body_like_str, store)`. На вход подаётся синтетический «квази-body», собранный из ФИО в формате, который уже понимает `text_extractor.extract_fio_from_body` (одна ФИО на строку в псевдо-секции «Участники:»). Это позволяет НЕ менять контракт matcher-а и не расширять его тестовое покрытие.
- Логика неоднозначности (D2+D3 из master-ТЗ): 1 → match, 0 → unmatched, >1 при 1 слове — тихий unmatched, >1 при 2+ словах — unmatched + WARN.

**Slug**: `ContactHit.slug` = `display` = «Фамилия Имя [Отчество]» из `contacts.enc[login].fio`. Это уже единая политика MOFS v0.2, отдельного маппинга не нужно.

## 6. Пайплайн

**Инструмент:** отдельный подкоманд MOFS — `mofs backfill-contacts` (не отдельный инструмент, см. §11.5). Живёт в `~/USERTOOLS/MarkObjectsFromSummary/markobjectsfromsummary/backfill_contacts.py`.

**Шаги:**

```
mofs backfill-contacts \
    --from 2025-01-01 --to 2026-06-30 \
    --sources s1,s2,s5           # варианты: s1,s2,s3,s5 или пресеты: det|hybrid|full
    --llm-model haiku-3.5         # если в sources есть s3
    --min-confidence 0.8          # порог записи в frontmatter (см. §8)
    --dry-run                     # обязателен первый прогон
    [--only-empty-contacts]       # skip файлов с уже заполненным contacts
```

**Внутренний поток:**

1. Найти все `*-summary.md` в scope (§2).
2. Для каждого: прочитать frontmatter → если `contacts:` непуст И `--only-empty-contacts` (default) → skip.
3. Собрать hits по источникам S1..S5 в порядке приоритета. Логировать источник каждого hit-а в `_mark_objects_registry.json` в новом поле `contact_provenance: {login: source}` (расширение существующего provenance-механизма из v0.7).
4. Дедуп по `login`. При коллизии — сохранить source с наименьшим приоритетным номером (S1 бьёт S3).
5. Расчёт confidence (§8). Отфильтровать hits с `confidence < --min-confidence`.
6. В dry-run — вывести diff frontmatter (existing `contacts:` vs new). В apply — записать через тот же frontmatter-writer, что использует `mofs rematch`.
7. По завершении — печатать сводку: обработано / получили ≥1 контакт / полностью unmatched / средний размер списка / распределение по источникам.

**Интеграция с `mofs rematch`:** backfill НЕ вызывает rematch. Rematch — про перепроверку contacts по уже разложенным ФИО-строкам в теле summary; backfill — про извлечение ФИО-строк оттуда, где их нет. После успешного backfill можно один раз прогнать `mofs rematch --scope backfilled` для сверки (опционально; матч уже сделан на шаге 4).

**Идемпотентность:** повторный запуск с теми же параметрами и `--only-empty-contacts` — no-op на уже обработанных файлах. Без `--only-empty-contacts` — переписывает, но в dry-run сначала показывает diff.

## 7. Стоимость

Оценка для Haiku 3.5 (`$0.80 / 1M input, $4 / 1M output`, 22.07.2026):

**Вар. B — гибрид A+B (рекомендация):**

- ~150 файлов идут в LLM (после отсева проходом A).
- Средний input: 3000 токенов summary + ~200 токенов промпт = 3200 tokens.
- Средний output: список из ~5–10 ФИО = ~100 tokens.
- Итого: 150 × 3200 × $0.80/1M + 150 × 100 × $4/1M = **$0.38 + $0.06 = $0.44**.
- Время: 150 запросов × 2s (последовательно) = 5 минут; с параллелизмом 5 — ~1 минута.

**Вар. C — Haiku по transcript:**

- 514 файлов × 8000 tokens input + 100 output = 514 × 8000 × $0.80/1M + 514 × 100 × $4/1M = **$3.29 + $0.21 = $3.50**.
- Время: 514 × 3s = 25 минут (последовательно), ~5 мин (параллелизм 5).

**Вар. A — $0, <1 минуты.**

Все три оценки — на порядок ниже стоимости уже работающих LLM-конвейеров у Саши (ProtocolFromSummary), поэтому по абсолютной величине не блокер. Ограничитель — **не деньги, а качество и воспроизводимость**.

## 8. Качество

### Confidence per hit

| Источник | Base confidence | Модификатор |
|---|---|---|
| S1 (email) | 1.00 | — |
| S2 (speaker label, exact ФИО) | 0.95 | −0.10 если `find_contacts` вернул >1 (в matcher уже unmatched, сюда не попадает) |
| S3 (LLM по summary) | 0.85 | −0.15 если ФИО не встречается в теле буквально; +0.05 если встречается ≥3 раз |
| S5 (имя файла) | 0.60 | +0.20 если только 1 матч в contacts.enc; иначе unmatched |

По умолчанию `--min-confidence 0.80` → записываются S1, S2, S3 (при подтверждении регулярным вхождением). S5 требует явного повышения флага.

### Приёмка

1. **Выборочная ручная проверка:** случайные 30 файлов из 514. Метрики: precision (доля корректных `contacts:` от записанных), recall (доля найденных участников от всех реальных участников встречи — оценка «на глаз» по транскрипту).
   - Порог приёмки: precision ≥ 0.95, recall ≥ 0.85.
2. **Автотесты**: 5–8 фикстур `tests/backfill/`:
   - файл с header-email → S1 hit;
   - файл без header, но с спикер-метками → S2 hit;
   - файл только с summary → S3 hit (замокать LLM);
   - файл с коллизией имён → unmatched;
   - файл с уже заполненным `contacts:` → skip.
3. **Регрессия MOFS:** после backfill прогнать полный `pytest` (103 теста) — не должно уронить ни одного.
4. **Аудит provenance:** после apply — `_mark_objects_registry.json` должен для каждого backfilled файла содержать `contact_provenance: {login: "s1"|"s2"|"s3"|"s5"}`. Позволяет позже пересмотреть только результаты S3 без трогания S1/S2.

## 9. Что НЕ трогать

- `matcher_contacts.py` — не меняется (только вызывается из backfill).
- `text_extractor.py` — не расширяется секцией «Транскрипт»; парсинг transcript живёт в новом модуле `transcript_parser.py`, а не в text_extractor.
- Штатный `mofs run` / `mofs rematch` — не меняются; backfill — отдельная подкоманда.
- `contacts.enc` — только чтение через ContactStore; никаких новых записей (люди, которых нет в контактах — см. §11.4).
- Тело `*-summary.md` — не переписывается никогда (не вставляем «## Участники:»). Меняется только frontmatter `contacts:` и опционально `date:` (если пуст).
- `entities.json` — не трогаем, backfill только про contacts-корзину.

## 10. Связи с экосистемой

- **MOFS master** — это приложение, backfill вливается в тот же `_mark_objects_registry.json` (расширение поля `contact_provenance`). После прогона `mofs review` покажет backfilled матчи наравне со штатными.
- **MofsIndex** — после backfill FTS-индекс должен быть пересобран (`mofs-index rebuild`), т.к. заполнились `contacts:` во frontmatter 500+ файлов. Ожидаемое время ребилда — 5 сек (замер v0.1.0: 4.9с на 575 файлов).
- **EntityRegistry** — не участвует напрямую, но резолв ФИО из тела summary → contacts.enc → wiki-link `[[Фамилия Имя]]` создаст файлы `People/*.md`, которые Obsidian-граф прицепит к встречам. Это и есть польза для граф-навигации.
- **AggregateFromMeetings (AFM)** — после backfill получит корректные `contacts:` в старых встречах, что критично для карточек проектов (модуль D AFM), где секция «Участники проекта» строится агрегацией по meetings.
- **ProtocolFromSummary** — не затрагивается (PFS работает по свежим встречам, не по архиву).
- **MoveFromFF** — не затрагивается; backfill работает по уже разложенным файлам.

## 11. Решения Саши (22.07.2026)

Все восемь вопросов брифа закрыты — Саша принял рекомендации Opus без изменений. Ниже — принятые формулировки, кратко.

### 11.1. Вариант NER

**Принято: гибрид A + B в два прохода.**
- Проход 1 (детерминизм): S1 (regex email-header транскрипта) → S2 (спикер-метки в транскрипте) → S5 (имя файла, только если S1+S2 пусто).
- Проход 2 (LLM-добор): S3 (Haiku 3.5 по телу summary) — только для файлов, где после прохода 1 `len(contacts) < 2` ИЛИ в теле summary встречается ≥3 биграмм «Имя Фамилия», не совпадающих с уже найденными.
- Вариант C (Haiku по transcript) — не берём; при необходимости добавляется точечно позже.

### 11.2. Неоднозначность имён

**Принято: сохраняется действующая логика matcher_contacts v0.2** — >1 матч → unmatched + WARN. Дизамбигуация эвристиками отделов НЕ применяется. Все двусмысленные случаи с WARN дополнительно сбрасываются в отчёт `backfill_ambiguous.md` (~20–40 записей на архив) — ревью Саши вручную.

### 11.3. Минимальный порог confidence

**Принято: два прогона.**
- Первый прогон: `--min-confidence 0.90` (только S1 + S2 + S3-подтверждённый) — precision-приоритет.
- После ручной сверки — второй прогон: `--min-confidence 0.80` (добирается S3 без буквального подтверждения).
- S5 (0.60) в frontmatter не пишется никогда.

### 11.4. Люди вне contacts.enc

**Принято: НЕ писать в frontmatter, собирать в `unmatched_candidates.json`.** Формат записи:
```json
{"login": null, "fio_query": "Кирилл Гурбанов", "source": "s2", "meeting_files": [...]}
```
Placeholder-контакты в `contacts.enc` НЕ создаются (запрет засорения реестра). Ревью — раз в квартал; после добавления контактов через `anywherecontacts` CLI — точечный перепрогон `mofs backfill-contacts --only-unmatched`.

### 11.5. Архитектура

**Принято: подкоманда `mofs backfill-contacts` внутри пакета `markobjectsfromsummary`.** Отдельный tool не создаётся. Переиспользуются: `matcher_contacts`, `ContactStore`, frontmatter-writer, provenance-механизм, dry-run/apply protocol.

### 11.6. Периодичность

**Принято: только ручной запуск.** Крон-задача НЕ создаётся. Backfill — разовая операция; после первого apply запускается точечно (например, `--only-unmatched`) при добавлении новых контактов в `contacts.enc`.

### 11.7. Транскрипты без summary

**Принято: скипать.** Backfill пишет только во frontmatter summary. Файлы `*-transcript.md` без парного `*-summary.md` игнорируются; их починка — задача MoveFromFF, не backfill.

### 11.8. Поле `date:` во frontmatter

**Принято: проставлять попутно, идемпотентно, включено по умолчанию.** Флаг `--no-date-backfill` отключает эту логику. Уже заполненные `date:` не перезаписываются.

---

## Резюме на бриф (30 секунд)

- Архив: 514 старых файлов, 99% с транскриптом.
- 85% детерминированно решается regex-ом по email-header транскрипта (S1). Бесплатно, точность 99%.
- +5–10% — regex по спикер-меткам (S2). Тоже бесплатно.
- Остаток (~150 файлов) — Haiku по телу summary (S3). $0.5, 5 минут.
- Инструмент — подкоманда `mofs backfill-contacts`, не отдельный tool.
- Confidence-порог 0.80, provenance в реестре, dry-run обязателен.
- Ключевое решение Саши: (1) утвердить гибрид A+B, (2) утвердить политику «людей вне contacts.enc — в unmatched_candidates.json, не в contacts автоматически».

---

## 12. План реализации (пофайловый)

Опирается на решения §11 и текущее состояние `~/USERTOOLS/MarkObjectsFromSummary/` (MOFS v0.8.0, 103 теста). Новый функционал изолирован в отдельном модуле; штатный пайплайн MOFS не затрагивается. Не выводится полный код — только сигнатуры, структура и тестовое покрытие.

### 12.0. Сводка

**Новых файлов: 3**
1. `markobjectsfromsummary/backfill_contacts.py` — движок backfill (S1/S2/S3/S5, provenance, confidence).
2. `markobjectsfromsummary/transcript_parser.py` — парсинг transcript (header + спикер-метки).
3. `tests/test_backfill_contacts.py` — тесты движка и подкоманды.

**Изменяется: 2**
4. `markobjectsfromsummary/cli.py` — регистрация подкоманды `backfill-contacts`.
5. `markobjectsfromsummary/llm_fallback.py` (или новый `llm_ner.py`, см. §12.4) — вызов Haiku для S3.

**Не меняется, только вызывается:** `matcher_contacts.py`, `text_extractor.py`, `frontmatter.py`, `registry.py`, `pipeline.py` (только паттерны, не импорт).

### 12.1. `markobjectsfromsummary/transcript_parser.py` (НОВЫЙ)

**Назначение:** извлечение сырья из парного `*-transcript.md`. Отдельный модуль (не в `text_extractor.py`), чтобы не расширять контракт штатного парсера summary — см. §9 «Что НЕ трогать».

**Публичный API (сигнатуры):**

```python
def parse_transcript_header_emails(transcript_text: str) -> list[str]
    # S1: regex по первым 1–2 KB. Ищет строку "**Участники:** email1, email2, ...".
    # Возвращает уникальный список email-ов (порядок сохраняет),
    # мусор ("fred@fireflies.ai" — bot Fireflies) фильтруется по чёрному списку.

def parse_transcript_speakers(transcript_text: str) -> list[str]
    # S2: regex `\[\d+:\d+\]\s*\*\*([^*]+):\*\*` → уникальные ФИО-спикеры.
    # Отсекает "Speaker N", "Unknown speaker", строки короче 2 слов.
    # Возвращает список ФИО в порядке первого появления.

def find_transcript_for_summary(summary_path: Path) -> Path | None
    # Заменяет "- summary.md" → "- transcript.md" в имени файла.
    # None если файла нет.
```

**Константы модуля:** `HEADER_SCAN_LIMIT = 2048` (байт); `BOT_EMAILS = {"fred@fireflies.ai", ...}`; `SPEAKER_STOP_TOKENS = {"speaker", "unknown", ...}`.

**Тесты (в `test_backfill_contacts.py`):**
- Header с несколькими email-ами и дубликатами → uniq в порядке появления.
- Header отсутствует → `[]`.
- Спикеры «Speaker 1» / «Unknown speaker» → отфильтрованы.
- Один спикер несколько раз → в списке один раз.

**Checkpoint:** `pytest tests/test_backfill_contacts.py::test_parse_transcript_*` — зелёные. На реальном примере `2025-08-12 10-30-00 Вопросы по тг для ИБ - transcript.md`: `parse_transcript_header_emails` возвращает 6 email-ов (`lyakutin@tutu.tech`, `tkachenkoav@tutu.ru`, `gribov@tutu.tech`, `krivorotov@tutu.ru`, `surkiz@tutu.ru`, `pak@tutu.ru`), `fred@fireflies.ai` отфильтрован; `parse_transcript_speakers` возвращает {"Лякутин Валентин", "Криворотов Кирилл", "Пак Дмитрий", "Ткаченко Александр Владимирович"}.

### 12.2. `markobjectsfromsummary/backfill_contacts.py` (НОВЫЙ)

**Назначение:** ядро backfill. Держит источники S1/S2/S3/S5, provenance, confidence, dry-run/apply, идемпотентность.

**Типы:**

```python
@dataclass
class BackfillHit:
    login: str
    display: str
    slug: str
    source: str           # "s1" | "s2" | "s3" | "s5"
    confidence: float
    fio_query: str

@dataclass
class BackfillStats:
    scanned: int = 0
    skipped_already_filled: int = 0
    skipped_no_transcript_no_body_hits: int = 0
    matched_files: int = 0        # получили ≥1 hit >= min_confidence
    total_hits: int = 0
    by_source: dict[str, int]     # {"s1": 412, "s2": 87, ...}
    ambiguous_records: int = 0
    unmatched_candidates: int = 0
```

**Функции (порядок вызова = порядок в файле):**

```python
def resolve_by_emails(emails: list[str], store) -> list[BackfillHit]
    # S1. Для каждого email → store.get_contact_by_email(email).
    # confidence = 1.00. source = "s1". Дедуп по login.

def resolve_by_speakers(speakers: list[str], store, *, logger) -> tuple[list[BackfillHit], list[str], list[dict]]
    # S2. Оборачивает matcher_contacts.resolve_contacts через
    # синтетический "квази-body" (см. §5 ТЗ), чтобы не менять контракт matcher.
    # Возвращает (hits, unmatched_fios, ambiguous_records).
    # confidence = 0.95. source = "s2".

def resolve_by_llm_summary(summary_body: str, existing_logins: set[str], store, *,
                           model: str, api_key: str | None, logger) -> tuple[list[BackfillHit], list[str], list[dict]]
    # S3. Вызывает llm_ner.extract_fio_from_summary(body, model).
    # Каждое ФИО → matcher-обёртка. base confidence = 0.85,
    # +0.05 если ФИО встречается в body ≥3 раз, −0.15 если 0 раз (не должно, но safety).
    # source = "s3".

def resolve_by_filename(summary_path: Path, store, *, logger) -> list[BackfillHit]
    # S5. regex по имени файла — токен после "HH-MM-SS ". Через matcher.
    # confidence = 0.60. source = "s5". По умолчанию НЕ пишется (см. §11.3).

def should_run_llm_pass(existing_hits: list[BackfillHit], summary_body: str) -> bool
    # Триггер прохода 2 (§11.1): len(existing) < 2 ИЛИ ≥3 биграмм ФИО в теле,
    # не совпадающих с уже найденными display_name-ами.

def dedup_hits(hits: list[BackfillHit]) -> list[BackfillHit]
    # Дедуп по login. При коллизии выигрывает hit с меньшим source_order
    # (s1 < s2 < s3 < s5); confidence — max из объединённых.

def process_summary(
    summary_path: Path,
    *,
    store,
    settings,                    # аналог pipeline.Settings
    min_confidence: float,
    use_llm: bool,
    llm_model: str,
    only_empty_contacts: bool,
    no_date_backfill: bool,
    dry_run: bool,
    logger,
) -> dict
    # Возвращает per-file report:
    # {"path": ..., "action": "skip"|"apply"|"dry_run",
    #  "contacts_added": [BackfillHit...],
    #  "unmatched": [...], "ambiguous": [...],
    #  "date_backfilled": bool}
    # Идемпотентность: если only_empty_contacts=True и frontmatter.contacts непуст → skip.
    # В apply — пишет через frontmatter.write_frontmatter,
    # обновляет _mark_objects_registry.json (contact_provenance).

def run_backfill(
    *,
    from_date: date,
    to_date: date,
    sources: set[str],           # {"s1","s2","s3","s5"} или подмножество
    min_confidence: float,
    llm_model: str,
    only_empty_contacts: bool,
    only_unmatched: bool,        # для перепрогонов после пополнения contacts.enc
    no_date_backfill: bool,
    dry_run: bool,
    settings,
    logger,
) -> BackfillStats
    # 1. iter_summary_files → filter по from/to.
    # 2. Открыть ContactStore один раз.
    # 3. Для каждого файла → process_summary.
    # 4. Собрать unmatched_candidates.json и backfill_ambiguous.md.
    # 5. Печать сводки (stats).
```

**Артефакты, которые пишет модуль:**
- `WorkVault/Meetings/NewMeetings/_mark_objects_registry.json` — расширение поля `contact_provenance: {login: "s1"|...}` (совместимо с v0.7 provenance-механизмом).
- `~/USERTOOLS/MarkObjectsFromSummary/logs/backfill_unmatched_candidates.json` — по §11.4.
- `~/USERTOOLS/MarkObjectsFromSummary/logs/backfill_ambiguous.md` — по §11.2.
- Structured log через `logger.event(...)` — те же события, что и `mofs run`: `dry_run`, `processed`, `contacts_ambiguous`, `contacts_backfilled`.

**Тесты (в `test_backfill_contacts.py`):**
- `test_resolve_by_emails_dedup_and_bot_filter` — email-header с ботом и дубликатом → корректный hit-list.
- `test_resolve_by_speakers_unmatched_and_ambiguous` — фикстура на 3 спикера: 1 матч, 1 unmatched, 1 ambiguous → WARN в логе + запись в ambiguous.
- `test_should_run_llm_pass_triggers` — 4 сценария (len<2 / ≥3 биграмм / оба / ни того ни другого).
- `test_dedup_source_priority` — S1 бьёт S3 при коллизии по login.
- `test_process_summary_skip_already_filled` — `only_empty_contacts=True` + непустой contacts → action=skip.
- `test_process_summary_dry_run_no_writes` — файл на диске не меняется, registry не пишется.
- `test_process_summary_apply_writes_provenance` — в registry появляется `contact_provenance`.
- `test_date_backfill_idempotent` — пустой `date:` заполняется; уже заполненный не переписывается; `--no-date-backfill` отключает.
- `test_unmatched_candidates_json_shape` — формат из §11.4 (list of `{login,fio_query,source,meeting_files}`).
- `test_ambiguous_md_shape` — таблица `| файл | ФИО | кандидаты |`.
- `test_min_confidence_filters_s3_and_s5` — при 0.90 S3-подтверждённый (0.90) проходит, S5 (0.60) — нет.

**Checkpoint:** `pytest tests/test_backfill_contacts.py -v` — все зелёные; общий счёт `pytest` MOFS ≥ 103 + N (новые), ноль регрессий.

### 12.3. `markobjectsfromsummary/cli.py` (ИЗМЕНЕНИЕ)

**Что добавляется:**

```python
def _cmd_backfill_contacts(args: argparse.Namespace) -> int:
    # Собирает settings из config.load_settings, logger.
    # Парсит --sources как пресеты (det|hybrid|full) или список ("s1,s2,s3").
    # Вызывает backfill_contacts.run_backfill(...).
    # Возвращает 0/1 по итогу.
```

**Регистрация парсера (внутри `build_parser` / `main`):**

```python
p_bc = sub.add_parser("backfill-contacts", help="Backfill contacts: NER по архиву старых summary")
p_bc.add_argument("--from", dest="from_date", type=parse_iso_date, required=True)
p_bc.add_argument("--to",   dest="to_date",   type=parse_iso_date, required=True)
p_bc.add_argument("--sources", default="hybrid",
                  help="det|hybrid|full или список 's1,s2,s3,s5' (default: hybrid = s1,s2,s3)")
p_bc.add_argument("--min-confidence", type=float, default=0.90)
p_bc.add_argument("--llm-model", default="claude-haiku-3-5")
p_bc.add_argument("--only-empty-contacts", action="store_true", default=True)
p_bc.add_argument("--no-only-empty-contacts", dest="only_empty_contacts", action="store_false")
p_bc.add_argument("--only-unmatched", action="store_true",
                  help="Перепрогон по файлам, попавшим ранее в unmatched_candidates.json")
p_bc.add_argument("--no-date-backfill", action="store_true")
p_bc.add_argument("--dry-run", action="store_true", default=True)
p_bc.add_argument("--apply", dest="dry_run", action="store_false",
                  help="Отключить dry-run и применить изменения (обязателен явный флаг)")
p_bc.set_defaults(func=_cmd_backfill_contacts)
```

**Инвариант safety (по аналогии с `mofs run` v0.7):** без явного `--apply` работает только dry-run; scope enforcement через обязательные `--from`/`--to`.

**Тесты (в `test_backfill_contacts.py`, секция CLI):**
- `test_cli_help_lists_backfill_contacts` — `mofs --help` содержит подкоманду.
- `test_cli_default_is_dry_run` — без `--apply` → фикстурный файл не изменён.
- `test_cli_sources_preset_hybrid` — пресет разворачивается в `{"s1","s2","s3"}`.
- `test_cli_scope_required` — без `--from`/`--to` → exit 2.

**Checkpoint:** `python -m markobjectsfromsummary backfill-contacts --from 2025-01-01 --to 2026-06-30 --dry-run` на реальном vault даёт корректную сводку без записей на диск.

### 12.4. `markobjectsfromsummary/llm_fallback.py` (ИЗМЕНЕНИЕ или новый `llm_ner.py`)

**Решение:** новая функция в существующем `llm_fallback.py` (он уже настроен на anthropic-клиент MOFS), чтобы не плодить модули.

**Добавляется:**

```python
def extract_fio_from_summary(
    summary_body: str,
    *,
    model: str = "claude-haiku-3-5",
    max_input_tokens: int = 3000,
    api_key: str | None = None,
    logger=None,
) -> list[str]
    # Промпт: "Извлеки список ФИО реальных людей, упомянутых как участники
    # или действующие лица встречи. Верни JSON-массив строк формата 'Имя Фамилия'.
    # Не включай названия компаний, продуктов, ролей."
    # Вход: summary_body обрезается до max_input_tokens (по правилу tokenizer).
    # Выход: list[str], JSON-парсинг с graceful fallback на [] при ошибке.
    # Ошибки LLM/сети → logger.event("llm_ner_error", ...); возвращает [].
```

**Тесты:** мок anthropic-клиента через `unittest.mock.patch`. Проверка: (1) корректный JSON → распарсен; (2) битый JSON → `[]` + событие в логе; (3) обрезка длинного body до лимита.

**Checkpoint:** ручная проверка на одном файле summary с известными участниками — Haiku возвращает ФИО, которые есть в теле; ни одного галлюцинированного ФИО (для одной фикстуры).

### 12.5. `tests/test_backfill_contacts.py` (НОВЫЙ)

Единый файл со всеми тестами (см. §12.1–12.4). Ориентировочно 18–22 теста. Использует существующие `conftest.py`-фикстуры MOFS (temp vault, mock `ContactStore`, `mock_logger`).

**Обязательные фикстуры (внутри файла):**
- `sample_transcript_with_header` — фикстура на строку с `**Участники:** ...`.
- `sample_transcript_speakers_only` — без header, только `[00:12] **ФИО:**`.
- `sample_summary_no_participants_section` — тело без секции «Участники».
- `mock_haiku_response` — контекст-менеджер, возвращающий заданный JSON.

**Checkpoint релиза приложения:**
1. Все тесты новых модулей зелёные.
2. `pytest` полностью зелёный, регрессий в 103 существующих тестах нет.
3. Прогон `backfill-contacts --dry-run` на реальном vault показывает: `scanned≈514, skipped_already_filled≈0, matched_files≥460, by_source.s1≥400`.
4. Прогон в `--apply` на 5 случайных файлах даёт precision ≥ 0.95 (ручная сверка).
5. `_mark_objects_registry.json` для этих 5 файлов содержит `contact_provenance` с правильными источниками.

### 12.6. Порядок реализации (минимально-инкрементальный)

1. `transcript_parser.py` + его тесты — самое дешёвое, детерминированное, без сети. → CI green.
2. `backfill_contacts.py` без S3 + тесты S1/S2/S5 + `dedup_hits` + `process_summary` в dry-run. → CI green.
3. `cli.py` подкоманда + CLI-тесты. → ручной прогон `--dry-run` на реальном vault. Sanity-check §12.5 п.3.
4. `llm_fallback.extract_fio_from_summary` + мок-тесты + интеграция S3 в `backfill_contacts`. → CI green.
5. Апгрейд `process_summary` до записи `contact_provenance` + `date:` backfill + тесты идемпотентности. → CI green.
6. Первый реальный прогон с `--min-confidence 0.90 --apply` на диапазоне 2025-01-01…2025-03-31 (пилотная четверть, ~120 файлов). Ручная сверка 30 файлов.
7. Если precision ≥ 0.95 → полный прогон на 2025-01-01…2026-06-30. Затем повторный прогон с `--min-confidence 0.80` для добора.

Каждый шаг завершается коммитом с сообщением вида `mofs backfill-contacts: step N — <что сделано>`; между шагами — возможность откатиться без потери прогресса.
