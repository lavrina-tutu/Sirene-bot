# OKR чекин: show / pull / apply / push

## Команды

```bash
cd ~/USERTOOLS/OKRTool

python3 -m okrtool.cli checkin show --keys OKRS-3119
python3 -m okrtool.cli checkin pull --keys OKRS-3119 --force
python3 -m okrtool.cli checkin apply --keys OKRS-3119 --set progress_pct=85
python3 -m okrtool.cli checkin push --keys OKRS-3119 --confirm
python3 -m okrtool.cli checkin parents --keys OKRS-3119
python3 -m okrtool.cli checkin propose --period "Q3 2026"
```

- `show` — первый шаг; предпочитать MD, если есть локальная копия.
- `pull --force` — только после явного «обнови» от пользователя.
- `apply` + `push --confirm` — двухшаговая запись; не `curl PUT`.

## Правило №0 (детали)

1. `find_existing(KEY)` / glob `**/OKRS-*_*.md` по **всему** `WorkVault/Projects/okr-tool/` (включая `Q3_chekin_july/` — имя папки ≠ fixVersion, не переименовывать).
2. MD есть → читать/анализировать с диска, **не** Jira.
3. MD нет → `pull`, сохранить per-task MD, дальше с диска.
4. Экспорт в GS/xlsx — поверх MD, не повод для повторного Jira.

## Родители и чужие assignee

- Писать чекин только на `assignee = tkachenkoav`; без `--allow-foreign` OKRTool откажет.
- После своих KR: `checkin parents --keys …`. Чужой parent → `STALE_PARENT <key> assignee=<фио>; child <key> %..%` — **не писать** в parent.
- Не каскадировать % и текст по Contains автоматически.

## OKR_BYPASS

Разрешено только если: OKRTool недоступен / операция вне контракта / Jira `400` на read-only (`customfield_43715`).

```
OKR_BYPASS: curl PUT OKRS-3119 customfield_43782 — причина: OKRTool недоступен
```

После обхода — обновить per-task MD (`pull` или ручная правка «Текущий чекин»).

## Склейка с SR

Источник ключей — SR-план/итог (`srtool preview` / MD в `Projects/sr-tool/`). TaskConnect — факты для текста SR, не для выбора OKR-ключей.

## Оргструктура (эскалации)

Источник — `contacts.enc`, поле `reports_to`. Цепочка АИД: Аралов → Ткаченко → Криворотов.

```python
from anywhere_contacts import ContactStore
store = ContactStore(path, key)
store.get_contact("tkachenkoav")["reports_to"]
store.find_subordinates("tkachenkoav")
```

## Верификация «выгружено всё?»

На вопрос «всё, что относится к цели X?» — свежий `GET`/`search` с `fields=issuelinks` на корневую Objective, не память сессии. Смежные ветки (Q3 при выгрузке Q1+Q2) — выгрузить или явно зафиксировать «вне scope».

## --fields / --grep / пакетный get

- Для точечного чтения полей — `show` с нужными ключами; не тащить полный JSON в чат.
- Пакет: один вызов с несколькими `--keys`, не поштучные GET.
- Фильтрация вывода — через флаги CLI (`--compact`), не сырой REST.
