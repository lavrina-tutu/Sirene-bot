---
date: 2026-06-01
author: Сирень (Opus)
type: daily-self-check
---

# Ежедневный self-check — 2026-06-01

## ✅ Что в порядке

- **config.yaml**: `default=claude-sonnet-4-6`, `fallback=claude-haiku-4-5`, `delegation=claude-opus-4-7` — корректная иерархия. `personality=sirene` активна.
- **GitHub autosync (`bc1b0ae442f0`)** — на Haiku, последний запуск 09:51 ok. Назначение модели правильное.
- **MoveFromFF cron (`1e62e18ae399`)** — на Haiku, статус ok. Правильно.
- **MoveFromZulip (`50a30903f503`)** — paused, не мешает.
- **Скиллы**: 50 файлов в `~/AppData/Local/hermes/skills/`, грубых противоречий нет. `movefrom-instruments` зонтичный, `movefrom-confluence`, `movefromff`, `fireflies-obsidian-sync` — конкретные реализации, дублирования нет.
- **hermes-agent репо**: локальная ветка `main` на `bea78675b`, апстрим ушёл вперёд (Playwright/Docker fixes, MiniMax-M3 1M context, desktop bugfixes). Ничего критичного для Windows-стенда.

## ⚠️ Что нашла

1. **`e7a53b2e2cf2` (Сирень self-check) — модель Opus, последние 2 запуска (30.05 и 01.06) упали с `Request timed out`.** Задача занимает >30 минут (gateway_timeout=1800). Opus + 4 шага + чтение 50 скиллов = слишком много.
2. **`1734ad364b99` (Dialog Backlog понедельничная сводка) — модель Opus, последний запуск 01.06 09:04 упал с тем же таймаутом.** Это координационно-tool-работа (читать backlog, дёргать fetch.py, апдейтить markdown), не deep research → должно быть на Sonnet.
3. **`665a2bf3737e` (P5: анализ токенов routing, разовый 22.06) — модель Haiku, но это анализ/планирование.** По правилам из system prompt анализ → Opus.
4. **`skills/yuanbao/`** лежит в корне `skills/` без категории-родителя (остальные — в `productivity/`, `devops/`, `mlops/` и т.д.). Косметика, но нарушает консистентность.
5. **Дубли скиллов в профилях**: `profiles/qwen-fast/skills/mlops/inference/obliteratus/templates/*.yaml` и `profiles/haiku-fallback/skills/...` дублируют корневые. Если профили не активны — мёртвый груз.
6. **Gateway не запущен** (cron list ругается). Cron-задачи не отстреливают автоматически, пока gateway не поднят.

## 💡 Топ-3 улучшения для Саши

1. **Переключить self-check (`e7a53b2e2cf2`) на Sonnet** и/или разделить на 2 крон-задачи: «аудит скиллов» (Sonnet) + «топ-3 улучшения» (Opus, раз в неделю). Сейчас Opus захлёбывается, ты получаешь пустые таймауты. Команда: `hermes cron edit e7a53b2e2cf2 --model claude-sonnet-4-6`.
2. **Перевести Dialog Backlog (`1734ad364b99`) на Sonnet.** Координация и работа с файлами — профиль Sonnet, не Opus. Иначе понедельничная сводка регулярно будет падать.
3. **Поднять Gateway автозапуском.** `hermes gateway install` (один раз) — иначе все cron-задачи зависят от того, что Саша вручную держит TUI открытым. Это самое узкое место.

Бонус (если будет настроение): почистить `profiles/qwen-fast` и `profiles/haiku-fallback`, если они не используются — экономия места и снижение когнитивной нагрузки при апдейтах скиллов (сейчас одно изменение надо делать в трёх местах).
