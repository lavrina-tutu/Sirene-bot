---
name: tutu-confluence-jira
description: "ТУТУ корп. системы: скачать страницы Confluence в WorkVault, работать с JIRA (создание задач, поля, проекты). Базовый URL dom.tutu.ru, аутентификация через ConfluenceSync .env."
version: 1.1.0
author: agent
license: MIT
platforms: [linux]
metadata:
  hermes:
    tags: [TUTU, Confluence, JIRA, WorkVault, договор, согласование]
    related_skills: [tutu-jira-contract-approval, tutu-jira-okr, obsidian, pm-briefing]
---

# TUTU Confluence & JIRA

Корпоративные системы ТУТУ доступны только через VPN/internal network. `web_extract` блокирует `dom.tutu.ru` (resolves to 10.x.x.x). Всегда использовать `terminal` + `curl` или ConfluenceSync CLI.

## Авторизация

**Два разных токена — не путать:**

| Система | Файл | Переменная |
|---|---|---|
| Confluence (`dom.tutu.ru`) | `~/USERTOOLS/ConfluenceSync/.env` | `CONFLUENCE_TOKEN` |
| JIRA (`hq.tutu.ru`) | `~/.hermes/profiles/anthropic/.env` или `~/.config/hermes/.env` | `JIRA_TOKEN` + `JIRA_BASE_URL=https://hq.tutu.ru` |

Загрузить Confluence: `source ~/USERTOOLS/ConfluenceSync/.env`

Для Confluence curl:
```bash
curl -H "Authorization: Bearer $CONFLUENCE_TOKEN" "https://dom.tutu.ru/rest/api/..."
```

Для JIRA curl:
```bash
source ~/.config/hermes/.env  # или ~/.hermes/profiles/anthropic/.env
curl -H "Authorization: Bearer $JIRA_TOKEN" \
     -H "Content-Type: application/json" \
     "https://hq.tutu.ru/rest/api/2/..."
```

---

## Confluence: скачать страницу в WorkVault

### Инструмент: ConfluenceSync CLI

```bash
cd ~/USERTOOLS/ConfluenceSync

# Скачать страницу в WorkVault (по умолчанию)
python3 -m confluencesync pull <pageId> --no-recursive

# Скачать и вывести MD в stdout (для агента)
python3 -m confluencesync pull <pageId> --to-context --no-recursive

# Скачать И в WorkVault И в stdout
python3 -m confluencesync pull <pageId> --to-both --no-recursive

# С дочерними страницами
python3 -m confluencesync pull <pageId> --depth 2
```

**Куда сохраняется:** `~/WorkVault/Confluence/<space-key>/.../<title>/index.md`  
Путь вычисляется по иерархии Confluence автоматически.

**Лог операций:** `python3 -m confluencesync log`

### Получить pageId из URL
URL вида `https://dom.tutu.ru/pages/viewpage.action?pageId=389284624` → pageId = `389284624`

### Прямой REST API (без сохранения)
```bash
source ~/USERTOOLS/ConfluenceSync/.env
curl -s -H "Authorization: Bearer $CONFLUENCE_TOKEN" \
  "https://dom.tutu.ru/rest/api/content/<pageId>?expand=body.storage" \
  | python3 -c "
import sys, json, re, html
data = json.load(sys.stdin)
title = data.get('title', '')
body = data.get('body', {}).get('storage', {}).get('value', '')
print('# ' + title)
text = re.sub(r'<li>', '\n- ', body)
text = re.sub(r'<h[1-6][^>]*>', '\n## ', text)
text = re.sub(r'<[^>]+>', '', text)
text = html.unescape(text)
print(re.sub(r'\n{3,}', '\n\n', text).strip())
"
```

---

## JIRA: создать задачу

### Проект TOMAKE — согласование договора

**Путь:** JIRA → Проект `TOMAKE` → Тип задачи `Задача`

Обязательные поля при согласовании договора:
- `summary` — название (напр. `Согласовать договор с АО «Неофлекс Консалтинг»`)
- `components` — `Маркетинг` (для маркетинговых/расходных договоров)
- `priority` — `Обычный` по умолчанию
- `description` — все договорённости с партнёром (см. `references/tomake-contract-fields.md`)
- Вложение — файл договора

**Исполнитель проставляется автоматически.**

### REST API: создать задачу
```bash
source ~/USERTOOLS/ConfluenceSync/.env

curl -s -X POST \
  -H "Authorization: Bearer $CONFLUENCE_TOKEN" \
  -H "Content-Type: application/json" \
  "https://dom.tutu.ru/rest/api/2/issue" \
  -d '{
    "fields": {
      "project": {"key": "TOMAKE"},
      "issuetype": {"name": "Задача"},
      "summary": "Согласовать договор с ...",
      "priority": {"name": "Обычный"},
      "description": "...",
      "components": [{"name": "Маркетинг"}]
    }
  }'
```

### REST API: получить поля проекта
```bash
source ~/USERTOOLS/ConfluenceSync/.env
# Все задачи проекта
curl -s -H "Authorization: Bearer $CONFLUENCE_TOKEN" \
  "https://dom.tutu.ru/rest/api/2/project/TOMAKE" | python3 -m json.tool

# Доступные компоненты
curl -s -H "Authorization: Bearer $CONFLUENCE_TOKEN" \
  "https://dom.tutu.ru/rest/api/2/project/TOMAKE/components"

# Приоритеты
curl -s -H "Authorization: Bearer $CONFLUENCE_TOKEN" \
  "https://dom.tutu.ru/rest/api/2/priority"
```

---

## Важные правила процесса (регламент ТУТУ)

1. **Новый договор** → задача через АДД «Нужна помощь аккаунт-менеджеров», поле «Договор (расходный/доходный)». АДД автоматически создаёт задачу MIX.
2. **ДС/Приложение/Заявка к существующему договору** → задача напрямую в TOMAKE, за 2 недели до старта работ.
3. **Договор согласовывается ДО даты начала работ/оказания услуг.**
4. Исполнитель назначается автоматически (руководитель отдела или его замена).
5. Статусы: `Сделать` → `В работе` → `Требуется доработка` (→ автору назад).

Инструкции сохранены в WorkVault:
- `WorkVault/Confluence/UACCOUT/.../Как поставить задачу на аккаунта_ JIRA-TOMAKE/index.md`
- `WorkVault/Confluence/UACCOUT/.../MIX. Регламент _Передача договора.../index.md`

---

## Питфоллы

- **`web_extract` блокирует dom.tutu.ru** — resolves to internal 10.x.x.x. Всегда использовать `terminal` + curl или ConfluenceSync CLI.
- **ConfluenceSync .env содержит PAT** — `source ~/USERTOOLS/ConfluenceSync/.env` перед curl.
- **`--dest` флага нет** у confluencesync pull — путь сохранения определяется автоматически по иерархии Confluence; управление через `.env` WORKVAULT_PATH.
- После изменений в WorkVault — `rclone sync ~/WorkVault owncloud:WorkVault`.
- **REST API возвращает 404 на некоторые pageId** — не ошибка конфигурации. Причины: страница в пространстве без прав для PAT, или пространство использует SSO/keycloak-only авторизацию (v2 API редиректит на keycloak). Это нормально — зафиксируй ссылку для ручного открытия, не трать время на обходы.
- **confluencesync pull выводит «✓ pulled 0 page(s)»** на уже скачанной странице — нужен флаг `--resync` для перезаписи. Без флага пропускает существующие файлы молча.

---

## Связанные скиллы

- `obsidian` — работа с WorkVault напрямую
- `pm-briefing` — брифование PM по открытым вопросам задачи

## Бриф по договорным задачам

Когда готовим задачу TOMAKE, часть полей может быть неизвестна заранее.
Бриф проводить в формате pm-briefing: **один вопрос — номерованные варианты — рекомендация**.

**Куда записывать ответы:** `WorkVault/Tasks/<название-задачи>.md` (мини-ТЗ), не в pm/-структуру.

Порядок вопросов по приоритету (блокирующие сначала):
1. **КБК** — без него задача вернётся на доработку
2. **Кто подтверждает оплату** — только для расходных
3. **Срок действия договора** — начало/конец
4. Механика, контакты партнёра, ЭДО, уставные документы

Если КБК неизвестен — искать в `references/kbk-tech-articles.md`,
предложить подходящую статью, элемент финансовой структуры уточнить у заказчика.

---

## Ссылки

- `references/tomake-contract-fields.md` — обязательные поля для согласования договора в TOMAKE
- `references/kbk-tech-articles.md` — справочник технических статей КБК для ИТ-договоров
- `templates/tomake-contract-description.md` — шаблон описания задачи TOMAKE (стандарт + нестандартный случай со стартом до подписания)

Работа с целями OKR (проекты OKRS/OKRAID) — отдельный скилл `tutu-jira-okr`, не здесь.
