# Группа 4 — бинарные приёмочные сценарии

Gate подготовки fixtures: **passed**. Это не PASS §20.

Добавлена отдельная документированная пара binary-identity-positive/anchor.mpp и revised.mpp. Рецепт меняет бинарный источник: содержательный корень UID1000/ID1, FixedDuration, без work/actuals/назначений, четыре FS связи, у revised FS lag +1d. Все изменения seed и hashes документированы в manifest. Проверены побайтовая воспроизводимость рецепта и реальный MPXJ экспорт; подмены очищенным JSON нет. Адресное тестовое правило исключает конкретную UID2 связь только для точного revised source hash; причина — явное тестовое исключение, evidence не относится к production.

Две положительные live-цепочки public CLI (diff и publish): needs_decision/3 → identity confirmed/0 → resume published_with_warnings/0, published:true; исходный snapshot один, MPXJ-read cold=1/resume=0, POST=PUT=1. Повтор resume: unchanged/0, MPXJ-read=POST=PUT=0, версия страницы без роста. Ограничение schedule:not_verified сохранено.

relations-all-types.mpp оставлен отрицательным. Обе live-цепочки: failed/5 → успешный identity confirm/0 → resume failed/5, published:false, external_effect:none, POST=PUT=0; snapshot прежний, resume MPXJ-read=0.

Команды: /usr/bin/python3.9 -m pytest tests/test_corrective_binary_fixtures.py --test-root T/group-4-fixtures (2 passed, rc=0); /usr/bin/python3.9 -m pytest tests/acceptance/test_live_publication.py -k binary_identity --test-root T/group-4-live (4 passed, rc=0). PYTHONPATH=/home/tkachenkoav/.local/lib/python3.9/site-packages. Первые ошибки тестового import/stdout parsing сохранены в JUnit. Все CLI команды/rc/измерения/receipts — evidence/.

Обновлены synthetic fixture manifest и ac-matrix.json: 755 тестов, все прежние 722 сохранены, добавлены 33 проверки и отрицательные подслучаи AC-04/09. Числа A–D и полные критерии gate не менялись. pipeline.py/cli.py не менялись. Production, Gateway, расписания не менялись.
