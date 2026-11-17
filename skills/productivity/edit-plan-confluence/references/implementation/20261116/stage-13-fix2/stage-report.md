# Корректирующий цикл 2 — §20 EditPlanConfluence

**§20: failed.** Полный окончательный прогон: **799 passed / 4 failed / 0 skipped**, rc=1; 803 обязательных теста, отсутствующих test ID нет. Упали только `acceptance/test_live_publication.py::test_real_publish_repeat_and_observed_dates[A..D]`. AC: {'passed': 23, 'failed': 4}; кейсы: {'failed': 4, 'passed': 4}; сценарии: {'failed': 1, 'passed': 10}. Успех с ограничениями не присваивается.

## Изменения и доказательства по группам

| Группа | Что сделано и доказано | Отчёт / commit |
|---|---|---|
| Г0 | Master 0.5.2, план и inventory: независимый архив; факты/отображение/расписание; процент, неизвестность и противоречия; замена при неизменной идентичности. Нормативные SHA/числа/кейсы/gate сохранены дословно | group-0/stage-report.md; `976aadc` |
| Г1 | Snapshot/read-back до создания клиента и GET; клиент/server/profile outage сохраняет архив; resume после отказа GET без исходника и нового snapshot; точный round-trip 6 полей. 44 passed | group-1/stage-report.md; `7c27b3b` |
| Г2 | Открыты status/percentdone/startdate/enddate/duration в view/edit; исходный percentDone без setter статуса. 0/21/47/76/100/21.125; 36 passed | group-2/stage-report.md; `ba165f9` |
| Г3 | Customtext для исходного процента, actual start/finish/duration/work/stop/resume и проверки фактов. Model/persistableData, обычный просмотр, видимый текст, второе открытие и summary. 42 unit + 1 live passed | group-3/stage-report.md; `65d77d4` |
| Г4 | Профиль связывает конкретное поле/метод с wrapper SHA и проверками; display не разрешает schedule. source_values и schedule раздельны в receipt/schema/verify. 191 проверка, дополнительно 38 binding/profile и 1 live passed | group-4/stage-report.md; `82c9bac` |
| Г5 | Новая адресная проверка native actuals/stop/resume отрицательна; календарное доказательство отсутствует. D и B/C разобраны адресно. 34 unit/identity/rule + 1 negative live passed. Лишнее повышение policy исправлено: конечная матрица publication-admission-v1 | group-5/stage-report.md; `b574a01` |
| Г6 | Дополнительный тест полной замены, проверенный живьём наблюдатель A–D, +45 обязательных ID без удаления старых; полный прогон и отдельные R/M, 14 восстановлений patch/after-copy; честный failed | group-6/stage-report.md; текущий завершающий commit, SHA — в журнале плана |

Подробные test ID и команды — JUnit/машинные отчёты каждой группы. Новые ключевые проверки: `test_source_values_live.py::test_visible_source_values_and_reopen`, `::test_real_plan_observer_reads_visible_values`; `test_publish_replacement.py::test_full_replacement_retains_macro_and_repeat_versions`; `test_plugin_profile.py::test_separate_field_capability_rejects_unbound_proof`; `test_fix2_schedule_boundaries.py`.

## Что видно и что это подтверждает

На контрольных тестовых страницах видны штатный статус, процент, плановые даты/длительность и отдельные подписанные исходные факты. Исходный процент сохраняется точной строкой; native круговой renderer округляет число. В контроле source summary **47.375** сохранился текстом, native summary стал **44.1875**. Эти значения не смешиваются. Actual finish берётся из источника, никогда из endDate; отсутствие — «не задано». Неизвестный/противоречивый исходник получает «требует проверки»; неактивность не означает завершение.

Свежие observations, browser-received bytes, GET storage и screenshots: `final/capability-controls/source-values/`, `real-plan-observer/`. Проверены обычный read-only просмотр, сериализуемые значения и повторное открытие. View/edit descriptors проверены отдельно; полное сохранение через UI редактора не заявляется. Положительный контроль не заменяет наблюдение самих A–D.

Профиль **1.2.1**, converter **prepared-gantt-v5**. Confluence 8.9.4, engine 5.4.1, frontend H6u7SQymvwxeyojc1ur6Z. Engine SHA `4e57cf0dcdcc4f9c855d59d8f600e3682a12dadd91725426fedb096581433cfe`; wrapper SHA `9a43a94647ce8c2fff5cabdb07a52b8619b824bf8673b0bcafe9a090cd9dccb2` проверены по фактическим ответам браузера.

## A–D: фактический последний публичный CLI

| Кейс | Архив / display_task_count / связи | Work, ч | POST / PUT операции | Blockers | Даты / успешный повтор |
|---|---:|---:|---:|---:|---|
| A | 58 / 57 / 53 | 1576 | 0 / 0 | 27 | не наблюдались / не выполнен |
| B | 62 / 61 / 60 | 2096 | 0 / 0 | 28 | не наблюдались / не выполнен |
| C | 62 / 61 / 61 | 2088 | 0 / 0 | 103 | не наблюдались / не выполнен |
| D | 72 / 71 / 76 | 3136 | 0 / 0 | 217 | не наблюдались / не выполнен |

Все четыре — failed/5, archive:verified, page version 1→1. Display count является метрикой подготовленного представления; на этих страницах план не опубликован. Создание пустых тестовых страниц учитывается отдельно от POST/PUT публикационных операций.

Полные исходные документы структурно равны источникам цикла 1; MPP SHA совпадают; bytes нормализованного архива равны SQL; все шесть полей, качество и единицы точно совпали в каждой строке plan_task_version. Все исходные коллекции complete. Свежий аудит: `final/blocker-audit/archive-audit.json`, source/representation/admission-evidence в lossless gzip.

## Незакрытые контракты

Остаются **375 source/rule диагностик**: 367 actuals/stop/resume, 6 назначений/интервалов D и 2 B/C. Каждая содержит source_field, normalized_source, representation, layer, test_id, evidence и **fix_proof:null** в [blocker-ledger.json](blocker-ledger.json). Точное текстовое отображение не доказывает календарное влияние. Проверенный native-кандидат не имеет соответствующих определений полей в модели; универсальная невозможность других преобразований не утверждается. Закрепления дат и подмены actuals процентом нет.

D: blocking назначения без resource UID441/699/700/701 и независимый интервал назначения UID441 уже были в ledger цикла 1. UID441 относится к задаче UID373: назначение заканчивается 30.03.2026 09:00, задача — 22.04.2026 18:00. Другие отсутствующие endpoints с прежними узкими zero-work/service эквивалентностями не переименовываются в эти четыре блокера.

B/C: UID510→UID323 FS/0 DAYS PREDECESSOR сохранена в представлении. Точная текущая причина удаления и применимая активная revision не получены; historical-unresolved-v1 inactive. Правильная передача связи сама по себе не доказывает not_needed для старой календарной причины. Production read-only probe также не обнаружил таблицу новых правил; миграция не запускалась.

## Полнота прогона и сохранность

Конечная команда и окружение — `group-6/final-command.json`; исходный T: `/home/tkachenkoav/.cache/edit-plan-confluence-acceptance/accept-fix2-20261117-145510/verified-repeat`. [JUnit](final/reports/junit.xml), [машинная приёмка](final/reports/acceptance-report.json.gz), [читаемая приёмка](final/reports/acceptance-report.md). Все первоначальные AC, кейсы, scenarios, failure matrix и подслучаи сохранены: `group-6/matrix-preservation.json`. Все 208 тестируемых источников стабильны, missing_required=[]; три прежних CSV сохраняют свои проверенные CRLF bytes и неизменные LF Git blobs через существующий clean filter (group-6/existing-git-filter-fixtures.json); 14 комплектов восстановлены, 38 текущих USERTOOLS hashes совпали. R: **81 passed + 1 optional legacy §19 skip**, M: **206 passed**, rc=0 в разных последовательных процессах.

**Production preservation gate не прошёл:** хэш `168a1f7cc8283521ddeb76b9401e8a758d3aa48e81d88d69849b1115402073c8` → `b2ea4b6cfce4e343f5d855dc19cf29d3e9b5ff512c42eddd79df916a8be445fb` за время последнего прогона. Это единственный изменившийся файл из 3512 защищённых; ответственный writer и построчные изменения не установлены. Все наши специальные production-аудиты использовали URI mode=ro. Состав plan-таблиц прежний, plan_project_rule отсутствует; это не доказывает неизменность строк. Никакого отката БД или воздействия на фоновые процессы не выполнялось. Отдельное ограничение — `group-6/production-db-change-audit.json`.

Canon hash совпадает: `a6e841a660f60f2aee932edbd558992c68fc560de4464a580ffbb1a8e0b17892`; файл не включается в коммиты. На входе он был clean, заявленного M не было; искусственный M не создавался. Параллельные правки вне этого пакета сохранены. Gateway, кроны, наблюдатели и расписания не менялись; записи — только выделенные дочерние страницы 519501810, production A/B/C/D/AB исключены. OwnCloud sync и production docs indexing не заявляются.

Первая полная попытка: 799/4, но initial-state/external-checks не были подготовлены исполнителем; её дополнительные report gates остались непроверенными. История сохранена в `history/first-full-missing-preflight/`. Последний прогон имеет свежую внешнюю регрессию, исходную сверку и восстановление; отчёты не переписаны ради passed. Большие JSON/log/JS сохранены gzip с проверенными original/stored SHA и codec в [delivery-manifest.json](delivery-manifest.json); raw файлы остаются в T. Декомпрессия восстанавливает исходные bytes.

Критерии §20 не выполнены: нет успешной публикации, дат и повтора A–D; дополнительно не подтверждена полная неизменность production DB. Итерация зафиксирована, passed с ограничениями не присвоен.
