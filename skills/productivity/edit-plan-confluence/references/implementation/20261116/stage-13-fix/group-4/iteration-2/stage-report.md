# Группа 4 — итерация 2: долговечные источники batch

Первый полный повтор дал четыре FileNotFoundError: test_real_batch_cli_native_copies считывал E/F/D-risks из исчезнувшего transport cache origin. Закреплённые бинарные копии уже существовали в tests/fixtures/real/ и были проверены другими приёмочными сценариями.

Тест теперь берёт байты из versioned fixture path, проверяет прежние точные SHA-256/размер и создаёт копии в T/Inbox. Исходный origin сохранён в provenance; transport cache не восстанавливался и production не изменялась. Никакой JSON-подмены бинарного экспорта нет.

Реальная команда /usr/bin/python3.9 -m pytest tests/test_plan_batch.py -k test_real_batch_cli_native_copies --test-root T/batch-source-fix; PYTHONPATH=/home/tkachenkoav/.local/lib/python3.9/site-packages. Все четыре режима mpp/manifest/inbox/named-risks прошли (4 passed, rc=0), включая холодный read, повтор, archive read-back и populated baseline.

Матрица дополнена новым отрицательным граничным тестом группы 2, итерации 2: 756 обязательных тестов (717 regression + 39 acceptance). Старые test IDs и критерии A–D/gate сохранены. Первый failed-прогон сохраняется в группе 5/history. Второй полный прогон запускается с EDITPLAN_LIVE=1, чтобы обязательный REST тест выполнялся. Этот параметр окружения не разрешает обращения к production страницам: прежние guards действуют.
