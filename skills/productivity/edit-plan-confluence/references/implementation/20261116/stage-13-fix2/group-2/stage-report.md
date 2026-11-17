# Г2 — колонки и процент

36 passed, rc=0; reports/junit.xml. status, percentdone, startdate, enddate, duration открыты в view и edit. Prepared percentDone сохраняет 0/21/47/76/100/21.125; status не записывается (setter теряет точность). Legacy CSV также перестал округлять до int. Converter v4 инвалидирует старые представления, parse cache не изменён. Golden обновлён только по видимости колонок, SHA manifest пересчитан; исходный ожидаемый mismatch сохранён. Живое доказательство точных исходных значений, actual finish и summary — группа 3; capabilities здесь не повышались.
