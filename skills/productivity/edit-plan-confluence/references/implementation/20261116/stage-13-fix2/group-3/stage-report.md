# Г3 — точные исходные факты в пользовательских колонках

42 unit passed, 1 live passed, rc=0. Test ID: test_source_values_live.py::test_visible_source_values_and_reopen. Страница 537575108 — новый тестовый ребёнок 519501810. Штатный upload → точные bytes read-back → обычный view → модель и persistableData → видимый текст каждой колонки → закрытие/повторное открытие. 274 проверок. Observation и screenshots: live/source-values/.

Все семь строк, включая summary, сохраняют точные customtext percent/actual_start/actual_finish/duration/work/stop/resume и явно подписанное состояние исходных фактов. На листовых задачах native percent 0/21/47/76/100/21.125 и производные статусы совпали; исходный summary 47.375 сохраняется текстом, native summary пересчитан в 44.1875. Эти значения не смешиваются. View и edit-дескрипторы открыты; живое наблюдение выполнено в обычном read-only просмотре. Полноценное сохранение через редактор не заявлено: сериализуемые значения проверены через persistableData и штатный повторный load. Wrapper SHA-256 9a43a94647ce8c2fff5cabdb07a52b8619b824bf8673b0bcafe9a090cd9dccb2.

Это доказательство отображения и сохранности; календарная семантика actuals не доказана, fail-closed не снят. Первая ошибка тестового selector (field/id) и ошибка возврата объекта UI-scroll сохранены как история, текущий live-тест прошёл. Запасная таблица не потребовалась.
