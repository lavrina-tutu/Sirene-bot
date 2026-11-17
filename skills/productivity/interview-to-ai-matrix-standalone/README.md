# interview-to-ai-matrix-standalone

> Самодостаточный навык для AI-агентов Cursor и Hermes: из транскрипции интервью с
> владельцем процесса за один проход собирает матрицу ИИ-зации (как сейчас → как
> будет) с обоснованным решением, что отдать ИИ, а что оставить человеку. Никаких
> других навыков для работы не требуется — вся логика встроена.

## Что делает

```
транскрипт интервью → проверка по вопросам → описание процесса → матрица ИИ-зации → Excel
```

1. Сверяет транскрипт с 40 контрольными вопросами и показывает, что раскрыто, а чего не хватает.
2. Собирает описание процесса (форматы **А** / **Б** / **В**; по умолчанию — **А**; формат **Б** — **полный** нарратив-регламент с деталями из интервью, см. `templates.md`).
3. Строит матрицу ИИ-зации: строки — виды деятельности, столбцы — стадии, клетки — что и каким типом ИИ поддержать.
4. Помечает узкие места и выгружает результат в Excel с цветовой разметкой.

Пользователь сам выбирает режим вывода: только матрица, только описание или и то и
другое.

## Структура папки

| Файл | Назначение |
|------|------------|
| `SKILL.md` | Главная инструкция: режимы вывода, воркфлоу из 14 шагов, принципы |
| `questions.md` | 40 контрольных вопросов (8 блоков), 12 обязательных |
| `reference.md` | Методология матрицы: легенда из 4 типов ИИ, дерево выбора, виды работы, маркировка узких мест |
| `templates.md` | Все шаблоны: итог проверки, форматы **А** / **Б** / **В**, таблицы матрицы, сводки, схема `spec.json` |
| `reproducibility.md` | Тройной прогон и согласование для устойчивого результата |
| `scripts/export_matrix.py` | Сборка Excel (и CSV) с цветом и пометкой узких мест |
| `scripts/consensus_matrix.py` | Сведе́ние трёх прогонов в согласованную версию |
| `scripts/spec_template.json` | Образец файла данных матрицы |

## Установка

### Cursor

Скопировать папку `interview-to-ai-matrix-standalone` целиком (все файлы и каталог
`scripts/`) в одно из мест:

- **macOS:** `~/.cursor/skills/interview-to-ai-matrix-standalone/`
- **Windows:** `%USERPROFILE%\.cursor\skills\interview-to-ai-matrix-standalone\`
- **для команды (обе ОС):** `<repo>/.cursor/skills/interview-to-ai-matrix-standalone/`

Каталог `.cursor` скрытый: macOS — Finder → Cmd+Shift+G → `~/.cursor/skills/`;
Windows — в адресную строку Проводника `%USERPROFILE%\.cursor\skills`.

Cursor обнаруживает навык автоматически по полю `name` в `SKILL.md`. Перезапуск не
нужен; если навык не виден в открытом чате — начать новый.

Зависимость для Excel (один раз, только если нужна выгрузка):

```bash
# macOS
pip3 install openpyxl
# при ошибке externally-managed-environment:
pip3 install openpyxl --user --break-system-packages
```

```powershell
# Windows
pip install openpyxl
```

Для Markdown и `spec.json` зависимости не нужны.

### Hermes (Telegram-бот)

Авто-обнаружения нет — содержимое навыка передаётся боту как system prompt:
`SKILL.md` (+ при необходимости `questions.md`, `reference.md`, `templates.md`,
`reproducibility.md`). Скрипты из `scripts/` держать там, где есть Python — в
Telegram они не исполняются.

## Запуск

### Cursor

- В чате написать «Применить interview-to-ai-matrix-standalone к этому транскрипту» и приложить расшифровку, указав режим вывода (матрица / описание / оба);
- если данных мало — навык предупредит и предложит донести недостающее;
- для матрицы нужен Agent-режим: Cursor сам вызывает `scripts/export_matrix.py`. Ручной вызов:

```bash
# macOS
python3 scripts/export_matrix.py --input <имя>.spec.json --format xlsx --output <имя>.xlsx
```

```powershell
# Windows
python scripts\export_matrix.py --input <имя>.spec.json --format xlsx --output <имя>.xlsx
```

### Hermes

- Отправить боту транскрипт и указать режим вывода — логика работает на стороне модели;
- бот отдаёт итог проверки, описание/матрицу в Markdown и блок `spec.json`;
- Excel без Python в Telegram не собрать: сохранить `spec.json`, взять `export_matrix.py` и собрать локально (`pip install openpyxl` → `python export_matrix.py ...`).

## Команды по ОС

- macOS — `python3` / `pip3`; Windows — `python` / `pip` (или `py`);
- `--break-system-packages` — только macOS и только при ошибке `externally-managed-environment`;
- CSV — только по запросу (`--format csv` или `--format both`), по умолчанию Excel;
- тройной прогон (финальные матрицы):

```bash
python3 scripts/consensus_matrix.py --inputs run1.spec.json run2.spec.json run3.spec.json --output <имя>.spec.json --report <имя>.divergence.md
```
