# Группа 2 — итерация 2: граница нулевого назначения

При дополнительной проверке обнаружено: прежняя ветка zero_work_unassigned_milestone могла скрыть явно заданный, но отсутствующий resource UID, если work и duration нулевые. Новый граничный тест до исправления реально упал; JUnit/log сохранены.

Преобразование теперь требует resource_key:null и resource_uid:{value:null, quality:missing, reason:not_set}. Заданный неизвестный UID не считается отсутствием ресурса и даёт assignment_partial. Проверены обе формы отсутствующего lookup: resource_key:null при UID99999 и external:resource:uid:99999. Исходные данные не меняются.

После исправления 43 representation/calendar/converter/profile теста passed, rc=0. Команда: /usr/bin/python3.9 -m pytest tests/test_corrective_representation.py tests/test_mpp_calendar.py tests/test_mpp_convert.py tests/test_plugin_profile.py --test-root T/representation-boundary-after; PYTHONPATH=/home/tkachenkoav/.local/lib/python3.9/site-packages.

Test ID: test_corrective_representation.py::test_zero_work_unassigned_milestone_never_hides_a_declared_missing_resource. Прежний отчёт группы 2 и первый полный прогон сохранены. Общий gate §20 остаётся failed из-за actuals и других ещё не представленных возможностей D.
