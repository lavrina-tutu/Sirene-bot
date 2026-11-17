# Группа 2 — итерация 3: инвалидация представления

После граничного исправления отсутствующего resource UID (c18614e) версия конвертера повышена с prepared-gantt-v2 до prepared-gantt-v3. RepresentationCache использует явную версию, профиль, правила и шаблон; хеша реализации в ключе нет. Повышение исключает повторное использование представления, построенного до защитного исправления. ParseCache и исходные snapshots сохраняют независимые ключи.

Команда: PYTHONPATH=/home/tkachenkoav/.local/lib/python3.9/site-packages /usr/bin/python3.9 -m pytest -c S/tests/pytest.ini S/tests/test_plan_cache.py S/tests/test_corrective_representation.py --test-root T/cache-revision --junitxml=T/group-5/cache-revision.xml -q. Результат: 20 passed, rc=0; существующий test_independent_cache_keys проверяет miss при изменении converter_version и отсутствие повторного чтения MPP.

Второй полный прогон прерван SIGINT только процесса pytest до изменения исходников: 441 passed, rc=2, 201.17s. Артефакты сохранены в T/repeat-stage13-v2/final. Новый полный прогон использует отдельный чистый корень. Эта итерация не закрывает неподдержанные actuals и общий gate.
