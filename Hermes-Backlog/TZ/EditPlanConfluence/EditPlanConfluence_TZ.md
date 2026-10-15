---
tool: EditPlanConfluence
version: 0.2.2
date: 2026-10-01
status: approved (TZ:finalize 01.10 render-fix 0.2.2; implemented v0.2.0 09.09; version-inc 0.2.1)
author: architect (cursor-grok-4.6-high)
last-section-added: 2026-10-01 — TZ:finalize v0.2.2 render-fix (outline_level=0 шапка + однострочное «Итого»)
depends_on:
  - MppReader
  - ConfluenceSync
  - tutu-confluence-jira
brief_session: 5d622690-f36e-4569-aea2-1a2ac776d807
---

# EditPlanConfluence — ТЗ

Скилл Hermes `productivity/edit-plan-confluence`: залить план MS Project (`.mpp`) на страницу Confluence с макросом **gantt-chart-planner**. Реализация кода **запрещена** до явного «берём в работу». Согласование этого ТЗ ≠ команда на реализацию.

## Приложения к ТЗ

Пока нет. Эталонные артефакты этапа тестирования (08.09.2026) на ВМ: `/tmp/mpp_to_gantt.py`, `/tmp/build_calendar2.py`, `/tmp/gantt_test.json`, `/tmp/gantt_newplan.json` — **не runtime-зависимости**; логику перенести в скрипты скилла.

---

## 1. Цель

По команде в чате и присланному файлу `.mpp` сделать так, чтобы страница Confluence с макросом `gantt-chart-planner` показывала **тот же план, что в файле** (задачи, даты, ресурсы, назначения, связи FS, календарь рабочего времени), и чтобы над макросом стояла одна строка «Итого» вида `Итого: с DD.MM.YY по DD.MM.YY - N рабочих дней` (без строки «Трудозатраты»).

---

## 2. Контекст и проблема

План AB-платформы ТУТУ живёт в Confluence как макрос плагина Gantt Chart Planner. Плагин хранит данные **не в storage страницы и не в БД плагина**, а в JSON-вложении `gantt-chart-<macro-id>.json`. Саша ведёт канон в MS Project; руками переносить план на страницу нельзя. Этап тестирования (pageId `519501810`) доказал чтение/запись вложения, конвертацию MPP→JSON и синк календаря. Спайк 08.09.2026: программная установка макроса и создание дочерней страницы через REST работают, UI не нужен (дочка `519502120`).

---

## 3. Что делаем (Scope v1) vs Что НЕ трогаем

### Scope v1

- Прочитать план: скачать JSON-вложение макроса на указанной странице.
- Залить `.mpp` → **полная замена** JSON вложения (дерево, даты как посчитал Project, ресурсы, назначения, effort, предшественники FS, календарь).
- Работать с **любой** страницей, у которой есть макрос `gantt-chart-planner` (pageId из чата или сессии).
- Если макроса нет — поставить его REST (новые uuid `macro-id` / `id` / `hash` + вложение).
- Создать дочернюю страницу от указанного родителя: сразу макрос и сразу план.
- Патч блока «Итого» в теле страницы: одна строка `Итого: с DD.MM.YY по DD.MM.YY - N рабочих дней` (N = ceil duration корня из MPP). Строка «Трудозатраты» не создаётся и удаляется из storage, если уже есть.
- Гейт: дифф + явное «лей». Нет pageId — спросить, не угадывать. Помнить pageId **в рамках сессии**.
- Новый MPP на ту же страницу: в диффе предупреждение «план будет заменён целиком».

### Non-goals / этап 2 (не реализовывать)

- Поштучные чат-правки задач (имя, даты, duration, связи, ресурс, units, percentDone, effort, add/delete, иерархия).
- Каскад / планировщик (даты в v1 только из MPP).
- Связи SS/FF, lag≠0, `constraintType`, baselines, календари ресурсов (не Default Calendar).
- Экспорт JSON→MPP.
- Merge MPP с чат-правками по задачам/полям; метки `mpp_<ts>` / `chat_<ts>` на сущностях.
- Третья строка про «70%» — не создавать и не выдумывать.
- Трогать любые страницы кроме целевой; `web_extract` на `dom.tutu.ru`.
- Менять скиллы `read-mpp`, `page-to-schedule`, пакет `ConfluenceSync`, скрипт `read_mpp.py` (только вызов).
- Живая AB `519492935` — только если Саша явно дал этот pageId / «на боевую».

### Решения брифа (закрыты)

| ID | Решение |
|---|---|
| Q1 гейт | Всегда дифф + «лей». Нет страницы — спросить. Страница-сессия. |
| Q2 макрос | REST, спайк подтверждён. |
| Q3 дочка | Имя спросить, черновик `<title родителя>. План <ДД.ММ.ГГ>`. План C: MPP → из MPP; иначе родитель с гантом → копия JSON; иначе пустой шаблон. |
| Q4/Q6 v1 | Только заливка MPP. Чат-патчи и каскад — этап 2. |
| Q5 / Q5a | Последовательность операций. MPP = полная замена JSON. Меток по задачам нет. |
| Q7 «Итого» | Патчить тело. Нет блока → вставить над макросом одну строку дат/N. Есть → заменить только даты и N. Строка «Трудозатраты» не создаётся и удаляется, если уже есть. Хвост 70% не выдумывать; если уже есть — не трогать. |

---

## 4. Место в экосистеме

- Класс: on-demand, **не** крон.
- Скилл: `productivity/edit-plan-confluence` (канон: `~/hermes-workspace/skills/productivity/edit-plan-confluence/SKILL.md`).
- Код v1: `scripts/` **внутри скилла** (конвертер, календарь, REST вложения/storage, «Итого»). Отдельный USERTOOLS-пакет **не заводить** (reuse-first): чтение MPP — существующий `~/USERTOOLS/MppReader/read_mpp.py`.
- Соседи:
  - `read-mpp` — скилл с этим именем **есть** в `~/hermes-workspace/skills/productivity/read-mpp/`. Другой выход (Google Sheets). Не вызывать его пайплайн GS. Файл `.mpp` в Telegram — как у него: **переименовать в `.zip`**.
  - `mpp-to-google-sheets` — второй скилл MPP→GS в том же каталоге workspace. **Не** переименовывать ссылки ТЗ на него: канон zip-входа для этого ТЗ — `read-mpp`. Не вызывать.
  - `tutu-confluence-jira` — паттерн `load_confluence_env` (bash-функция в `~/hermes-workspace/skills/productivity/tutu-confluence-jira/SKILL.md`, блок «Авторизация»; не Python-импорт). Из `~/USERTOOLS/ConfluenceSync/.env` — `CONFLUENCE_TOKEN` и при необходимости `WORKVAULT_PATH`. Не `source` всего `.env`.
  - `page-to-schedule` — план-график из **таблиц** страницы в GS, не плагин gantt. Не смешивать.
  - `deep-mine-project` — не потребитель этого скилла.
  - `confluence-gantt-plan` — **не канон v1**. Есть только как профильный каталог `~/.hermes/skills/productivity/confluence-gantt-plan/` (не workspace, не `profiles/default`, не симлинк). Триггеры пересекаются с этим ТЗ. Источник истины — это ТЗ, не SKILL.md спайка. Канон реализации — `edit-plan-confluence` в hermes-workspace; два скилла с теми же триггерами не оставлять.
- Приложение: Confluence Server/DC `https://dom.tutu.ru` (не `conf.tutu.ru`).

[NEW-ENTITY] новый скилл `edit-plan-confluence`. Согласован постановкой Саши на разработку скилла. Отдельный USERTOOL / новая сущность EntityRegistry — не предлагаются.

---

## 5. Архитектура прогона

Один прогон скилла (после резолва pageId и наличия `.mpp` или ветки «дочка без файла»):

1. Резолв цели: pageId из сообщения / сессии; иначе стоп и спросить. Для «создай дочку от <parent>» — parentId обязателен.
2. Прочитать страницу: storage + child/attachment. Есть ли макрос `gantt-chart-planner`.
3. Собрать новый JSON:
   - есть `.mpp` → конвертер MPP→JSON (+ календарь);
   - нет MPP, создание дочки, у родителя есть гант → копия JSON родителя;
   - нет источника → пустой шаблон (корень без детей, пустые deps/assignments).
4. Если макроса нет (или новая дочка) — сгенерировать новые uuid: `ac:macro-id`, параметры `id` и `hash`. Имя вложения = `gantt-chart-<macro-id>.json`. На **существующем** макросе `id`/`hash`/`macro-id` **не менять**.
5. Собрать строку «Итого» из MPP (даты и N корня; или из собранного JSON, если копия/пустой шаблон). `m_hours` можно считать внутри, в storage не выводить.
6. **Гейт:** показать дифф, ждать «лей» / «пиши». Без подтверждения — никаких POST/PUT.
7. Запись: вложение (POST `/data?conflictPolicy=override` или POST attachment, если первого нет) → PUT storage (макрос при установке; блок «Итого» всегда при заливке/создании). PUT страницы: re-read `version` сразу перед записью, в payload слать **current+1**. `conflictPolicy=override` на страницу не ставить (только на вложение).
8. Короткий отчёт: URL страницы, версия вложения, «Итого».

Каскад дат скилл **не считает**. Источник дат — MPP (или уже посчитанный JSON при копии).

---

## 6. Схема данных JSON вложения

Плагин: **Gantt Chart Planner for Confluence**, макрос `gantt-chart-planner`.

Storage макроса (не менять `id`/`hash` на живых копиях страниц — это идентификаторы экземпляра, не checksum содержимого):

```html
<p><ac:structured-macro ac:name="gantt-chart-planner" ac:schema-version="1" ac:macro-id="<uuid>">
<ac:parameter ac:name="id"><uuid-or-hex></ac:parameter>
<ac:parameter ac:name="hash"><uuid-or-hex></ac:parameter>
</ac:structured-macro></p>
```

Ключи верхнего уровня JSON: `eventsData`, `resourcesData`, `dependenciesData`, `assignmentsData`, `startDate`, `macroConfig`, `calendarsData`, `initialState`, `baselineVersions`, `customColumns`, `linkedSites`, `idCounter`.

| Ключ | Роль в v1 |
|---|---|
| `eventsData` | Массив из **одного** корня; дерево через `children`. Поля события: `id, parentIndex, startDate, endDate, duration, durationUnit, name, calendar, manuallyScheduled, unscheduled, ignoreResourceCalendar, constraintType, constraintDate, percentDone, effort, effortUnit, inactive, segments, baselines, parentId, rollup, children, effortDriven, schedulingMode`. `rollup: true` = сводная. Вехи: `duration=0`. |
| `resourcesData` | `{id, parentId, name, eventColor, resourceType:"custom"}`. Плагин плодит копии одного имени; активная группа = max id на имя. |
| `assignmentsData` | `{id, event, resource, units}`. `units` = % загрузки. |
| `dependenciesData` | `{id, from, to, type, lag, lagUnit, active}`. v1: только `type:2` (FS), `lag:0`. |
| `calendarsData` | Заменять из MPP при заливке файла. При копии с родителя — как в копии. |
| `startDate` | `YYYY-MM-DD` старта плана. |
| `idCounter` | Следующий свободный id = `max(все id событий/ресурсов/связей/назначений)+1`. **Не** хардкод `300000` из тестового скрипта. |
| `macroConfig`, `initialState`, `baselineVersions`, `customColumns`, `linkedSites` | Если на странице уже есть JSON — **сохранить как есть**. На новой странице — скопировать из шаблона (эталон тестового вложения v1). |

Идентификаторы: ключ страницы = **pageId**. Не считать уникальным ключом пару `id`+`hash` (у теста `519501810` и живой `519492935` они совпали из-за копирования страницы).

---

## 7. REST Confluence

База: `https://dom.tutu.ru`.  
`Authorization: Bearer $CONFLUENCE_TOKEN`.  
`X-Atlassian-Token: no-check` на запись.  
Токен: только через `load_confluence_env` из `~/USERTOOLS/ConfluenceSync/.env` (переменные `CONFLUENCE_TOKEN`, при необходимости `WORKVAULT_PATH`). Не `source` всего `.env`.

| Операция | Метод и путь |
|---|---|
| Список вложений | `GET /rest/api/content/{pageId}/child/attachment` |
| Скачать JSON | `GET /download/attachments/{pageId}/gantt-chart-<macro-id>.json?version=N&api=v2` или download из attachment API |
| Обновить вложение | `POST /rest/api/content/{pageId}/child/attachment/{attachId}/data?conflictPolicy=override` — multipart `file=@...json;type=application/json;filename=gantt-chart-<macro-id>.json`. **POST, не PUT** (PUT → 405). WADL: `updateData`. |
| Создать вложение | `POST /rest/api/content/{pageId}/child/attachment` multipart |
| Создать дочку | `POST /rest/api/content` JSON: `type=page`, `title`, `space.key` с родителя, `ancestors:[{id:parentId}]`, `body.storage` с макросом (и блоком «Итого») |
| Обновить тело | `PUT /rest/api/content/{pageId}`: `body.storage` + `version.number` = свежий GET `expand=version` **плюс 1**. Слать current as-is → HTTP 409 `Version must be incremented`. `conflictPolicy=override` на страницу не ставить. |

Спайк (доказано): родитель `519501810` → дочка `519502120`, space `~tkachenkoav` (от родителя), новые uuid макроса, вложение с планом 080926, плагин отрисовал тот же проект.

Не использовать `web_extract` / браузерный fetch на `dom.tutu.ru`.

---

## 8. MPP → JSON и календарь

Вход файла: путь к `.mpp` или к `.zip`, внутри которого `.mpp` (Telegram). JVM: `org.mpxj.*` (не `net.mpxj.*`), как в `read_mpp.py`.

```text
read_mpp.py <mpp> --format csv
  → __tasks.csv, __resources.csv, __assignments.csv
+ UniversalProjectReader.getDefaultCalendar() → calendarsData
```

### Задачи

- Строки с пустым `id` и `id=0` не брать в дерево (служебный корень MPP). Также отбрасывать узлы, у которых `outline_level` парсится как число **≤ 0** (служебная шапка MPP с настоящим id, напр. `id=217` / `outline_level=0`). Парс уровня безопасный: `int(float(raw))`; пустое/мусор → 0 → отброс. Корень дерева = первый узел с `outline_level >= 1`.
- `outline_level` (> 0) → вложенность `children`. `summary=True` → `rollup: true`.
- `duration` (дни) → `duration`. Вехи (`milestone` / duration 0) → `duration=0`, `effort=0`.
- `start` / `finish` → `startDate` / `endDate` (нормализовать до секунд, как в эталоне плагина).
- `parentId` / `parentIndex` проставить после сборки дерева.
- `percentDone` в v1: из MPP `percent_complete`, если колонка есть; иначе 0. Каскад % по родителям не считать.
- `schedulingMode`: `FixedDuration` (как в шаблоне плагина).

### Ресурсы и назначения

- Матч ресурса MPP → плагин **по точному `name`**.
- При полной заливке MPP на страницу, где уже был JSON: взять активную группу (max id на имя) как пул для матча; имена из MPP без матча — новый id, `resourceType: custom`. Старые неактивные копии имён (низкие id) **не включать** в новый `resourcesData` (как в успешном тесте 080926).
- `assignmentsData`: `event` = id события, `resource` = id плагина, `units` из MPP.
- `effort` листа = сумма `work` всех назначений этой задачи (часы). Сводные: не суммировать детей в `effort` корня для JSON (rollup рисует плагин).

### Связи

- Колонка `predecessors` (напр. `[2]`) → `{from: pred, to: task, type: 2, lag: 0, lagUnit: "day", active: true}`.
- Иные типы связей MPP в v1 не маппить (нет в приёмке). Если в файле не-FS — в диффе предупредить «пропущены связи не FS», не падать.

### Календарь (доказано Сашей «да супер»)

`calendarsData` — массив `{id, name, unspecifiedTimeIsWorking, intervals[]}`.

Нерабочие `intervals`:

- рекуррент: обед `at 12:00`–`at 13:00`; ночь по часам MPP (эталон 080926: `at 18:00`–`at 09:00`); `on Sat`–`on Sun`; `on Sun`–`on Mon`;
- исключения: `getCalendarExceptions()` где `working=False`; `startDate: YYYY-MM-DD 00:00`, `endDate: (toDate+1 день) 00:00`.

Часы MPP 09–13 / 14–18 → обед 12–13 и ночь 18–09 (как в `/tmp/build_calendar2.py`). Только `getDefaultCalendar()`. Календари ресурсов — не в v1.

### Пустой шаблон

Один корень (имя «Новый план» или title страницы), `duration=0`, без детей, пустые `dependenciesData`/`assignmentsData`, `calendarsData` — минимальный General (сб/вс + рабочие часы как в шаблоне теста) либо пустые intervals. В диффе явно: «план пустой».

### Копия с родителя

Скачать JSON вложения родителя, залить на дочку **как есть** (новые macro-id/id/hash у макроса дочки; содержимое JSON то же, кроме необходимости выставить согласованный `idCounter`). «Итого» пересчитать из этого JSON.

---

## 9. Блок «Итого»

Канон — **одна** жирная строка в storage (`<p><strong>…</strong></p>`):

```
Итого: с <ДД.ММ.ГГ> по <ДД.ММ.ГГ> - <N> рабочих дней
```

Строка `Трудозатраты: <M> человек-часа` **не создаётся** (ни `build_itogo_html`, ни `patch_itogo`, ни `apply_itogo`) и **удаляется из storage**, если уже есть. Разделитель дат и N — дефис с пробелами: ` - ` (не em-dash). Даты: `DD.MM.YY`. N: целое, пробел как разряд тысяч (`1 960`).

Переменная `m_hours` из `compute_itogo_from_csv` / `compute_itogo_from_gantt` **остаётся** в кортеже и в сигнатурах (`build_itogo_html(..., m_hours)`), в HTML блока «Итого» не подставляется. Текст гейта `gate_diff.py` («…N р.д., M ч-ч») — не storage, в пакет render-fix не входит.

Источник цифр (при заливке MPP):

| Поле | Откуда |
|---|---|
| дата1, дата2 | start / finish **корня плана** (первый узел outline_level≥1, не служебный id=0 и не шапка outline_level≤0) |
| N | `duration` корня в днях, округление **вверх до целого** (`ceil`) |
| M (`m_hours`, не в HTML) | сумма `work` (часы) по **всем строкам назначений** `__assignments.csv` (не суммировать summary-задачи — иначе двойной счёт), затем `ceil` |

При копии JSON / пустом шаблоне: даты и N с корня `eventsData`; M внутри = сумма `effort` листьев (`rollup=false`) или `0`, если assignments пусты — в storage не выводить.

Правила патча:

1. Блока «Итого: с …» нет → **вставить над макросом** одну строку шаблона. Если в storage уже есть «Трудозатраты: …» — вырезать (вместе с обёрткой `<p>…</p>`, не оставлять пустой абзац).
2. Строка «Итого: с …» есть → заменить только даты и N. Хвост (в т.ч. про 70%) **не менять и не создавать**. Строку «Трудозатраты» вырезать, если есть; новую не писать.
3. Не искать «Итого» на других страницах и не синхронизировать соседние абзацы.

---

## 10. Триггеры и ветки диалога

Триггеры: «поправь план», «обнови план на страничке», «помести план на страничку», «скорректируй план», «добавь задачу в план», плюс явные «создай страницу с планом» / «поставь гант на страницу».

| Вход | Поведение v1 |
|---|---|
| Триггер + `.mpp` / `.zip` + pageId или сессия | Сборка JSON, дифф, по «лей» — заливка + «Итого» |
| Триггер + файл, страницы нет | Спросить pageId (или родителя для дочки) |
| «Создай дочку от <parent>» | Спросить title (черновик `<title родителя>. План <ДД.ММ.ГГ>`), план по правилу C, дифф, «лей» |
| «Добавь задачу» без `.mpp` | Отказ: в v1 только заливка файла; поштучно — этап 2 |
| Триггер без файла на странице с макросом | Не патчить задачи. Спросить файл или подтвердить, что нужна только дочка/пустой макрос |

Сессия: запомнить последний подтверждённый pageId плана. Новая сессия — память пустая. Не подставлять живую AB по умолчанию.

---

## 11. Гейт записи

Показывать до любого POST/PUT:

- pageId, title, URL;
- операция: замена JSON / установка макроса / новая дочка;
- для дочки — черновик title;
- сводка плана: число задач, start–end корня, новые ресурсы (имена без матча);
- «Итого» было → стало;
- если на странице уже был план: **«план будет заменён целиком; правки не из этого MPP сгорят»**.

Ждать явное «лей» / «пиши» / «да». Иные реплики — не писать.

---

## 12. Страницы-ориентиры (тест)

| pageId | Назначение |
|---|---|
| `519501810` | Тестовая. Единственная страница, на которой проводились запись и спайк. Приёмка v1 — здесь, пока Саша не дал другой id. |
| `519502120` | Дочка спайка (макрос REST). Не эталон содержимого. |
| `519492935` | Живая «AB-платформа ТУТУ - Таймлайн и Стоимость доработок». Писать только по явному pageId/команде. |

Вложение теста: id `519501809` (имя `gantt-chart-<macro-id>.json`). Макрос теста: `ac:macro-id=25b9de75-cb34-4cc1-a17a-c314457308b2` (на новых страницах **не копировать**).

---

## 13. Риски

- Telegram не принимает `.mpp` — только `.zip` (как `read-mpp`).
- `conflictPolicy=override` затирает правки, сделанные в UI плагина.
- PUT вложения → 405; нужен POST `/data`.
- Версия страницы при PUT storage: re-read свежий `version` перед PUT, в payload слать **current+1**. Гонка между re-read и PUT → штатный 409 (чужая правка); повторный `apply` с новым re-read. `conflictPolicy=override` только на вложение, не на страницу. Слать current as-is → 409 `Version must be incremented` даже без гонки.
- Совпадающие `id`/`hash` у копии страниц — писать только по pageId.
- Тестовый конвертер: сломанный `idCounter=300000`; не переносить в прод-скрипт.
- Не-FS связи и ненулевой lag в MPP — молча пропуск с предупреждением в диффе.
- Сумма effort по всем задачам включая summary завысит `m_hours` в `compute_itogo_*` (гейт-дифф); канон расчёта M — сумма work назначений. В storage блока «Итого» M не выводится.
- Два шага записи (вложение + storage): если storage упал после JSON — гант новый, «Итого» старое. Повторить PUT storage; не откатывать вложение автоматически.
- Пустой шаблон: N=0, даты с `startDate` или одинаковые границы корня (`m_hours` внутри может быть 0; в HTML не попадает).
- Служебная шапка MPP с `outline_level≤0` и настоящим id (не 0) без фильтра попадает в `eventsData[0]` → плагин «No records to display». Фильтр в `build_event_tree` на `rows` (не только стек).

---

## 14. Шаги реализации

После «берём в работу» (hermes-feature). Кроны не ставить.
**Выполнено off-board 09.09 (HF:impl → HF:test):** скилл-канон v0.2.0 доведён, оффлайн/мок-тесты green (33 passed). См. TZ:docs-handoff ниже.

1. Скрипты скилла: конвертер MPP CSV→JSON (логика `/tmp/mpp_to_gantt.py` без битого idCounter) + календарь (`/tmp/build_calendar2.py`) + сборка «Итого». Юнит-тесты на CSV 080926 (число задач, FS, ресурс «Найм», ceil N; корень id=1).
2. REST: download/upload вложения на **тесте** `519501810`; не трогать `519492935`.
3. REST: дочка от тестового родителя + макрос + вложение + «Итого» над макросом (регресс спайка).
4. Патч «Итого»: нет блока / есть блок / есть хвост 70% (не трогать третью строку).
5. Скилл: триггеры, zip, `load_confluence_env`, сессия pageId, гейт, отказ «добавь задачу» без файла, предупреждение полной замены.
6. `restore-all-skills.sh` после появления скилла. Регистрация в EcosystemManifest — в том же HF-прогоне, без крон.
7. Приёмка с Сашей на тесте: заливка 080926, праздники календаря, «Итого» = даты корня + ceil(duration), рендер плагина. Строки «Трудозатраты» на странице нет.

---

## 15. Критерии успеха (проверяемые)

- На `519501810` после «лей» вложение бампает версию; плагин показывает дерево, FS-стрелки, ресурсы и календарные исключения из MPP.
- Даты задач на странице совпадают с MPP (не пересчитаны скиллом).
- Одна строка «Итого» над макросом (`Итого: с DD.MM.YY по DD.MM.YY - N рабочих дней`); N — целое вверх из duration корня; формат дат `DD.MM.YY`; строки «Трудозатраты» нет (если была — удалена); третьей строки про 70% скилл не добавил.
- Дочка от теста создаётся REST без UI; макрос с **новыми** uuid; план виден.
- Без «лей» запросов записи нет.
- Без pageId скилл спрашивает страницу, не пишет на `519492935`.
- `read_mpp.py`, `page-to-schedule`, ConfluenceSync-код не изменены.

---

## 16. Что НЕ трогать

- Любые pageId, кроме явно указанного / сессионного / созданной дочки.
- `~/USERTOOLS/MppReader/read_mpp.py` и скилл `read-mpp` (кроме того, что агент **вызывает** `read_mpp.py`).
- `page-to-schedule`, `pmo-charter-fill`, storage-патчи минуток/`ac:task`.
- Пакет ConfluenceSync (кроме чтения `.env` через `load_confluence_env`).
- `macroConfig.jiraFieldMappings` и Jira-интеграцию плагина.
- Кроны, Gateway, `contacts.enc`.
- `scripts/gate_diff.py`: строка гейта «Итого: … N р.д., M ч-ч» — текст диффа перед «лей», не storage страницы; пакет render-fix её не меняет.

---

## 17. Связи с существующими инструментами

| Инструмент | Связь |
|---|---|
| MppReader | Вызов `read_mpp.py` → CSV. Не менять инструмент. |
| ConfluenceSync | Только токен из `.env`. Не pull/push страницы этим ТЗ. |
| tutu-confluence-jira | Скопировать в скилл паттерн `load_confluence_env` из `~/hermes-workspace/skills/productivity/tutu-confluence-jira/SKILL.md` (самодостаточность скилла). Не вызывать section-patch минуток. |
| page-to-schedule | Нет общего пайплайна. |
| read-mpp | Тот же вход `.zip`; другой выход. Имя скилла на диске — `read-mpp` (не `mpp-to-google-sheets`). |
| mpp-to-google-sheets | Сосед MPP→GS. Не зависимость, не вызывать. |
| confluence-gantt-plan | Не канон. Профиль-локальный скилл вне workspace. Не развивать вместо `edit-plan-confluence`. |

---

## 18. Связи с инфраструктурой Hermes

- Профиль default. Скилл в `hermes-workspace/skills/productivity/`, синк `restore-all-skills.sh`.
- Java 17 + venv `~/hermes-agent/.venv` (`mpxj`, `jpype1`) — уже есть для MppReader.
- Кроны не создавать.
- ErrorBus в v1 не обязателен (интерактив, гейт Саши); ошибки — в чат.

---

## Контракты экосистемы

### Источник истины

- Владелец плана проекта: файл `.mpp` Саши (на время прогона заливки).
- Владелец отображения на странице после «лей»: JSON-вложение макроса + одна строка «Итого» в storage этой страницы Confluence.
- Владелец токена: `~/USERTOOLS/ConfluenceSync/.env` (`CONFLUENCE_TOKEN`).

### Входные контракты

| Поле | Тип | Обязательность | Источник (кто отдаёт) | Формат/enum |
|---|---|---|---|---|
| page_id | str | optional | чат / сессия скилла | числовой id страницы Confluence; нет → спросить |
| parent_id | str | optional | чат | parentId для POST дочки |
| mpp_path | str | optional | чат (файл) | путь `.mpp` или `.zip` с `.mpp` |
| CONFLUENCE_TOKEN | str | required | ConfluenceSync `.env` | Bearer PAT |
| tasks_csv | str | required | MppReader `read_mpp.py` | `{stem}__tasks.csv` |
| resources_csv | str | required | MppReader `read_mpp.py` | `{stem}__resources.csv` |
| assignments_csv | str | required | MppReader `read_mpp.py` | `{stem}__assignments.csv` |
| confirm | enum[лей, пиши, да] | required | Саша | без значения запись запрещена |

### Выходные контракты

| Поле | Тип | Потребитель (кто получает) | Формат/enum |
|---|---|---|---|
| gantt_json | str | api_confluence (вложение) | JSON ключей §6 |
| body.storage.value | str | api_confluence | XHTML: одна строка «Итого» (дат/N) + макрос; без «Трудозатраты» |
| page_id | str | Саша (URL), сессия скилла | id страницы после создания/правки |
| page_url | str | Саша | `https://dom.tutu.ru/pages/viewpage.action?pageId=` + id |
| attachment_version | int | Саша (дифф/отчёт) | версия вложения после POST |

### Зависимости

- Получает от: [MppReader (`read_mpp.py`), ConfluenceSync `.env`, api_confluence (`dom.tutu.ru`)]
- Отдаёт: [api_confluence (вложение + storage), Саша в чате (дифф, URL)]

### Breaking changes policy

- Внутреннего `schema_version` нет: схема JSON принадлежит плагину. Версия конвертера = версия ТЗ/скилла.
- Ломающее изменение маппинга MPP→JSON или шаблона «Итого»: бамп `version` ТЗ и скилла, обновить тесты на фикстуре 080926. Потребителей внутри экосистемы нет (кроме человека и плагина).

### Границы («что НЕ трогать»)

- Не менять контракт CSV `read_mpp.py` (`tasks`/`resources`/`assignments`).
- Не писать в Google Sheets (`read-mpp` / `page-to-schedule`).
- Не использовать PUT на `/child/attachment/{id}` без `/data`.
- Не менять `id`/`hash` существующего макроса при обновлении JSON.
- Не создавать третью строку «Итого» и не создавать/не оставлять строку «Трудозатраты» в storage.
- Не менять `scripts/gate_diff.py` в пакете render-fix (M в тексте гейта — не storage).
- PUT `/rest/api/content/{pageId}`: `version.number` = свежий GET + 1, не current as-is; не `conflictPolicy=override` на страницу.

---

## Открытые вопросы

Нет. Бриф закрыт 08.09.2026 (Q1–Q7, Q5a, формат «Итого»). Пакет render-fix (01.10.2026) уточняет Q7 до одной строки дат/N; строка «Трудозатраты» снимается. `gate_diff.py` («…N р.д., M ч-ч») в пакет не входит — не вопрос Саше.

---

## Этап 2 (не в v1)

Фиксируется, чтобы не потерять. **Не делать** в этом прогоне:

- Поштучные операции из исходной постановки + полный каскад как в MS Project (задача + зависимости по `dependenciesData` + `calendarsData` + rollup).
- Последовательность «чат поверх последнего MPP» без merge по полям (решение Q5a=1): чат патчит текущий JSON; следующий MPP снова полная замена с предупреждением.
- Расширения планировщика: SS/FF, lag, constraints.
- JSON→MPP.
- Генерация прозы про загрузку 70%.

---

## TZ:patch 2026-09-08 (факт-сверка)

Сверка master-ТЗ v0.1.0 с диском. Версия **не** бампилась (бамп — `TZ:finalize`). Код/скиллы/эталоны не менялись.

### Дельта (внесена в §4, §17)

1. **Коллизия скилла.** Канон v1 по брифу — новый `productivity/edit-plan-confluence` в `~/hermes-workspace/skills/…` (каталога ещё нет — ожидаемо до `HF:impl`). На диске уже есть `~/.hermes/skills/productivity/confluence-gantt-plan/` (реальный каталог, не workspace, не `profiles/default`) с пересекающимися триггерами («поправь план», «добавь задачу в план», …). `skill_manage` 08.09 уже вернул «already exists». ТЗ это не фиксировало — исправлено: не канон, не развивать вместо `edit-plan-confluence`, два скилла с теми же триггерами не оставлять.
2. **Имя `read-mpp`.** В workspace скилл `read-mpp` **существует** (`name: read-mpp`). Рядом — отдельный `mpp-to-google-sheets`. Ссылки ТЗ на `read-mpp` верны; добавлено «не путать / не вызывать» второй скилл.
3. **`load_confluence_env`.** Уточнён путь: bash-функция в `tutu-confluence-jira/SKILL.md` (блок «Авторизация»), читает `CONFLUENCE_TOKEN` и `WORKVAULT_PATH` из `~/USERTOOLS/ConfluenceSync/.env`. Соответствует §7; в §4/§17 добавлен точный путь.

### Не дельта (ТЗ не менять дальше)

- Скилла `edit-plan-confluence` в workspace нет — ожидаемо, создаётся на `HF:impl`.
- `read_mpp.py`, `ConfluenceSync/.env` (`CONFLUENCE_TOKEN` есть), `page-to-schedule`, эталоны `/tmp/mpp_to_gantt.py`, `/tmp/build_calendar2.py`, `/tmp/gantt_test.json`, `/tmp/gantt_newplan.json`, план `plans/HF-plan-20260908.md` — на месте.
- §6 ключи JSON = ключи `gantt_test.json` / `gantt_newplan.json`. Связи эталона: только `type:2`, `lag:0`. Ресурсы теста — копии имён, активные = max id (как §8).
- Календарь MPP: `/tmp/build_calendar2.py` = обед 12–13, ночь **18:00–09:00**, сб/вс, исключения `toDate+1` — как §8. В `gantt_test.json` ночь **17:00–08:00** — это календарь живого вложения-шаблона, не рецепт заливки MPP; пустой шаблон может брать часы шаблона теста, заливка MPP — часы из `build_calendar2.py`. Эталон не переписывать.
- `idCounter` в `gantt_test.json` = max used (354), в `gantt_newplan.json` = битый `300000`. Канон v1 остаётся §6: `max(все id)+1`, не копировать 300000.
- «Итого» в JSON-эталонах нет (это storage страницы). Тогда канон §9 — две строки; запрет третьей — без расхождения с эталонами. Канон v0.2.2 (§9) — одна строка дат/N, без «Трудозатраты».
- Этап 2 в v1-секциих не раскрывался.

---

## TZ:finalize 2026-09-08

Версия бампнута 0.1.0→0.2.0. ТЗ финализировано как текущее состояние (дельта `TZ:patch` включена). Открытых вопросов нет. Реализация не начата — ждёт «берём в работу» через `GATE:take-into-work`.

## TZ:docs-handoff 2026-09-09 (финальная реализация)

HF:docs-handoff (граф DEV EditPlanConfluence, SKILL-DEV, GLOSSARY §5.2 / hermes-feature Блок 4). Реализация скилла v1 завершена off-board в режиме «делай в 1 проход» (GATE:plan-approve auto-pass). Апдейт по факту реализации; контракты §6/§8/§9 не менялись — версия ТЗ/скилла без бампа (0.2.0).

### Состояние реализации
- Канон скилла: `~/hermes-workspace/skills/productivity/edit-plan-confluence/SKILL.md` **v0.2.0** (97 строк) — полный текст финализирован. Манифест этим фазом не трогался (только `ORCH:shared-state`).
- HF:impl (t_88768e1c): черновик скилла доведён до канона v1 по плану `TZ/EditPlanConfluence/plans/HF-plan_EditPlanConfluence_20260909.md`.
- HF:test (t_74af57e6): pytest `-m "not live"` — **33 passed / 1 deselected / 0 failed**. Все 9 обязательных сценариев §3.1 + мок REST §3.2 green. Live REST (T5–T6) не гонялся — требует явной команды Саши `EDITPLAN_LIVE=1`.

### Ключи §15 подтверждены (фикстура CSV 080926, мок REST)
- «Итого» = `28.09.26..18.05.27`, N=154, разделитель « - », третьей строки про 70% нет (хвост сохранён). M=2356 тогда считался (ceil work) и выводился второй строкой; канон v0.2.2 — в storage только строка дат/N, «Трудозатраты» нет.
- Вставка блока «Итого» — над макросом `gantt-chart-planner`; существующая строка дат/N заменяется, хвост сохраняется; строка «Трудозатраты» с v0.2.2 вырезается.
- Дерево: 33 события flat (без id=0), корень id=1, единый корень. Даты из MPP **не** пересчитаны (startDate JSON 2026-09-28, duration 154.0).
- Ресурсы: 16 вкл. «Найм»; deps=28, все FS (type=2, lag=0); assignments=27.
- `idCounter` = max(все id)+1 = 381, **не** 300000.
- Мок гейт: `apply` без «лей» → 0 write-вызовов; upload→put порядок; guard живой AB `519492935` → PermissionError.
- Соседи не изменены: `read_mpp.py`, `page-to-schedule`, ConfluenceSync.
- Коллизия `confluence-gantt-plan` погашена: `~/.hermes/skills/productivity/confluence-gantt-plan/SKILL.md` = 951-байт **DEPRECATED-редирект** на `edit-plan-confluence` (дублирующей логики нет).

### Не изменено этим фазом
- `EcosystemManifest.json`, `restore-all-skills.sh`, `.env`, `jobs.json` — только `ORCH:shared-state` (следующий шаг).
- Live-приёмка (T5–T6 §3.3) на тесте `519501810` — ждёт явной команды Саши `EDITPLAN_LIVE=1`.

### Осталось (следующие фазы графа)
- `ORCH:shared-state`: запись манифеста `tools["edit_plan_confluence"]`, digest/render, `restore-all-skills.sh` (симлинк скилла в профиль).
- `GATE:done`: preflight `pipeline_gate_done_preflight.py` + итог Саше.
- Live-приёмка с Сашей на тесте `519501810` (заливка 080926, праздники календаря, «Итого» = даты корня + ceil(duration), без строки «Трудозатраты»).

---

## TZ:patch 2026-10-01 — PUT storage `version+1` (HTTP 409)

Пакет `DEV/edit-plan-version-inc`. Баг скилла `productivity/edit-plan-confluence`, не USERTOOL. Источник: `_fix_plan_edit-plan-version_20261001` / `BUG:diagnose`. Версия ТЗ **не** бампится здесь (бамп — `TZ:finalize`). Код на этой фазе не меняется.

**I1.** `current`: `apply_plan` делает re-read страницы (`get_page(..., expand="version")`) и передаёт в `put_page` **текущий** `version.number` as-is. `ConfluenceClient.put_page` кладёт это число в payload без инкремента. Confluence REST на PUT требует **current+1**, иначе HTTP 409 `Version must be incremented. Current is: N`. Симптом двух подряд 409: вложение уходит с `conflictPolicy=override` (бампает версию вложения), PUT страницы падает, storage не сохраняется, повторный `apply` снова 409.  
`target`: re-read остаётся (optimistic lock); в `put_page` уходит `version + 1`. Клиент и вложение не рефакторятся. `conflictPolicy=override` на страницу не вводится.

Связь с соседями (reuse-first, без новых сущностей): ConfluenceSync `push` уже пишет PUT «с инкрементом version» — **не** импортировать его клиент (другой хост `conf.tutu.ru`, ТЗ запрещает менять пакет). Инкремент — на call-site в скилле (`pipeline.py`), сигнатура `put_page(..., version)` без изменения. MppReader / `read_mpp.py` к багу не относятся.

### Корневая причина (диск)

`scripts/pipeline.py` `apply_plan` (после upload вложения):

```python
fresh = client.get_page(page_id, expand="version")
version = int(fresh["version"]["number"])   # напр. 18
client.put_page(page_id, page["title"], storage, version)  # баг: 18, нужно 19
```

`scripts/conf_client.py` `put_page`: `"version": {"number": version}` — payload корректен; виноват переданный number. `scripts/gantt_attachment.py` `conflictPolicy=override` на вложение — оставить. `create_child_with_plan` идёт через POST create, не PUT — вне этого пакета.

Корпус §5 п.7 / §7 таблица «Обновить тело» / §13 риск версии / контракт «Границы» **этим патчем** приведены к `current+1` (историческая формулировка «с текущей version.number» была неверной относительно REST).

### Объём (факт, не команда skip)

Три файла кода+тестов, вне ядра канбана, без сущностей/cron/.env/манифеста: `scripts/pipeline.py`, `tests/test_pipeline.py`, `tests/test_rest_live.py`. SKILL.md / `conf_client.py` / `gantt_attachment.py` в этот пакет не входят (четвёртый файл — решение оркестратора, не этой карточки). Сужение LIGHT — оркестратор после `GATE:diagnose-review`.

### Что менять

1. `scripts/pipeline.py` — единственная runtime-строка: `client.put_page(..., version + 1)` вместо `version`. Re-read перед PUT сохранить.
2. `tests/test_pipeline.py`:
   - обновить `test_apply_plan_confirm_order_upload_then_put`: mock re-read `{"version": {"number": 5}}` → `assert ...call_args[0][3] == 6` (было `== 5`); порядок `upload` → `put` без изменений;
   - добавить `test_apply_plan_put_version_is_incremented`: вторая выборка `get_page` = `{"version": {"number": 18}}`, `list_attachments=[]`, `upload_gantt_json` мок → 1; `apply_plan(..., "лей")`; `assert ...call_args[0][3] == 19`.
3. `tests/test_rest_live.py`: `test_live_apply_plan_ok` под тем же гвардом `EDITPLAN_LIVE=1`, что существующий live-тест. Реальный `ConfluenceClient`, страница **только** `519501810`, `upload_gantt_json` мокать (не плодить вложения). Assert: вернулся `ApplyResult` с `page_url`, нет `ConfluenceError` 409. Не часть обязательного CI (`pytest -m "not live"` скипает).

### Что НЕ менять этим пакетом

- `scripts/conf_client.py` — сигнатура и тело `put_page`.
- `scripts/gantt_attachment.py` — `conflictPolicy=override` на вложение.
- SKILL.md — «PUT storage» достаточно; стратегия версии живёт в этом ТЗ.
- Живая AB `519492935`; live-запись только `519501810`.
- `read_mpp.py`, пакет ConfluenceSync, кроны, Gateway, манифест, `.env`.

### IAC (LIGHT: 1–3 строки; план = эта секция / `_fix_plan`)

| IAC | path | verify | depends | covers |
|---|---|---|---|---|
| **IAC-01** | `scripts/pipeline.py` (`put_page(..., version + 1)`) | `python3 -m pytest tests/test_pipeline.py -k "put_version or order_upload_then_put" -q` → оба passed | — | PUT несёт current+1 |
| **IAC-02** | `tests/test_pipeline.py` (регресс + обновлённый order-тест) | `python3 -m pytest tests/test_pipeline.py -q` → файл зелёный | IAC-01 | баг заперт; нет регресса оффлайн |
| **IAC-03** | `tests/test_rest_live.py` (`test_live_apply_plan_ok`) | при `EDITPLAN_LIVE=1`: `python3 -m pytest tests/test_rest_live.py -q` без 409; иначе skip | IAC-01 | боевой Confluence принимает инкремент |

Нет `depends: operator:` (класс S).

### Критерии приёмки (AC)

Только этот пакет. Наблюдаемое поведение / команда / артефакт. Класс S (поезд не ждёт Сашу).

### AC-001 — PUT несёт current+1

После `apply_plan` с подтверждением «лей» аргумент `version` у `put_page` равен свежему `get_page` `version.number` **плюс 1**, не as-is. Юнит: mock re-read 18 → PUT 19.

### AC-002 — регресс order-теста

`test_apply_plan_confirm_order_upload_then_put`: порядок вызовов `["upload", "put"]`; `put_page.call_args[0][3] == 6` при mock re-read `5`.

### AC-003 — оффлайн-файл зелёный

`python3 -m pytest tests/test_pipeline.py -q` в каталоге скилла: весь файл passed. Тесты `build_plan_*` и `live_ab_guard` без регресса.

### AC-004 — live-смоук существует и за гвардом

В `tests/test_rest_live.py` есть `test_live_apply_plan_ok` с тем же skip, что `test_live_get_test_page` (`EDITPLAN_LIVE != "1"`). Стационарный `pytest -m "not live"` его не гоняет. При `EDITPLAN_LIVE=1` полный `apply_plan` на `519501810` с моком upload возвращает `ApplyResult` с `page_url`, без HTTP 409.

### AC-005 — границы diff

Diff пакета не содержит `scripts/conf_client.py`, `scripts/gantt_attachment.py`, живую AB `519492935`, пакет ConfluenceSync, `read_mpp.py`. `conflictPolicy=override` остаётся только на вложение.

### Риски пакета

| Риск | Митигация |
|---|---|
| Гонка re-read→PUT → новый 409 | желаемо (optimistic lock); retry = повторный `apply` |
| Order-тест `==6` красный до фикса runtime | код и тест в одной итерации `HF:impl` |
| Live-тест мутирует `519501810` | только `EDITPLAN_LIVE=1`, вложение мокается |
| «Клиент виноват» → рефакторинг `conf_client` | не трогать: payload корректен |
| `conflictPolicy` на страницу | не использовать; только re-read+increment |

Открытых вопросов Саше нет.

---

## TZ:finalize 2026-10-01

Версия бампнута 0.2.0→0.2.1. Пакет `DEV/edit-plan-version-inc` (BUGFIX-LIGHT): PUT storage `version+1` (HTTP 409 `Version must be incremented`). Дельта `TZ:patch 2026-10-01` включена.

AC-001…005 пакета (класс S) уже записаны архитектором в секции `TZ:patch 2026-10-01`; показ в origin на `GATE:take-into-work` (auto-pass `ac-shown`).

`REV:tz` по кейсу BUGFIX-LIGHT (≤3 файла) не проводился — waived по канону (08.09.2026).

Открытых вопросов Саше нет. Реализация не начинается этой фазой — ждёт `GATE:take-into-work` → `HF:impl`.

---

## TZ:patch 2026-10-01 — render-fix (гант пуст + однострочное «Итого»)

Пакет `DEV/edit-plan-render-fix`. Баг скилла `productivity/edit-plan-confluence`, не USERTOOL. Источник: `_fix_plan_20261001.md` / `BUG:diagnose` (`t_0352f5a4`). Код на этой фазе не меняется. Версия корпуса **бампнута** 0.2.1→0.2.2 во frontmatter (этот `TZ:patch`); `TZ:finalize` пакета повторно не повышает, если frontmatter уже 0.2.2.

Два бага:

**I1 (критический).** `current`: `build_event_tree` отсекает только пустой `id` и `id=="0"`. Служебная шапка MPP с `outline_level=0` и настоящим id (воспроизведено: `id=217`) становится `eventsData[0]`; реальный корень `id=1` — ребёнок или вовсе выпадает из корня → плагин «No records to display».  
`target`: при сборке `rows` отбрасывать `outline_level`, который парсится как число ≤ 0 (`int(float(raw))`, пустое/мусор → 0). Корень = первый узел `outline_level >= 1`. Фильтр в одном месте (`rows`), не только в стеке: иначе шапка попадает в deps/`max_used`.

**I2.** `current`: блок «Итого» — две жирные строки, включая `Трудозатраты: M человек-часа`.  
`target`: в storage **только** `Итого: с DD.MM.YY по DD.MM.YY - N рабочих дней`. Строка «Трудозатраты» не создаётся и удаляется при `patch_itogo` / `apply_itogo`. `m_hours` остаётся в кортеже/сигнатурах, в HTML не подставляется.

Корпус §1 / §3 Q7 / §5 п.5 / §8 / §9 / §13 / §15 / контракты **этим патчем** приведены к однострочному «Итого» и фильтру `outline_level≤0`. История секций `TZ:patch`/`TZ:finalize`/`TZ:docs-handoff` до 01.10 не удалялась; в снимках 08–09.09 добавлена пометка канона v0.2.2.

Связь с соседями: MppReader / `read_mpp.py` / ConfluenceSync не менять. `gate_diff.py` (строка «…N р.д., M ч-ч») — текст гейта, не storage; в этот пакет не входит.

### Объём (факт, не команда skip)

Четыре файла кода+тестов, вне shared, без сущностей/cron/.env/манифеста: `scripts/mpp_convert.py`, `scripts/itogo.py`, `tests/test_mpp_convert.py`, `tests/test_itogo.py`. По GLOSSARY §2 **не** укладывается в BUGFIX-LIGHT (≤3 файла). Сужение LIGHT — оркестратор после `GATE:diagnose-review`, не этой карточки. SKILL.md / `references/mpp-to-gantt.md` — `HF:docs-handoff`, не impl.

### Что менять (impl, не эта фаза)

1. `scripts/mpp_convert.py` `build_event_tree`: фильтр `rows` = непустой `id`, `id != "0"`, `outline_level` > 0. Сигнатуру не менять. `ValueError` при отсутствии корня оставить.
2. `tests/test_mpp_convert.py`: синтетическая шапка `id=217` / `outline_level=0` (без нового файла фикстуры) → корень id=1, `count_tasks==33`, 217 нет в дереве и в deps. Желательно кейс «шапка не первая».
3. `scripts/itogo.py`: `build_itogo_html` — одна строка дат/N; хелпер выреза «Трудозатраты» (обёртка `<p>…</p>`, варианты «человек-часа/часов», NBSP); `patch_itogo` / `apply_itogo` вырезают старую line2, не пишут новую; патч line1 не зависит от наличия line2.
4. `tests/test_itogo.py`: убрать ожидание «Трудозатраты: 2 356…»; assert отсутствия строки; патч вырезает; вставка без line2; кейс «только Трудозатраты без line1».

### Что НЕ менять этим пакетом

- `scripts/gate_diff.py`, `scripts/pipeline.py`, `scripts/child_page.py`, `scripts/cli.py` (сигнатура `build_itogo_html(..., m_hours)` сохранена).
- `~/USERTOOLS/MppReader/read_mpp.py`, скилл `read-mpp`, пакет ConfluenceSync.
- Живая AB `519492935`; live REST.
- Новая фикстура CSV на диске.

### IAC (план = `_fix_plan_20261001.md` / эта секция)

| IAC | path | verify | depends | covers |
|---|---|---|---|---|
| **IAC-01** | `scripts/mpp_convert.py` (`build_event_tree` filter) | `python3 -m pytest tests/test_mpp_convert.py -q` → passed; в т.ч. тест шапки id=217 | — | корень id=1, 33 задачи, нет 217 в дереве/deps |
| **IAC-02** | `scripts/itogo.py` | `python3 -m pytest tests/test_itogo.py -q` → passed | — | HTML без Трудозатрат; патч вырезает старую строку |
| **IAC-03** | оба + регресс | в каталоге скилла `python3 -m pytest -m "not live" -q` → passed | IAC-01, IAC-02 | нет регресса оффлайн |

Нет `depends: operator:` (класс S). Live Confluence / `EDITPLAN_LIVE` в пакет не входят.

### Критерии приёмки (AC)

Только этот пакет. Наблюдаемое поведение / артефакт. Класс S (поезд не ждёт Сашу).

### AC-001 — корень дерева не шапка

После конвертации CSV с служебной строкой `outline_level=0` и id≠0 `eventsData[0]["id"] == 1`, `count_tasks == 33`, id шапки нет в дереве и в `dependenciesData`. Фикстура 080926 (шапка `id=0`) без регресса.

### AC-002 — одна строка «Итого» в HTML

`build_itogo_html` содержит `Итого: с 28.09.26 по 18.05.27 - 154 рабочих дней` и не содержит `Трудозатраты`.

### AC-003 — патч вырезает «Трудозатраты»

`apply_itogo` / `patch_itogo` на storage с двумя строками: даты/N обновлены, «Трудозатраты» нет, хвост 70% на месте. На storage без line1, но с Трудозатратами: line1 вставлена, Трудозатраты нет.

### AC-004 — оффлайн зелёный

`python3 -m pytest -m "not live" -q` в каталоге скилла: passed.

### AC-005 — границы diff

Diff пакета не содержит `read_mpp.py`, пакет ConfluenceSync, `scripts/gate_diff.py`, живую AB `519492935`. `conflictPolicy=override` на страницу не вводится.

### Риски пакета

| Риск | Митигация |
|---|---|
| Не все MPP дают шапку outline_level=0 | фильтр идемпотентен |
| Шапка не первая в CSV | тот же фильтр; тест «шапка не первая» |
| Нет узлов outline_level≥1 | существующий `ValueError`, шапку не подставлять |
| `outline_level` пустой / `0.0` / нечисло | `int(float)` / мусор → 0 → отброс |
| Предшественник/назначение на id шапки | нет в `flat` → skip |
| Вариации «человеко-часов» / NBSP / без `<strong>` | расширить вырез; минимум — канон `<p><strong>Трудозатраты: N человек-часа</strong></p>` |
| `m_hours` unused в HTML | оставить аргумент, не каскадить call-site |
| 4 файла > LIGHT | факт в диагнозе; граф не укорачивать с этой карточки |

Открытых вопросов Саше нет. Реализация не начинается этой фазой — ждёт `TZ:finalize` → `GATE:take-into-work` → impl.

---

## TZ:finalize 2026-10-01 — render-fix

Версия корпуса **не** бампится повторно: frontmatter уже **0.2.2** с `TZ:patch 2026-10-01 — render-fix`. Пакет `DEV/edit-plan-render-fix`: (1) фильтр `outline_level≤0` в `build_event_tree` — служебная шапка MPP с настоящим id не становится `eventsData[0]`; (2) блок «Итого» в storage — одна строка `Итого: с DD.MM.YY по DD.MM.YY - N рабочих дней`, строка «Трудозатраты» не создаётся и удаляется. Дельта патча включена.

Чеклист качества (Шаг 4 `tz-workflow`):

- [x] Цель одним предложением (§1)
- [x] Входы и выходы явны (раздел «Контракты экосистемы»)
- [x] Шаги impl атомарны (секция патча «Что менять», 4 файла)
- [x] Критерии успеха проверяемы (§15 + AC-001…005 пакета)
- [x] «Что НЕ трогать» заполнено (§16 + пакет)
- [x] Связи с экосистемой (§17 / §18)
- [x] Контракты по стандарту (в т.ч. storage без «Трудозатраты»)
- [x] Открытые вопросы закрыты
- [x] I1 / I2 `current` / `target` в секции патча
- [x] AC только пакета, класс S, нет `depends: operator:`

AC-001…005 (класс S) уже в секции `TZ:patch 2026-10-01 — render-fix`; показ в origin на `GATE:take-into-work` (auto-pass `ac-shown`). Operator-hold нет.

Объём 4 файла кода+тестов — по GLOSSARY §2 **не** BUGFIX-LIGHT; табличный skip `REV:tz` OFF при ≤3 файлах **не** применяется. `flag-waived: Sasha` эта фаза не ставит. Состав хвоста графа — оркестратор.

Соседи без изменений пакета (reuse-first, без новых сущностей): MppReader / `read_mpp.py` / ConfluenceSync / `scripts/gate_diff.py`.

Открытых вопросов Саше нет. Реализация не начинается этой фазой — ждёт `GATE:take-into-work` и хвост графа.
