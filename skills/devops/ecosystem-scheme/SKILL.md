---
name: ecosystem-scheme
description: "По запросу Саши «дай/покажи/выведи/выгрузи архитектурную/интеграционную/арх/приложения схему» — выдать полную или компактную интеграционную схему экосистемы Hermes/USERTOOLS из манифеста. Читает EcosystemManifest.* в WorkVault/Registries и отдаёт файл/текст."
version: 1.0.0
author: Sirene
license: MIT
platforms: [linux]
metadata:
  hermes:
    tags: [ecosystem, manifest, схема, архитектура, интеграция, WorkVault]
    related_skills: [hermes-feature, tz-workflow, about_usr_skills]
---

# Ecosystem Scheme — выдача интеграционной схемы

## Триггер

Любое из слов в просьбе Саши: **дай / покажи / выведи / выгрузи** + **архитектурную / интеграционную / арх / схему / приложения схему**.

Примеры: «дай интеграционную схему», «покажи архитектурную схему», «выведи схему», «выгрузи приложения схему».

## Источник истины

Всё — в `~/WorkVault/Registries/` (рядах с entities.json):

| Файл | Содержимое |
|---|---|
| `EcosystemManifest.json` | **Канон** — полная машиночитаемая схема (tools / entities / links / conflicts) |
| `EcosystemManifest.render.md` | Полный human-рендер (~9 КБ) — читаемая версия всей схемы |
| `EcosystemManifest.digest.md` | Компактный digest (~1.7 КБ, ≤800 токенов) — строка на инструмент, для Cursor/быстрого обзора |
| `EcosystemManifest.schema.json` | JSON-схема формата |
| `render_manifest.py` | Генератор: `--render` / `--digest` / `--check-drift` |

## Действие

1. **Перечитать** актуальную схему (не из памяти): при необходимости перегенерировать
   ```bash
   cd ~/WorkVault/Registries && python3 render_manifest.py --render && python3 render_manifest.py --digest
   ```
   (Если файлы уже свежие и не менять — можно просто отдать существующие. Перегенерировать только если манифест недавно правился.)
2. **Отдать Саше** в зависимости от запроса:
   - «полную / архитектурную / приложения схему» → **`EcosystemManifest.render.md`** (скинуть файлом `MEDIA:` или вывести/дать путь)
   - «кратко / compact / для работы» → **`EcosystemManifest.digest.md`**
   - «raw / json / машиночитаемую» → **`EcosystemManifest.json`**
3. Если запрос неоднозначен — спросить коротко: полный рендер, digest или JSON (с рекомендацией render.md).

## Питфоллы

- Не выдумывать схему — брать из файла манифеста, не из памяти (манифест меняется).
- `render_manifest.py --check-drift` — если запрос про «проверь актуальность», выполнить и показать результат.
- Файлы в WorkVault доступны и через ownCloud синк — путь стабилен.
- Не редактировать манифест по этому скиллу — только чтение/выдача. Изменения — только по явному императиву через `hermes-feature`/`tz-workflow`.
