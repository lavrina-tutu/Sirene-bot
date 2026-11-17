# MppReader — чтение/запись MS Project из Hermes

## Что установлено на VM (AlmaLinux 9.7)

- `java-17-openjdk-headless` (через `sudo dnf install -y java-17-openjdk-headless`)
- В venv `/home/tkachenkoav/hermes-agent/.venv`:
  - `mpxj==16.4.0`
  - `jpype1==1.7.1`

## Файлы

- `read_mpp.py` — чтение .mpp/.mpx/.xml/.xer через mpxj. Печатает JSON,
  сохраняет CSV рядом с файлом.
- `push_to_gs.py` — .mpp CSV → новый GS (export 16 колонок) + форматирование + права.
- `gantt_csv_to_gs.py` — Gantt CSV → новый GS.
- `roadmap_gs_to_gs.py` — GS/CSV-роадмап → новый GS (гибрид 10 колонок).
- `quarter_labels.py` — парсер квартальных меток роадмапа.
- `mpp_to_gs_xlsx.py` — .mpp → xlsx (без Google).
- `read_write_mpp_com.py` — заготовка для Windows (MS Project + pywin32).
  Поддерживает read/mark/rename. Запускается на машине с MS Project.
- `tests/` — pytest, без live Google (`pytest -m "not live"`).

## Быстрая проверка

```bash
source /home/tkachenkoav/hermes-agent/.venv/bin/activate
python3 /home/tkachenkoav/USERTOOLS/MppReader/read_mpp.py /tmp/test_project.xml --summary
python3 /home/tkachenkoav/USERTOOLS/MppReader/roadmap_gs_to_gs.py --from-csv \
  /home/tkachenkoav/USERTOOLS/MppReader/tests/fixtures/roadmap_sample.csv --dry-run
cd /home/tkachenkoav/USERTOOLS/MppReader && python3 -m pytest -m "not live"
```

Три входа в GS (каждый — **новый** документ, права writer на
`tkachenkoav@tutu.ru` и `i.alex.tkachenko@gmail.com`, **не** anyone):

```bash
# 1. .mpp
python3 push_to_gs.py <stem> --dir /tmp --title "…"

# 2. Gantt CSV
python3 gantt_csv_to_gs.py /path/gantt-chart-export.csv --title "…"

# 3. Роадмап GS
python3 roadmap_gs_to_gs.py "https://docs.google.com/spreadsheets/d/<ID>/edit" --title "…"
```

OAuth: `~/.hermes/google_token.json` (не `profiles/anthropic`).
ТЗ: `~/WorkVault/Hermes-Backlog/TZ/MppReader/MppReader_TZ.md`.

## Ограничения

- mpxj читает .mpp всех версий, но **не записывает** обратно в .mpp.
  Для записи .mpp — путь через Windows + MS Project COM.
- На больших проектах (>5000 задач) первый запуск долгий из-за старта JVM
  (~2–4 c). Если будет частый вызов — стоит сделать долгоживущий
  daemon-процесс (см. roadmap ниже).

## Roadmap (если потребуется)

1. Долгоживущий FastAPI-сервис на VM: один старт JVM, эндпоинт `POST /read`.
2. Windows-агент: simple Flask-app или scheduled task, опрашивает SMB-папку
   `IN/`, читает/правит .mpp через COM, кладёт результат в `OUT/`. VM
   общается с ним по HTTP/SSH.
3. Двусторонняя синхронизация: Sirene делает правку в Project через COM,
   возвращает diff пользователю.

## Полный экспорт для edit-plan-confluence (§20)

`plan_export.export_full(path)` — versioned `full-export-v2`, один вызов общего
`read_project_file`/MPXJ reader. CLI скилла выбирает проверенный Python/JVM через
`env.select_mpxj_python`: текущий `/usr/bin/python3.9`,
`PYTHONPATH=/home/tkachenkoav/.local/lib/python3.9/site-packages`, MPXJ 16.4.0 /
JPype 1.7.1. CLI — `/usr/bin/python3`, exporter subprocess — выбранный MPXJ Python.
Список выше про старый hermes-venv относится к прежней установке; наличие JVM
проверяется запуском, не наличием бинарника.

Экспорт сохраняет ID/UID/WBS/иерархию/summary/milestone, dates/durations/constraints,
actuals/splits/baseline (слоты 0–10), FS/SS/FF/SF с signed lag/units/elapsed,
ресурсы/назначения/units/work/timephased, интервалы и исключения календарей,
наследование/коэффициенты и bindings проекта/задач/ресурсов. Поля хранят
value/quality/reason, численные quantities — десятичные значения и units;
missing/unsupported не заменяют нулём, ошибки getter снижают качество.
Timezone unknown сохраняется. Completeness извлечения не доказывает расписание.

`PreparedPlan` нормализует результат в существующем скилле; календарь, «Итого»,
архив и Gantt используют те же данные без CSV и повторного reader.
Старые `read_mpp.py`/CSV/Google Sheets потребители сохраняют свои контракты;
legacy `convert` не заменяет новый admission. Scheduler capability matrix
`references/scheduler-capability-matrix.md` ограничивает локальную модель,
а не возможности Confluence-плагина; полного schedule replay не обещает.

Публичные команды, лимиты и recovery:
`~/hermes-workspace/skills/productivity/edit-plan-confluence/references/cli-contract.md`,
`operations-and-recovery.md`, `export-contract.md`.
Новых CLI, reader daemon, конфигов и расписаний этот контракт не вводит.
