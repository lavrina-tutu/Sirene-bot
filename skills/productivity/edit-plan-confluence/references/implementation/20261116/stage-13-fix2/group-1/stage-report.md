# Г1 — архив до Confluence

44 passed, rc=0. tests/test_publish_prepare.py: client/server/profile outage после verified snapshot, resume с удалённым исходником сохраняет snapshot и не вызывает reader; неразрешённый slug и binding conflict архив не получают. tests/test_plan_save.py: точный round-trip actual_start/finish/duration/work/stop/resume, quality/missing/units в snapshot и plan_task_version. Исходный snapshot/read-back теперь до создания ConfluenceClient и GET; сохранённая preparation позволяет resume после отказа GET. POST/PUT при отказе 0. JUnit и log в reports/.
