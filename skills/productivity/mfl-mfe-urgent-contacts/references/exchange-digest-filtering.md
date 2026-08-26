# ExchangeMonitor — питфолы digest-фильтра (цикл дайджеста писем)

Это про **дайджест** (`mfl_digest.py` → `ExchangeMonitor/exchangemonitor/digest.py`), НЕ про urgent-путь. Заметки по настройке исключений «не оповещать о письмах Confluence без тега / о рассылках» (26.08.2026).

## Архитектура digest-пайплайна

`run_digest_exchange()` в `exchangemonitor/digest.py`:
1. `fetch_inbox_since(account, wm)` — только `is_read=False`, фильтр по watermark; `.only(...)` тянет `subject, sender, to_recipients, cc_recipients, text_body, body, item_class`.
2. **person-check** → `is_real_person(email, sender_name, cstore, person_cache)` в `person_checker.py`.
3. Если True → `compute_tag()` + `format_email()` → строка в дайджест.
4. Watermark поднимается до max `datetime_received`; если `lines` пуст → `new_wm = now_ms()`.

## Критичные факты (установлены инвентаризацией 26.08.2026, 160 писем/14 дней)

1. **Все уведомления Confluence и Jira приходят от ОДНОГО отправителя `hq@tutu.ru`.** Тип виден НЕ по email (он всегда `hq@tutu.ru`), а по:
   - sender.name с суффиксом: `Набиева Даяна (Confluence)`, `Пользователь для автоматики (Jira)`
   - subject префиксом: `[confluence] …`, `[JIRA] … / ADD-…`
   Нельзя фильтровать по отправителю `hq@tutu.ru` — убьёт все внутренние письма. Нужен разбор темы/имени.

2. **`hq@tutu.ru` есть в `contacts.enc`** → `is_real_person()` в person_checker.catch short-circuit: `get_contact_by_email(hq@tutu.ru)` вернёт контакт → `True`. Поэтому Confluence/Jira-автопоставки всегда проходят person-check, бот-маркеры им не помогают.

3. **Бот-маркеры (`BOT_MARKERS` в `person_checker.py`) проверяются только в sender email и sender.name, НЕ в теме.** Confluence-письмо с `[confluence]` в теме не ловится этими маркерами, т.к. маркер `confluence` ищется в email `hq@tutu.ru`/name `(Confluence)` — name проходит, потому что name содержит маркер `confluence`... но `hq@tutu.ru` в контактах → short-circuit срабатывает РАНЬШЕ (шаг 2 до шага 3). Итог: автопоставки проходят.

4. **Дайджест-письма приходят `to=[tkachenkoav@tutu.ru]` — даже массовый маркетинг** (Ollama `hello@ollama.com` шлёт с `to=[tkachenkoav@tutu.ru]`, `cc=[]`). Значит отличить «рассылку» по тому, что ты не единственный в To, НЕЛЬЗЯ. Только по отправителю.

### Классификация отправителей за 14 дней (образец для правил)

**Внешние рассылки/сервисы — кандидаты на блок:**
`hello@ollama.com`, `team@mail.cursor.com`, `hi@cursor.com`, `noreply@dion.vc` (dion_robot), `noreply@mail.manus.im`, `support+notifications@figma.com`, `leander@fireflies.ai`, `no-reply@todoist.com`, `team@mail.miro.com`, `info@sberuniversity.ru`, `catie.ditmore@tavily.com`, `owncloud@tutu.ru`, `ok@tutu.ru` (HR-автоматика), `hotel@tutu.ru` («Отель из избранного»).

**Внутренние автопоставки `hq@tutu.ru`:** `(Confluence)` и `(Jira)` — глушить, НО оставлять, если в теме ИЛИ теле есть тег: `Ткаченко Александр Владимирович`, `tkachenko`, либо @-упоминание в формате Confluence.

**Реальные люди (`@tutu.ru`/`@tutu.tech`, темы «Принято/Приглашение/встречи»):** оставлять.

## Правило упоминаний (для исключения Confluence)

Глушить `[confluence]`-письмо только если НЕ найдено ни одного из в теме И тяле:
- `tkachenko` / `tkachenkoav` (username / его часть)
- `Ткаченко Александр Владимирович` (ФИО)
- @-упоминание в формате, как присылает Confluence

Проверять и тему, и тело (´text_body´/´body´ уже фетчатся в `.only(...)` — доступно).

## Инвентаризация отправителей (read-only)

Как «выявить все рассылки однажды»: собрать Counter по `(sender_email, sender_name)` за N дней из `account.inbox.filter(datetime_received__gt=…)`, вывести кол-во + пример темы + `to/cc` для каждого топ-отправителя. ВАЖНО: брать ВСЕ письма (не только `is_unread`), иначе картина рассылок неполная.

`search_files` не находит исполняемые `py` в `ExchangeMonitor/exchangemonitor/` как text (some `person_checker.py` бьется как `Binary file`) — читать через `python3 -c "print(open(...).read())"`.

## РЕАЛИЗОВАНО (26.08.2026) — фильтр в продакшене

Согласовано с Сашей и внедрено через `hermes-feature` (архитектор → план → composer-2.5). Попадает в дайджест (не urgent). Рабочий путь — `exchangemonitor/`, НЕ `movefromloop/exchange_filter.py` (мёртвый код).

### Категория A — внешние рассылки (в `person_checker.py`)
Добавлены `EXTERNAL_SENDER_DOMAINS` + `EXTERNAL_SENDER_EMAILS` + `is_external_sender()`. В `is_real_person()` проверка ставится **ПЕРЕД** BOT_MARKERS и **ПЕРЕД** contacts-hit (порядок: cache → external → bot marker → contacts → sender_name). Это критично: иначе внешняя рассылка, случайно добавленная в contacts.enc, снова начнёт показываться (тот же класс бага, что `hq@tutu.ru`).
- `is_external_sender` — точное сравнение домена `rsplit("@",1)[-1] in DOMAINS` и `email in EMAILS`. **НЕ substring** (иначе `user@notcursor.com` ложно попадёт под `cursor.com`).
- Подробности реализации: см. worker session 26.08.
- Тесты: `tests/test_person_checker.py` (+5), incl. `test_external_sender_not_substring_false_positive`, `test_external_sender_overrides_contacts`.

### Категория B — Confluence (новый модуль `confluence_filter.py`)
Отдельный модуль, потому что нужны `subject` + `text_body`/`body`, которых нет в сигнатуре `is_real_person()`.
- `is_confluence_notification(email, name, subject)`: `email=="hq@tutu.ru"` AND (`"(confluence)"` в name OR `"[confluence]"` в subject). Строго требует `hq@tutu.ru` — Jira (`(Jira)`/`[JIRA]`/`ADD-…`) через него не проходит.
- `is_user_mentioned(subject, text_body, body)`: substring, case-insensitive, маркеры `("ткаченко александр владимирович", "tkachenko", "tkachenkoav@tutu.ru")`.
- `should_suppress_confluence(...)`: Confluence-письмо и НЕТ упоминания → True (глушить).
- Интеграция в `digest.py`: после `is_real_person` в цикле — `if should_suppress_confluence(...): continue`.
- Тесты: `tests/test_confluence_filter.py` (14), incl. Jira-not-affected, case-insensitive, None-body без NPE.

### Статус
- `pytest tests/` в `ExchangeMonitor` → **113 passed** (venv: `MoveFromLoop/venv_linux`).
- Smoke на реальных отправителях: Ollama/Cursor/hotel глушатся; Confluence с `tkachenko` в теле остаётся; Jira и real people (Krivorotov, Taranov) проходят.
- Манифест `render_manifest.py --check-drift` → no drift.

### Известный риск (не баг, вне задачи)
Watermark в `digest.py` продвигается только по **показанным** письмам; подавленное самое новое письмо будет повторно фетчиться (no-op). Безвредно, но при большом хвосте спама — лишняя EWS-нагрузка. Если станет проблемой — отдельный фикс: продвигать `new_wm` по последнему обработанному письму.