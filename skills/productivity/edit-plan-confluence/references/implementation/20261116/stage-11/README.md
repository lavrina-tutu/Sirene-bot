# Этап 11: доказательное сравнение и доверие

Норматив: согласованный план §13 и master §20 (AC-23, AC-24, AC-25, AC-27).
Финальный gate и реальные команды/rc: `stage-report.json`, `stage-report.md`,
`reports/external-checks.json`, `reports/junit.xml`, `reports/mofs-junit.xml`.
SHA завершающего коммита записывается после commit в журнал канонического плана.

Изменения ограничены внутренними query/selectors/history/render MofsIndex,
существующим CLI и адаптерами edit-plan-confluence, тестовым контуром стадии 11
и инструкциями workvault-rag. Схема, writer, миграции и конфиги не менялись.
Прежние stages 01–10 и их evidence сохранены.

Селекторы — точные snapshot/publication ID с проверкой проекта до diff.
Публикации проверяются по странице, attachment, исходному snapshot и качеству
связи. Gantt/MPP требуют подтверждённого mapping; одна связь публикации с MPP
не доказывает позиционные Gantt ID. Без identity возвращаются структурные
несопоставленные сущности. Подтверждённые концы зависимостей нормализуются;
локальные endpoint ID/UID в provenance не создают ложных замен связей после
перенумерации. Мультимножество сохраняет параллельные записи и все семантические
поля (тип, signed lag, units, elapsed, calendar basis, прочие сохранённые свойства).
Задачи, календари, ресурсы, назначения и вложенные данные сравниваются полностью.
Неизвестная timezone не даёт абсолютного сдвига; полнота не выводится из timezone.

Publication verify блокирует изменяющие HTTP-методы на уровне транспорта,
проверяет ожидаемые bytes и storage, точную версию и текущую актуальность
отдельно. Новые scoped observations добавляются в существующий MofsIndex;
исторические trust/status/published_at не меняются. Повтор не увеличивает
версию вложения. Текущее совпадение не восстанавливает прежнюю дату публикации.
Нет достаточных свидетельств или найден mismatch — not_verified/5.

`reports/stage11-compare-cli.json` содержит фактические CLI-вызовы и результаты
всех десяти подслучаев AC-24. `reports/stage11-live.json` — GET-only перепроверка
выделенной страницы этапа 10 по его неизменным bytes/storage: историческая версия
совпадает, current attachment намеренно уже изменён прежним тестом. Это
синтетический Gantt-контур, не доказательство расписания произвольного MPP.
`reports/stage11-loopback.json` — два настоящих CLI-процесса над HTTP-fixture.
Ни одна из этих проверок не выполняет POST/PUT. Live-регрессии прежних стадий
пишут только на собственные выделенные тестовые страницы и учитываются отдельно.

## Воспроизводимый комплект MofsIndex

`usertools/MofsIndex/manifest.json` содержит абсолютные target paths,
before/after SHA-256, тип изменения и режим каждого из шести файлов.
`before/` — исходные версии; новый selectors.py до этапа отсутствовал.
`after/` — полные конечные версии, `changes.patch` — unified patch.
Runtime использует USERTOOLS/MofsIndex; импортировать Python из evidence запрещено.

Оба способа восстановления проверены в независимых временных деревьях:

```bash
cp -a usertools/MofsIndex/before/. /absolute/temporary/MofsIndex/
patch --batch -p1 -d /absolute/temporary/MofsIndex -i /absolute/path/changes.patch
# Альтернативное отдельное дерево:
cp -a usertools/MofsIndex/after/. /absolute/temporary/MofsIndex-after/
```

Сверка hashes и режимов с manifest и рабочими файлами —
`reports/restore-checks.json`; реальный stdout patch сохранён отдельно.
Не копировать тестовые БД/cache в production. Этап не меняет рабочую БД.

Этапы 12/13, доставка в активную библиотеку, полная приёмка §20 и старого §19,
проверка расписания и ownCloud sync здесь не объявляются завершёнными.
canon.md сохранён побайтно относительно входа и исключён из поставки.

## Браузерный runtime приёмки

Новый изолированный T сначала не содержал Playwright: первый полный прогон
получил 597 passed / 1 failed (ModuleNotFoundError до записи контрольных планов).
Этот отказ сохранён в `failed-browser-runtime/reports/`. Исправление окружения
не меняло исходники и глобальные пакеты: переиспользованы зависимости прежней
принятой стадии 10. Реальная команда подготовки:

```bash
cp -a --reflink=auto \
  /home/tkachenkoav/.cache/edit-plan-confluence-acceptance/stage10-20261116T193250/stage-10/browser-deps \
  /home/tkachenkoav/.cache/edit-plan-confluence-acceptance/stage10-20261116T193250/stage-10/browsers \
  /home/tkachenkoav/.cache/edit-plan-confluence-acceptance/20261117T045241Z/stage-11/
```

Playwright 1.60.0, greenlet 3.2.5, Chromium 148.0.7778.96; фактический launch/close
в этом T прошёл. Версии и происхождение — `reports/browser-runtime.json`.
На другом чистом хосте нужны эти тестовые зависимости; runtime/venv/browser
binaries не входят в git-комплект. Существующий live-тест сам подхватывает
`T/stage-11/browser-deps` и `T/stage-11/browsers`. Финальный прогон использует
`PYTHONPATH=/home/tkachenkoav/.local/lib/python3.9/site-packages` и
`EDITPLAN_LIVE=1`; полная команда записана pytest-hook в отчёт.
