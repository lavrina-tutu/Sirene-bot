# Г5 — календарная семантика и остаточные ограничения

34 unit/identity/rule passed; один адресный live probe passed как отрицательный контроль, rc=0. test_fix2_schedule_boundaries.py и test_plan_rules.py; отдельные результаты identity/resume и JUnit — unit-reports/.

Нативный кандидат actualStartDate/actualEndDate/actualDuration/actualEffort/stopDate/resumeDate/stop/resume не имеет соответствующих определений поля в модели установленной обёртки. Входные bytes прочитаны браузером, wrapper/engine hashes проверены. Observation остаётся not_verified для scheduling: live/actuals-stop-resume/observation.json. Универсальная невозможность не утверждается. Все 367 actuals/stop/resume блокеров сохранены, fix_proof:null; customtext отображение не снимает их.

D: все четыре blocking assignment_partial UID441/699/700/701 уже присутствовали в ledger цикла1; дополнительно UID441 start/finish независимы. UID441: назначение 30.03.2026 09:00–09:00, задача UID373 до 22.04.2026 18:00. UID699/700/701 work56/16/56 h без resource UID. Ресурс не выдумывался, работы/связи не удалялись. Всего отсутствующих endpoints больше: узкие прежние исключения служебных/zero-work milestone не объявляются новыми блокерами. Точные исходные строки — source-boundary-audit.json.

B/C: исходная связь UID510→UID323 FS/0 DAYS PREDECESSOR сохранена и точно представлена. Наличие корректной связи не доказывает необходимость её удаления или not_needed относительно исторической календарной причины. Точная активная revision и проверенная текущая причина отсутствуют; historical-unresolved-v1 inactive. Никаких новых подтверждений от имени владельца не создавалось.

В предварительном прогоне: 7 failures/14 passed. Исправлены неверная тестовая предпосылка «все назначения без ресурса блокируются» и лишнее повышение POLICY_VERSION из Г4: матрица допуска не менялась, policy остаётся publication-admission-v1; подтверждённые адресные тестовые правила снова совместимы. После исправления новый расширенный прогон34 passed. История сохранена в initial-regression-failures/. Глобальных разрешений не введено.

Корневой blocker-ledger.json содержит 375 остающихся причин (367 actuals +6 D +2 B/C), все fix_proof:null, конкретные source_field/normalized_source/representation/layer/test_id. Это аудит исходных нормализованных данных цикла1; новый полный CLI-прогон и его фактические результаты — Г6.
