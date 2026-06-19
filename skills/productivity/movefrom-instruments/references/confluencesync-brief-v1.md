# ConfluenceSync — Бриф v1 (28.05.2026)

## Проект
- Директория: `USERTOOLS/ConfluenceSync/`
- Скилл Hermes: `movefrom-confluence`
- Credentials: `USERTOOLS/MoveFromConfluence/.env` (CONFLUENCE_URL=https://dom.tutu.ru, CONFLUENCE_TOKEN)
- API работает из дома без VPN (проверено 28.05.2026: HTTP 200 с PAT)

## Чтение
- Scope: указанная страница + все дочерние рекурсивно
- Читаем: текст, комментарии, вложения (только ссылки — файлы не скачиваем)
- Изображения: `📎 [рисунок](ссылка_на_confluence_страницу)` — не скачивать
- Ссылки вне дерева: оставить URL + пометить 🔗
- Макросы → Obsidian callouts (`> [!info]`, `> [!warning]`)
- Ре-синк: только по явному запросу

## Хранение
- Путь: `WorkVault/Confluence/<Space>/<Страница>/index.md`
- Дочерние: подпапки с `index.md`
- Frontmatter: `confluence_id`, `title`, `confluence_url`, `synced_at`, `space`, `parent`, `children`, `author`, `last_modified`

## Режимы вывода
- `--to-file` (default): сохранить в WorkVault/Confluence/
- `--to-context`: вывести MD в stdout (для Opus)
- `--to-both`: оба

## Запись в Confluence
- Обновление: по `confluence_id` из frontmatter
- Создание: новая подстраница от указанного родителя
- `confirm=True` (default): спрашивать подтверждение перед записью
- `confirm=False`: писать сразу (для программных вызовов от других инструментов)

## Логирование
- Путь: `WorkVault/_meta/ConfluenceSync/_sync_log.jsonl`
- Формат: JSONL (машиночитаемый)
- Содержимое: всё — чтение, запись, ошибки, пропуски
- Каждая запись: `timestamp`, `operation`, `page_id`, `title`, `status`, `details`

## Use Cases
1. **"Прочитай и сделай"**: пользователь даёт ссылку → `--to-context` → контент в Opus → Opus работает по паттернам разработки/настройки
2. **"Встретил ссылку — обогати"**: инструмент видит ссылку → ConfluenceSync читает страницу → сохраняет рядом с сущностью (проект, встреча, контакт)
3. **Автообновление**: инструмент вызывает с `confirm=False` → обновление без подтверждения

## Тесты
- Unit: моки Confluence API, без реального подключения
- Smoke: реальный Confluence, отдельная тестовая страница

## Структура проекта
Python-пакет с CLI через click (как MoveFromZulip), `pip install -e .`

## Статус
- Бриф завершён 28.05.2026
- Opus пишет ТЗ (cronjob `6171448dffc0`) → `USERTOOLS/ConfluenceSync/TZ.md`
- После ТЗ: Opus реализует → создать скилл `movefrom-confluence`
