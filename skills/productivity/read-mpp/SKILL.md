---
name: read-mpp
description: "прочитай mpp: конвертация плана в Google Sheets"
version: "1.1.0"
platforms: [linux, macos, windows]
tools: [terminal, read_file, write_file]
metadata:
  hermes:
    tags: [mpp, ms-project, files, planning, roadmap]
---

# Read MPP — чтение Microsoft Project файлов

## Триггер
Запускается по фразам:
- «прочитай файл mpp», «прочитай файл .mpp <путь>»
- «открой .mpp», «открой mpp»
- «read mpp», «parse mpp», «разбери mpp»
- «залей в gs», «конвертируй mpp», «пришли xlsx из mpp»
- «конвертируй csv в gs», «залей gantt csv», «gantt-chart-export в gs»
- «план из роадмапа», «план MS Project в GS из роадмапа», «сделай план MS Project в GS из роадмапа»

## ⚠️ Не вызывать для deep-mine-project
Бурение проекта (`deep-mine-project`) нуждается в CSV/`plan.md` в overlay, **не** в Google Sheets.
Для шага C вызывай напрямую `read_mpp.py --format csv` / `--format both`. Этот скилл для deep-mine **не** грузить.

## ⚠️ Важно: .mpp не принимается напрямую
Hermes блокирует файлы .mpp. Пользователь должен **переименовать файл в `.zip`** перед отправкой.
Если пользователь говорит что не может отправить .mpp — сразу напомни: *«Переименуй файл в `.zip` и пришли»*.

## Что есть на машине

- **Java**: OpenJDK 17 (`/usr/bin/java`) — установлено через `dnf install java-17-openjdk-headless`.
- **Python пакеты**: `mpxj==16.4.x`, `jpype1` — есть в системном `/usr/bin/python3`. ⚠️ venv `~/hermes-agent/.venv` может НЕ иметь mpxj (`ModuleNotFoundError: No module named 'mpxj'`) — тогда запускать скрипт через `/usr/bin/python3` (в нём стоят mpxj+jpype), а не искать пакет по venv'ам.
- **Скрипт**: `/home/tkachenkoav/USERTOOLS/MppReader/read_mpp.py`.

### Питфолл: Log4j-предупреждение в stdout ломает JSON
`read_mpp.py --format json > file` печатает `main ERROR Log4j API could not find a logging provider.` в **stdout** (не stderr), поэтому строка попадает в начало файла и `json.load()` падает с `Extra data: line 1 column 5`. Фикс: перед `json.load` срезать первую строку — `tail -n +2 file > clean.json`

Поддерживаются форматы: **.mpp** (Project 98–2019/365), **.mpx**, **.xml/MSPDI**,
**.xer** (Primavera), **.pp** (ProjectLibre), и др. — всё, что умеет mpxj.

## Шаги

### 1. Извлечь путь к файлу из запроса
- Если пользователь дал путь явно — используй его.
- Если нет — спроси («какой файл прочитать?»). Если файл уже приложен в
  диалог, сохрани его во временную папку (`/tmp/`) и используй её путь.

### 2. Запусти скрипт
```bash
source /home/tkachenkoav/hermes-agent/.venv/bin/activate
python3 /home/tkachenkoav/USERTOOLS/MppReader/read_mpp.py "<путь>" --summary
```
Флаг `--summary` оставляет в JSON только сводку + первые 20 задач, чтобы не
раздувать вывод. CSV-файлы (`<имя>__tasks.csv`, `__resources.csv`,
`__assignments.csv`) при этом сохраняются рядом с исходником.

Для большого проекта, где нужен полный список задач, запусти без `--summary`
и/или передай в анализ только CSV.

### 3. Собери ответ для пользователя
По JSON-выводу составь короткий человеческий отчёт:
- **Проект**: название, автор, даты начала/окончания.
- **Сводка**: число задач, ресурсов, назначений.
- **Структура**: верхнеуровневые задачи (outline_level=1, summary=True) и их
  длительности — это де-факто этапы плана.
- **Критические/просроченные**: задачи с `percent_complete < 100` и
  `finish < сегодня` (если есть `status_date` / план уже идёт).
- **Ближайшие 5 задач** по дате `start`.
- **Ресурсы**: список (имя + max_units).
- **CSV-файлы**: укажи пути — пользователь может забрать их по SSH.

Если в Telegram-канале — отчёт коротким сообщением + при желании приложи
CSV-файлы.

### 4. Если скрипт упал
Типовые причины и фиксы:
- `ImportError: Java package 'net' not found` — старая версия mpxj. У нас уже
  новая (классы переехали в `org.mpxj.*`). Скрипт это учитывает.
- `JVMNotFoundException` — нет Java. Поставить:
  `sudo dnf install -y java-17-openjdk-headless`.
- `Не удалось прочитать файл` — формат не распознан или файл повреждён.
  Уточни у пользователя версию MS Project, попроси пересохранить в .mpx или
  .xml (MSPDI).

## Получение .mpp через Telegram (workaround)

Hermes Gateway **блокирует `.mpp`** — нет в whitelist допустимых расширений.

**Схема:** пользователь переименовывает файл в `.zip` и присылает.
Файл — настоящий OLE2 (Composite Document File V2), просто с неверным расширением.

```bash
# Убедиться что это действительно MS Project
file /path/to/received.zip
# → "Composite Document File V2 Document ... Name of Creating Application: Microsoft Project"

# Скопировать с правильным расширением и обработать
cp /path/to/received.zip /tmp/project.mpp
source /home/tkachenkoav/hermes-agent/.venv/bin/activate
python3 /home/tkachenkoav/USERTOOLS/MppReader/read_mpp.py /tmp/project.mpp --format csv
```

Альтернативы доставки: SCP на VM напрямую, Яндекс.Диск → WebDAV.

## Выгрузка в xlsx по шаблону Google Sheets

Используй готовый конвертер — он сам запускает `read_mpp.py`, собирает CSV и строит xlsx:

```bash
source /home/tkachenkoav/hermes-agent/.venv/bin/activate
python3 /home/tkachenkoav/USERTOOLS/MppReader/mpp_to_gs_xlsx.py /tmp/<имя>.mpp
# Последняя строка stdout: READY:/tmp/<имя>.xlsx
```

Отправить результат: `MEDIA:/tmp/<имя>.xlsx`

### Структура шаблона GS Саши
Шаблон: https://docs.google.com/spreadsheets/d/1uehO6B-Cq-5NlkWOqoEixvIDiAyE70rR1DfEQqcW6gg/
Колонки: `No | Название задачи | Длительность | Названия ресурсов | Текст1 | Начало | Окончание | Предшественники`

Читать структуру шаблона (OAuth не нужен, таблица публичная):
```bash
curl -sL "https://docs.google.com/spreadsheets/d/<SHEET_ID>/export?format=csv&gid=0" -o /tmp/gs.csv
head -1 /tmp/gs.csv
```

Ключевые форматы при генерации xlsx:
- **Даты** → `чт 04.06.26` (день недели + `%d.%m.%y`)
  ```python
  DAYS_RU = {0:"пн",1:"вт",2:"ср",3:"чт",4:"пт",5:"сб",6:"вс"}
  dt = datetime.fromisoformat(iso_str)
  result = DAYS_RU[dt.weekday()] + " " + dt.strftime("%d.%m.%y")
  ```
- **Длительность** → `9 дней` (целое число, не `9.0 d`)
- **Ресурсы** — из `__assignments.csv` (join по `task_id`), в `__tasks.csv` поле пустое
- **Предшественники** — очистить от `[`, `]`, пробелов

## MPP → Google Sheets напрямую (OAuth настроен)

OAuth настроен, токен: `~/.hermes/google_token.json` (не `profiles/anthropic/` — профиль удалён).
Переопределение: env `GOOGLE_TOKEN_PATH` или `HERMES_HOME/google_token.json`.
Scopes: Drive + Sheets + Docs. Аккаунт: `tkachenkoav@tutu.ru`.

Пайплайн «пришли .mpp → получи ссылку на новый лист GS»:

```bash
GAPI="python /home/tkachenkoav/.hermes/skills/productivity/google-workspace/scripts/google_api.py"
source /home/tkachenkoav/hermes-agent/.venv/bin/activate

# 1. Парсим .mpp в CSV
python3 /home/tkachenkoav/USERTOOLS/MppReader/read_mpp.py /tmp/<имя>.mpp --format csv

# 2. Создаём новую таблицу
$GAPI sheets create --title "<название из mpp>"
# → возвращает spreadsheetId и spreadsheetUrl

# 3. Пишем заголовок и данные
$GAPI sheets update <SHEET_ID> "A1:H1" --values '[["No","Название задачи","Длительность","Названия ресурсов","Текст1","Начало","Окончание","Предшественники"]]'
$GAPI sheets append <SHEET_ID> "A:H" --values '<JSON массив строк>'

# 4. Права — НЕ anyone. Скрипт push_to_gs.py / roadmap_gs_to_gs.py сам раздаёт
#    writer на tkachenkoav@tutu.ru и i.alex.tkachenko@gmail.com.
```

Вернуть пользователю: `spreadsheetUrl` из ответа `sheets create`.

### Шаблон Саши (актуальный)
Базовый шаблон — **Лист1** из файла `18qdUTa5GvGjpX-qmK2jERZtvWAw0QdIt-Rplw3IICCQ`.

Маппинг колонок:
| Колонка GS | Поле MPP |
|---|---|
| № | порядковый номер |
| % завершения | percent_complete |
| Название задачи | name |
| Длительность | duration |
| Названия ресурсов | assignments |
| Предшественники | тип+лаг из MPP (НО/НН/ОО/ОН + лаг через `;`) |
| Начало | start |
| Окончание | finish |
| Отклонение окончания | "0 дней" |
| Базовое окончание | "НД" |
| Текст1 | notes |

Sheet ID старого шаблона: `1uehO6B-Cq-5NlkWOqoEixvIDiAyE70rR1DfEQqcW6gg`
Читать без OAuth: `curl -sL "https://docs.google.com/spreadsheets/d/<ID>/export?format=csv&gid=0"`
Читать через API (для проверки): `$GAPI sheets get <ID> "A1:H3"`

### Заливка данных в GS (основной сценарий)

После парсинга MPP в CSV — залить данные новым листом:
```bash
source /home/tkachenkoav/hermes-agent/.venv/bin/activate
python3 /home/tkachenkoav/USERTOOLS/MppReader/push_to_gs.py <stem> --dir /tmp
```
Скрипт создаёт новый лист, заливает данные, форматирует заголовок (синий), возвращает `READY:<url#gid=...>`.

### Обновление шаблона колонок
Если пользователь присылает новый шаблон GS и просит выгружать по нему — прочитать заголовки из шаблона, обновить маппинг в `push_to_gs.py` и подтвердить изменения.

### ⚠️ ПРАВИЛА — обязательно для каждого нового .mpp

1. **Каждый .mpp → отдельный новый GS документ** (не вкладка в существующем файле)
2. Скрипт `push_to_gs.py` сам создаёт документ, заливает данные и раздаёт права — всё в одном запуске
3. **Права раздаются автоматически** скриптом на: `tkachenkoav@tutu.ru` и `i.alex.tkachenko@gmail.com` (writer). **Не** `--share anyone`.
4. **Возвращать ссылку** на новый документ: `https://docs.google.com/spreadsheets/d/<ID>/edit`

## Роадмап GS → план MS Project в GS (третий вход)

Триггер: «сделай план MS Project в GS из роадмапа `<url>`», «план из роадмапа».
Правила маппинга и квартальных меток — закрыты, **не переспрашивать** (ТЗ `TZ/MppReader/MppReader_TZ.md`).

```bash
source /home/tkachenkoav/hermes-agent/.venv/bin/activate
python3 /home/tkachenkoav/USERTOOLS/MppReader/roadmap_gs_to_gs.py "<URL>" --title "Роадмап в план MS Project"
# Последняя строка stdout: READY:https://docs.google.com/spreadsheets/d/<ID>/edit
```

Профиль колонок (гибрид 10, не export 16 и не import 8):
`No | Название задачи | % выполнения | Длительность | Названия ресурсов | Текст1 | Текст2 | Начало | Окончание | Предшественники`

Кратко: Название=Инициатива, Текст1=Описание, Текст2=Комментарий, %=Done 100 / In progress 50 / Backlog 0, Начало=релиз SaaS, Окончание=релиз VPC, длительность/ресурсы/предшественники пусто. Квартал: early/mid/end → последний день 1/2/3-го месяца квартала; диапазон в ячейке → конец B; `-` пусто; Deprioritized = max дат этого плана.

Тесты без сети: `cd ~/USERTOOLS/MppReader && python3 -m pytest -m "not live"`. Live Google — только по явной команде Саши.

## Запись изменений в .mpp

mpxj **читает** .mpp, но **писать** обратно в .mpp не умеет (формат закрытый
от Microsoft). Можно:
- Сохранить изменённый план в **.mpx / MSPDI .xml** — открывается в MS
  Project как новый проект.
- Для прямого изменения .mpp использовать **MS Project COM на Windows** —
  см. `/home/tkachenkoav/USERTOOLS/MppReader/read_write_mpp_com.py`
  (заготовка под win32com).

## Файлы

- `/home/tkachenkoav/USERTOOLS/MppReader/read_mpp.py` — основной скрипт чтения.
- `/home/tkachenkoav/USERTOOLS/MppReader/mpp_to_gs_xlsx.py` — конвертер MPP → XLSX в формате GS-шаблона Саши.
- `/home/tkachenkoav/USERTOOLS/MppReader/push_to_gs.py` — заливка MPP в GS (новый документ + форматирование + права).
- `/home/tkachenkoav/USERTOOLS/MppReader/gantt_csv_to_gs.py` — заливка Gantt CSV (gantt-chart-export_*.csv) в GS. Использование: `python3 gantt_csv_to_gs.py <файл.csv> [--title "Название"]`
- `/home/tkachenkoav/USERTOOLS/MppReader/roadmap_gs_to_gs.py` — роадмап GS/CSV → гибрид-план в новом GS.
- `/home/tkachenkoav/USERTOOLS/MppReader/quarter_labels.py` — парсер квартальных меток (`26Q3`, early/mid/end, диапазоны, Deprioritized).
- `/home/tkachenkoav/USERTOOLS/MppReader/extract_predecessors.py` — извлечение predecessors из MPP с типом связи и лагом.
- `/home/tkachenkoav/USERTOOLS/MppReader/read_write_mpp_com.py` — заготовка для Windows (COM, требует MS Project).
- ТЗ: `~/WorkVault/Hermes-Backlog/TZ/MppReader/MppReader_TZ.md`
