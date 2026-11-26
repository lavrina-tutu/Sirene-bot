# Лабораторные proof-прогоны роли-исполнителя

Класс: лаб-исполнение proof/матрицы (B2, ErrorBus E-02/04/07, B3-01…09) через `codex exec` на роль-исполнитель (lab-исполнитель gpt-6.1-terra) — широкую многопробовую программу в один инвок НЕ отдавать.

## Симптом

Исполнитель загружает закреплённую среду и pinned-версию (Python 3.14.x / OpenAI 2.x), считает hashes/pinned, пишет manifest — и завершается, не запустив ни одного managed worker/collector/probe. Итог: `NOT_PROVEN`, все пробы `NOT_RUN`. Проявилось на трёх независимых proof-прогонах (B2-матрица, ErrorBus E-02/04/07, B3-01…09) при отдаче широкой программы одним инвоком.

## Verstehen

`NOT_RUN`/preflight-статус — НЕ дефект ядра/кандидата и НЕ `FAIL` продукта; это незавершённая подготовка (setup-неполнота). Независимый счётчик не измерен — запись `NOT_MEASURED` не равна доказанному нулю. Перезапуск того же широкого промпта даёт тот же исход и жжёт токены.

## Правило — узкий шаг на инвок

1. Разбить обязательную программу на УЗКИЕ шаги: ОДНА обязательная проба на инвок, промпт с явным заголовком «ШАГ B3-NN» и oracle/FAIL-таблицей именно этой пробы. Не параллелить пробы одного стенда в одном промпте, если у каждой свой worker/collector lifecycle.
2. Каждый шаг требовать явный `reuse` существующего managed harness кандидата: fixtures `pipeline/tests/kanban_fixtures.py` (w1_04_board, w1_05_config/cli-stub, w1_05_effect_worker, RunBoundary, w1_06_claim) — доказаны 129 прошедшими тестами `pytest delivery/Registries/pipeline/tests -q`. НЕ формулировать «построй свой harness с нуля»: открытая установка сама оседает на preflight.
3. Если и узкий шаг вернул preflight — это установленный факт: классифицировать по SETUP_FAIL (неисправный стенд) / именованному FAIL совместимости (доказанное отсутствие capability на pinned-версии) / NOT_PROVEN, и остановиться, а не дробить дальше. `SETUP_FAIL` ≠ product FAIL и не даёт доказанного `send=0`.

## Evidence на пробу

pinned interpreter/packages/loaded module hashes и candidate/core identities, точная команда, board/task/run/claim/admission/ordinal, фактический OS rc и native events до/после, состояние task и accepted chain, независимый counter на принимающей границе (НЕ из adapter self-report; отсутствие файла не ноль), source/notification ack. Автоперезапуск проверять и по runs/dispatch trace, не только по отсутствию второго send.

## Изоляция

bwrap `--unshare-all --die-with-parent --ro-bind / /`, отдельный /tmp (tmpfs), env -i, скрыть production .hermes, PID/network namespaces, PYTHONDONTWRITEBYTECODE=1, `--dev-bind /dev/urandom` (Python rc1 без него). Пишется только в lab root; ядро, кандидат, production, Gateway, платные вызовы, реальный Telegram, cron, смена модели/effort/окна — вне допуска.
