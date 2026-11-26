# Lab-исполнитель: срез на префлайт и compressor-зависимость W1-09

## Срез больших lab-инвоков на префлайт

Lab-исполнитель (gpt-6.1-terra, codex exec) на большом объёмном инвоке стабильно
срезает задачу на префлайт-подготовке: все пробы NOT_RUN, harness/реализация не
собраны, только source-audit/preflight и hashes. Наблюдалось повторно в B2, ErrorBus
и B3 при попытке слать одним инвоком полную матрицу или целый proof.

Правило: НЕ слать одной задачей всю матрицу / весь proof / весь компонент. Резать на
узкие ОБЯЗАТЕЛЬНЫЕ шаги — по одной пробе / одному компоненту на инвок, каждый с
завершённым evidence (hashes, exact команды, счётчики, события). Следующий шаг
продолжает с точки останова предыдущего, повторно используя уже готовые harness и
fixtures кандидата (переиспользуй, не строй с нуля).

## Compressor-фаза блокирована W1-09

В кандидате compressor-фаза (TZ:compress/HF:compress) блокирована реальной
зависимостью W1-09: `invoke_once` на role=compressor до транспорта возвращает
`local-error: compressor transport: W1-09 dependency`, 0 HTTP-запросов/CLI-запусков.
B3 proof на compressor-ветви NOT_PROVEN до реализации W1-09 (полный Compressor
invoke + OS isolation, файлы invoke_role.py/pipeline_extract.py/pipeline_context.py/
test_kanban_compressor.py). Порядок «B3 proof → W1-09» для compressor-ветви некорректен:
сначала W1-09, затем B3 proof.

## ErrorBus-кодовые доработки не срезать в диагностику

ErrorBus: исполнители стабильно добавляют матрицу «oracle → факт → статус» и
изолированные пробы, но код (per-event guard/снятие общего witness-mutex, штатная
регистрация tick-observer, source-discovery, E-04 ключи, commit-fault протокол,
независимый reader) не доводят за один инвок. Итог остаётся NOT_PROVEN/FAIL. Реакция
фактов и notebook-
мониторится как не-закрытые.
