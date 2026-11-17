---
name: edit-plan-confluence
description: "MPP/ZIP → архив или план Confluence: залей/обнови план на странице, сохрани только в архив, сохрани MPP из Inbox, покажи историю или сравни версии плана."
version: "0.5.0"
platforms: [linux]
tools: [terminal, read_file, write_file]
metadata:
  hermes:
    tags: [confluence, gantt, plan, mpp, ms-project, gantt-chart-planner]
    related_skills: [tutu-confluence-jira, workvault-rag, read-mpp]
---

# MPP → архив / Confluence

Единственный канон обоих имён `edit-plan-confluence` и `confluence-gantt-plan`.
Публичный вход — `/usr/bin/python3` и
`/home/tkachenkoav/hermes-workspace/skills/productivity/edit-plan-confluence/scripts/cli.py`.
Глобальные `--db`, `--workvault`, `--cache-dir`, `--allow-live-ab` стоят **до** подкоманды.
Флаги, примеры и коды — [cli-contract.md](references/cli-contract.md).

## Выбор сценария

| Запрос пользователя | Действие CLI |
|---|---|
| «Залей этот MPP на страницу», «обнови план» | `publish --mpp FILE --page-id PAGE --project-slug SLUG` |
| «Сохрани только в архив» | `save --mpp FILE --project-slug SLUG` |
| «Сохрани все MPP из этой папки Inbox» | `batch save --inbox FOLDER --project-slug SLUG --batch-id ID` |
| «Что не загрузилось?» | `batch show --batch-id ID --view errors` |
| «Покажи хронологию планов» | `history --project-slug SLUG --view files` |
| «Какие файлы загрузили сегодня?» | `history --view files --time-field received` с project и локальным периодом |
| «Сравни X и Y» | `compare --project-slug SLUG --from snapshot:ID --to snapshot:ID` либо точные `publication:ID` |
| «Какая версия опубликована?» | `history --view publications`; последняя подтверждённая версия отдельно от текущего наблюдения |
| «Продолжи после сбоя» | `operation show`, затем `resume --operation-id ID`; для пакета — `batch resume` |

Файл использовать по доставленному абсолютному пути. CLI сам фиксирует байты;
новая привязка создаётся внутри `publish --project-slug`. При существующем
однозначном binding slug можно опустить. Проект выбирать из `Registries/entities.json`;
отсутствующий/неоднозначный проект или цель требуют адресного уточнения.
`pfs.page_id` — минутки, а не страница плана. Не угадывать страницу по этому полю.

Команда «залей» с однозначными файлом и целью разрешает обычный `publish`.
Повторное общее «да» не требуется. `diff` архивирует пригодный источник и
возвращает operation/snapshot ID; GET цели допустим, POST/PUT отсутствуют.
Подготовленную операцию можно продолжить через `resume`.
`save` и batch работают локально без Confluence token/клиента, публикаций и сдвига baseline.
Совместимый `save --page-id` задаёт только локальную привязку.

## Адресные решения

После `needs_decision / 3` читать `operation show --operation-id ID` и сообщать
конкретную причину/последствия. Снимок исходного MPP уже сохранён, если
`verification.archive:verified`; блокировка публикации его не отменяет.

- Идентичность: `identity confirm` с точной парой snapshot, явным свидетельством
  пользователя и mode `continuity` либо `mapping`; затем отдельный
  `resume --operation-id ID --mapping-revision REVISION`.
- Неизвестная timezone: `resume --operation-id ID --timezone-hint Europe/Moscow`
  после указания пользователем и до внешнего эффекта. Новая подготовка сохраняет
  прежнюю; старые решения и mapping автоматически не переносятся.
- Преобразование смысла: `resume --operation-id ID --accept-proposal PROPOSAL
  --rule-scope once --reason "Основание пользователя"`. Scope `project` требует
  явного согласия на правило проекта. B/C меняют только производное представление.
- Batch-item: `resume --accept-proposal` регистрирует решение размещения и
  оставляет item в `needs_decision`. Обработку запускает отдельный
  `batch resume --batch-id ID --retry-decisions`.

Точные команды, evidence и пределы — [identity-and-rules.md](references/identity-and-rules.md)
и [batch-and-inbox.md](references/batch-and-inbox.md). UID/имя/lineage не доказывают
идентичность между MPP. Не удалять связи автоматически ради совпадения срока.
`--drop-dep` формирует адресное предложение для проверки и согласования.

## История и достоверность

Актуальный план — архивный файл с наибольшим mtime, зафиксированным при чтении.
`history` возвращает `result.current_plan` (snapshot, mtime; равенство разных
snapshot = ambiguous, старые записи без mtime = unknown). Порядок поступления
и дата внутри MPP актуальность не определяют. Выбранный файл архивируется и
публикуется как есть: историческое правило B/C не применяется по решению
владельца; назначения с `resource_uid: missing` сохраняются без выдуманного
ресурса и видны текстом на задачах вместе с исходными интервалами и работой.
План показан как снимок сохранённых дат без пересчёта плагином; исходный режим
планирования MPP виден отдельной колонкой. Противоречивая веха с duration=0 и
разными start/finish блокируется отдельно: менять исходные даты нельзя.
При вопросе об истории использовать `compare` двух точных snapshot:
`result.task_history.added/removed` содержит задачи и все их связи. Это дифф
локальных записей; без mapping нельзя утверждать идентичность переименованной
задачи между независимыми MPP.

Для «сегодня» вычислять две локальные полуночи в зоне пользователя (для Саши
Europe/Moscow), передавать ISO timestamps с UTC offset и полуинтервалом
`[since, until)`. День определяется на момент запроса; таймзона задач MPP от
этого не устанавливается. [history-and-verification.md](references/history-and-verification.md)
содержит вычисление, cursor и различия времён.

«Какая версия опубликована»: назвать page/attachment/version/publication ID,
trust и время подтверждения последней подтверждённой версии. Текущая цель может
уже отличаться. Для свежей проверки выбранной записи —
`publication verify --project-slug SLUG --publication-id ID --scope current_state`
(только GET, добавляет локальное наблюдение). Без свежего наблюдения говорить
«последняя известная регистрация на момент …». Historical scope не заменяет
current scope; нынешнее совпадение не доказывает старую дату. Наличие публикаций
определять typed API по связям snapshot, а не по nullable дате.

История/compare — typed API MofsIndex через CLI либо `workvault-rag`.
Один «v2» требует выбора страницы/вложения и точного ID; произвольный ID не выбирать.
Архив, байты/страница и расписание имеют независимые статусы:
`schedule:not_verified` не становится verified после успешного POST/PUT.
Публикация идёт по плановым датам: «по плану; факт — в колонках». Точный процент,
фактические начало/конец/длительность/работа и stop/resume видны отдельными колонками;
их участие в пересчёте timeline не заявляется.
В ответе кратко дать результат, IDs, архив/публикацию/расписание и следующий шаг;
полный экспорт и диагностика — по ссылкам квитанции.

## Несколько входов и эксплуатация

Основной сценарий — отдельная папка `WorkVault/Inbox/<имя-пакета>/` и одно
текстовое сообщение «сохрани все MPP из … в архив проекта …».
Freeze-all предшествует разбору, обработка последовательная. Исходники остаются
на месте. Отклонённое Gateway сообщение скилл не получает и исправить не может;
готовую папку обрабатывать по отдельной текстовой команде.

Сохранены `preview`, `diff`, `convert`, `archive-history`, `apply --confirm` и
дочерняя ветка `diff/apply --child`. `convert` — legacy CSV-адаптер; штатные
save/publish используют [prepared-data](references/mpp-to-gantt.md).
Для AB нужен явный page ID и `--allow-live-ab` при каждом resume.

Авторизация — `scripts/env.py` через штатные `usertools_config`/`usertools_env`.
ConfluenceSync в режиме `unified_only`: process env и центральный secret store,
локальный `.env` не требуется. Не source-ить `.env`, не печатать token/Authorization.
Timeout/size/retry, источники настроек, backup и восстановление —
[operations-and-recovery.md](references/operations-and-recovery.md).
Gateway/загрузчик не менять и не перезапускать; cron/наблюдатели не создавать.

Приёмка и границы stage-12 — [testing-and-acceptance.md](references/testing-and-acceptance.md).
Кейсы A–G, hashes и отличие D-risks — [cases-trisigma.md](references/cases-trisigma.md).
