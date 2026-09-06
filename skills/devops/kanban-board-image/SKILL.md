---
name: kanban-board-image
description: "Use when: Саша просит «покажи канбан»/«покажи доску канбан» в Telegram. Рендер доски Hermes kannban в PNG (колонки по статусам) для отправки как нативную картинку."
version: 1.0.0
author: agent
platforms: [linux]
metadata:
  hermes:
    tags: [kanban, visualization, telegram, render]
    related_skills: [kanban-orchestrator, kanban-worker]
---

# kanban-board-image

## Когда использовать
Саша говорит «покажи канбан», «покажи доску канбан» (в Telegram-чате, где нельзя открыть интерактивный веб-дашборд). Также при завершении работы с канбан-карточками, когда полезно показать итоговое состояние доски картинкой.

## Почему не веб-дашборд
Telegram не рендерит интерактивные доски (нет drag-drop/колонок/вкладок). Полная графика живёт в Hermes Desktop / `hermes dashboard` (браузер). В чате — статичный PNG-рендер по запросу.

## Шаги
1. Запусти скрипт рендера:
   `python3 ~/hermes-workspace/skills/devops/kanban-board-image/scripts/kanban_render.py /tmp/kanban_board.png`
2. Проверь, что файл создан (размер > 0).
3. Отправь в чат как нативную картинку командой `MEDIA:/tmp/kanban_board.png` в своём ответе.
4. Если доска пустая или только одна колонка — так и покажи (скрипт корректно рендерит 1 колонку).

## Скрипт
Использует `hermes kanban list --json` → группирует карточки по статусу → рисует колонки с цветовой маркировкой → сохраняет PNG.
- Статусы и цвета: triage (серый), todo (голубой), ready (жёлтый), running (ярко-голубой), review (фиолетовый), blocked (красный), done (зелёный), scheduled (лиловый), archived (тёмно-серый).
- Аргументы скрипта: `python3 kanban_render.py [output_path] [statuses_csv]` — второй аргумент фильтрует колонки.

## Питфоллы
- Скрипту нужен PIL: `python3 -c "import PIL"` — если нет, поставить `pip install --user pillow` (или через venv). Обычно PIL уже есть в системном python3.
- `hermes kanban list --format table` НЕ существует (ошибка unrecognized arguments) — только `--json` или дефолтный табличный вид. Для рендера использовать ТОЛЬКО `--json`.
- Если `hermes kanban list --json` вернул пусто/ошибку — доска не инициализирована или канбан выключен; сообщи Саше, картинку не слать.
- Не создавать файлы рендера в user workspace — только в /tmp или ~/.hermes/audio_cache-подобных temp-каталогах.

## Verification
- После рендера открыть PNG не обязательно; достаточно `ls -la` обычно > 10 КБ.
- Рендер должен содержать заголовки колонок вида `STATUS (count)`.
