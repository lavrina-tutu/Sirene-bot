# _fix_plan — preflight-ac-report-delivery (BUG:diagnose t_da2b0fa2)

Дата: 2026-09-25
Слаг: preflight-ac-report-delivery
Кейс: BUGFIX-LIGHT (рекомендация архитектора)
Диагностика: только чтение (kanban.db mode=ro, скрипт/тест/ТЗ/скилл — чтение). Ничего не менялось.

Диагноз и план создан архитектором `cursor-grok-4.6-high` (сессия 38596ec4-1972-4c7d-8bcc-39e69a84cc79).

---

## 1. ROOT CAUSE

`ac_report_ok()` (pipeline_gate_done_preflight.py, ~строки 330–372) считает PASS, если в
ЛЮБОМ источнике есть якорь `AC-\d{3}` И маркер секции («Отчёт AC» / «AC-report:» / «как тестир»):

- body+result корня;
- body+result фаз GATE:done / HF:test / HF:docs-handoff;
- ВСЕ task_comments достижимого графа;
- fallback-файл AC-report_<slug>*.md.

Это проверка «текст похож на отчёт», а не «Саша получил отчёт в диалоге».

Ложный PASS на живом графе t_15aa481f подтверждён в kanban.db (read-only): preflight на
GATE:done (t_7d85f4ea) написал «[OK] отчёт AC в comment/body/result», хотя доставки отчёта
в чат не было. Сработали три независимых ложных источника (достаточно любого):

1. Комментарий GATE:take-into-work (t_5023d9ea) — список AC-001…007 (payload приёмки). В
   формулировке AC-005 есть «как тестировали» → `_ac_report_text_ok()` зелёный.
2. Body самой GATE:done: «HITL never auto: preflight exit 0 + отчёт AC-001..010 как
   тестировали. Саша.» — инструкция, не отчёт.
3. Комментарий HF:test — перечисление IAC, снова «как тестировали» + AC-001.

В kanban.db НЕТ готового артефакта доставки: 0 комментариев/result/metadata с AC-delivered;
у task_events нет kind «posted to dialog»; kanban_notify_subs — Monitoring :7 (оркестратору),
не диалог Саши. tasks.result у GATE:done в момент preflight пустой (RESULT None) — complete
ещё не было.

Второй корень (порядок в скилле): hermes-feature сейчас делает СНАЧАЛА preflight, ПОТОМ чат.
Даже идеальная проверка маркера в таком порядке мертва: маркера ещё нет, PASS невозможен.
Доставка должна быть ДО preflight.

Канон (DevKanbanPipeline ~760–913): список/отчёт AC — диалог с Сиренью; GATE:done never auto;
preflight 0 необходим, не достаточен. Текущая строка ТЗ «требовать артефакт comment/файл»
сама фиксирует дыру «наличие ≠ доставка».

## 2. Развилки Р.1–Р.4

### Р.1. Чем гарантируем доставку
- (а) Маркер в kanban.db, ставит воркер/Сирень ПОСЛЕ реального поста в диалог — РЕКОМЕНДАЦИЯ.
- (б) Смотреть result воркера GATE:done на фразу «отчёт AC отправлен» — НЕТ: result пишется
  на kanban_complete, т.е. ПОСЛЕ Саши; в момент preflight он пуст.
- (в) Читать Telegram/чат из preflight — НЕТ: канон, только kanban.db + файлы.

Preflight НЕ может сам увидеть чат. Единственный согласованный с каноном замок — явная
аттестация того же класса, что `flag-waived: Sasha` и `auto-pass: one-pass mode`: воркер
постит в диалог, ЗАТЕМ пишет маркер, ЗАТЕМ preflight.

Остаточный риск: воркер может соврать (маркер без поста) — тот же trust, что у flag-waived.
Криптопроверки чата из sqlite нет. Страховка: GATE:done всё равно HITL never auto — без отчёта
в чате Саша не скажет «готово».

### Р.2. Где фиксировать
РЕКОМЕНДАЦИЯ: комментарий карточки GATE:done.
- Preflight уже читает task_comments.
- result GATE:done в момент preflight пуст — не подходит.
- task_runs.metadata допустим как второй канал (ac_delivered: true), не основной.
- Не корень, не GATE:take-into-work (там живёт список AC-001, не отчёт).

Каноническая строка (как `flag-waived: Sasha`): `AC-delivered: dialog`
Допустимый хвост: `AC-delivered: dialog chat=<id> msg=<id>`.
PASS: regex `AC-delivered:\s+\S+` (голый `AC-delivered:` — FAIL).
message_id не обязателен.

Один комментарий на GATE:done содержит И маркер, И тело отчёта:
```
AC-delivered: dialog
## Отчёт AC
AC-001 → команда / лог / результат
…
```

### Р.3. Строгость и «список ≠ отчёт»
- FAIL, если маркера нет — ДАЖЕ если артефакт AC есть.
- Маркер ТОЛЬКО на GATE:done (не по всему reach).
- Контент-проверку СУЗИТЬ: не сканировать все комментарии графа. Источники тела отчёта —
  комментарии GATE:done и/или файл AC-report_<slug>*.md. ИСКЛЮЧИТЬ GATE:take-into-work,
  body-шаблон GATE:done, комментарии HF:test.
- Оба условия обязательны: маркер И `_ac_report_text_ok` на суженном тексте.

### Р.4. Кейс
**BUGFIX-LIGHT.**
- ≤3 файла impl: скрипт + тест + hermes-feature/SKILL.md (перестановка порядка + строка маркера).
- Вне ядра канбана.
- Нет новых сущностей/cron/.env/манифеста/фаз.
- Скилл НУЖЕН в том же HF:impl, иначе проверка и писатель маркера разъедутся (все живые
  GATE:done начнут FAIL). tz-workflow в этой фазе НЕ трогать (это про AC-001 на
  GATE:take-into-work, другой гейт).
- TZ:patch этого же графа должен заменить в master-ТЗ строку «требовать артефакт comment/файл»
  на контракт маркера.

## 3. ПЛАН ПОЧИНКИ П.1…П.N

Порядок воркера GATE:done после фикса (контракт):
1. Собрать отчёт AC-### → как тестировали (команда, лог/артефакт, результат).
2. Опубликовать его в ДИАЛОГ Саши (не Monitoring :7).
3. kanban_comment на GATE:done: `AC-delivered: dialog` + тело отчёта.
4. Запустить preflight.
5. exit 0 → kanban_block (review-required: ждать «готово»). Complete — только Саша.
6. exit ≠ 0 → comment чек-листа, block, complete запрещён.

Preflight по-прежнему НЕ доставляет. Доставка — до preflight.

### П.1. Константы и проверка маркера в pipeline_gate_done_preflight.py
Файл: ~/WorkVault/Registries/pipeline_gate_done_preflight.py
- Добавить `AC_DELIVERED_MARKER = "AC-delivered:"` и `AC_DELIVERED_RE = re.compile(r"AC-delivered:\s+\S+")`.
- Новая `ac_delivered_ok(conn, phase_cards)`:
  - карточки фазы GATE:done в графе обязательны (карточка есть; НЕ требовать status=done);
  - сканировать ТОЛЬКО их: task_comments.body, опционально task_runs.metadata;
  - PASS если regex нашёл маркер;
  - FAIL: «нет маркера доставки AC (AC-delivered: на GATE:done)» или «фаза отсутствует в графе: GATE:done».
- НЕ читать tasks.result GATE:done как доказательство доставки.

### П.2. Сузить ac_report_ok() — контент ≠ весь граф
Там же.
- Убрать обход ВСЕХ комментариев reach и body+result корня / HF:test / HF:docs-handoff / body-шаблона GATE:done.
- Тело отчёта: комментарии карточек GATE:done + fallback-файл AC-report_<slug>*.md.
- `_ac_report_text_ok` без изменения семантики.
- Логи развести: «[OK] тело отчёта AC» vs «[OK] маркер доставки AC».
- В main после (3b) добавить (3c) ac_delivered_ok; оба FAIL копятся в all_problems, exit 1.

### П.3. Не добавлять GATE:done в mandatory_phases как «должна быть done»
Иначе deadlock (complete только после Саши). Требовать лишь НАЛИЧИЕ карточки + маркер.

### П.4. Фикстуры теста test_pipeline_gate_done_preflight.py
Файл: ~/WorkVault/Registries/test_pipeline_gate_done_preflight.py
- В CHANGE_PHASES / BUGFIX_PHASES / BUGFIX_LIGHT_PHASES / CHANGE_LIGHT_PHASES добавить "GATE:done"
  (в готовых графах статус НЕ done: todo/blocked через phase_status).
- build_graph:
  - ac_report_comment=True больше НЕ должен быть достаточным для PASS (кладёт AC_REPORT_COMMENT на корень).
  - Новый флаг ac_delivered=True (default для ready-графов): комментарий на карточку GATE:done:
    `AC-delivered: dialog\n## Отчёт AC\nAC-001 → pytest ok`
  - Старый ac_report_comment оставить для негативных тестов.

### П.5. Какие тесты менять / добавить
Изменить (иначе покраснеют ready-графы): T1, T6, T10, T11, T12, T13, T14 → PASS только с
ac_delivered=True на GATE:done. T16 → без отчёта и без маркера exit 1. **T17 → файл AC-report_*
без маркера exit 1** (закрытие дыры).

Добавить (T18–T25): см. сценарии в диагностике архитектора — регресс живого бага (комментарий
только на take-into-work), шаблон-body GATE:done без маркера, маркер+тело на GATE:done exit 0,
маркер без тела exit 1, тело без маркера exit 1, файл+маркер exit 0, голый `AC-delivered:` exit 1,
маркер на корне/HF:test exit 1.

Прогон: `python3 -m pytest ~/WorkVault/Registries/test_pipeline_gate_done_preflight.py -q`

### П.6. Скилл hermes-feature (3-й файл, тот же HF:impl)
Файл: ~/.hermes/.hermes/.../devops/hermes-feature/SKILL.md (секция «GATE:done — статус «готово»»,
~175–186; зеркало one-pass п.3 ~218).
Заменить порядок на П.0 (доставка → маркер → preflight → block). Явно: НЕ считать comment
GATE:take-into-work / Monitoring доставкой отчёта. После правок — restore-all-skills.sh (синка
профилей), операторка ORCH. tz-workflow НЕ менять в этой фазе.

### П.7. TZ:patch этого графа (не impl, отдельная фаза LIGHT)
В DevKanbanPipeline_TZ.md (~877): «Требовать маркер AC-delivered: на comment GATE:done И тело
отчёта (comment GATE:done или файл); не принимать список AC с GATE:take-into-work». В «Порядок
воркера»: доставка в диалог ДО preflight. Не парсить формулировки AC.

### П.8. Вне скоупа этой починки (не делать)
- Ядро канбана, новые фазы, склейка фаз, auto-complete GATE:done.
- Проверка доставки СПИСКА AC-001 на GATE:take-into-work (похожая дыра, другой гейт, нет
  preflight) — отдельная карточка.
- Чтение Telegram API / hermes send из preflight.

## 4. Кейс-классификация
BUGFIX-LIGHT (BUG-L).
Сборка: DX → TZ-WRITE(patch) → TAKE-INTO-WORK → PLAN-IMPL-TAIL-LIGHT (HF:impl → HF:test →
HF:docs-handoff → GATE:done). Skip: HF:plan / GATE:plan-approve / HF:backup / ORCH / REV.
Impl-файлы: (1) pipeline_gate_done_preflight.py (2) test_pipeline_gate_done_preflight.py
(3) hermes-feature/SKILL.md.
Рекомендация архитектора: скилл в том же impl.

## 5. РИСКИ / ОГРАНИЧЕНИЯ
- Preflight read-only, нет канала в чат → маркер.
- Ядро/TERMINAL_KINDS/новые фазы → не трогать.
- Порядок скилла (preflight → чат) + новый FAIL без маркера = deadlock → П.6 в том же пакете.
- Воркер врёт маркер → принятый trust; HITL Саши достаточен для complete.
- Monitoring :7 ≠ диалог → маркер не ставить по notify-подписке.
- T17 сегодня зелёный на файле без доставки → сознательно ломаем; замена T23.
- In-flight GATE:done после выката → штатный FAIL, пока Сирень не постит и не пишет маркер.
- AC-001 (список в чат) той же дырой → вне скоупа; не раздувать LIGHT.