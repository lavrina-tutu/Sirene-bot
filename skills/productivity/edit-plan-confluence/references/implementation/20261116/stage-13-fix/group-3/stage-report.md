# Группа 3 — допуск и правила

Gate: **failed** по обязательному восстановлению пригодных правил B/C; исправленный контракт классификации проверен.

completeness классифицирует причины по исходным полям; повтор quality_issues добавляет только точные provenance paths. Неизвестная причина/недоказанный origin/несовпадение counts и неполнота перечисления блокируют. partial допускается с предупреждениями только при полном record_count/error_count и полном совпадении перечисленных исходных причин с агрегатом; каждое исходное partial и provenance остаются в архиве. Глобальных разрешений collections.dependencies/assignments.*/quality_issues нет. Raw discarded self/dangling классифицируются адресно как graph, а отсутствие audit блокирует. Независимые semantic losses остаются после identity.

Таргетированные unit/regression: 73 passed, rc=0 (group-3-unit-final.xml); первоначальные 12 отказов и их JUnit сохранены. Причина первоначальных лишних отказов — точные зеркала известного отсутствия not_set; они теперь проверяются по оригиналу, не порождая диагностику.

Через read-only URI и typed query восстановлены B snapshot_63235566e13645a08825b6b27a458e49 (60 связей) и C snapshot_f34e96cb8e164bab9dd210ee1f4362f1 (61), проверены исходные MPP hashes; устойчивые ключи и точные старые metadata — bc-existing/. Production не мигрировалась и не записывалась. В ней нет plan_project_rule; пригодная точная revision/адресное согласование исключения не восстановлены. Общая норма master о наличии исторического согласования не определяет отсутствующий адрес и revision. Новые consent/revision не выдумывались. Профиль сохраняет inactive/historical-unresolved-v1 и проверяемый recovery manifest, plan_rules возвращает эту provenance без активации.

Команда: PYTHONPATH=/home/tkachenkoav/.local/lib/python3.9/site-packages /usr/bin/python3.9 -m pytest tests/test_corrective_completeness.py tests/test_admission.py tests/test_plan_rules.py --test-root T/group-3-unit. Финальная повторная проверка изменений recovery входит в группу 5. MofsIndex/production/Gateway/расписания не менялись. §20: финальная приёмка failed; исправления обязательны.
