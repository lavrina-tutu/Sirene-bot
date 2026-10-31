# Нативная эскалация задачи на более сильную модель (внутри Hermes, без Cursor)

Исследование 10.09.2026 (архитектор cursor-grok-4.6-high, Hermes 0.20.0, основной
`deepseek/deepseek-v4-flash-0731` / tutu).

## Лучший штатный способ — `/model <model> --once`

Механизм эскалации одного тяжёлого хода на более сильную модель **в том же
топике**, с **настоящей историей сессии** (не ксерокопией):

```
/model tutu:deepseek/deepseek-v4-pro --once   # один ход на pro
<следующее сообщение с доп. рамками>
# сессия сама возвращается на дефолтную модель после хода
```

- Имя модели/алиас: `model_aliases` в config.yaml; быстрый слэш `/analyst` — через quick_commands (см. ниже).
- `/model --once` обрабатывает **gateway** до LLM (надёжно, не зависит от детекта фразы моделью).
- Доп. вводные оркестратора вставляются **вторым** сообщением Саши после `--once` — не автоматически.

## Механика Telegram-меню команд (какие `/`-команды видно в подсказках)

Ключевой pitfall: меню `/` в Telegram строится **только** из трёх источников
(`hermes_cli/commands.py::telegram_bot_commands` / `telegram_menu_commands`):

1. встроенные команды ядра,
2. плагины (`register_command`),
3. скиллы (если не скрыты для платформы).

**Quick-команды (`quick_commands` в config.yaml) НЕ попадают в меню.** В коде
прямо указано: *«Aliases are skipped — Telegram shows one menu entry per canonical
command»*. Quick-команды работают (видимы только при ручном вводе `/analyst`),
но в подсказках как `/new` не появляются.

Три слоя «сделать /analyst»:
| Слой | В меню? | Модель топика | Контекст топика |
|---|---|---|---|
| quick_command `{type:alias, target:/model tutu:... --once}` | нет | да | да (полный тред) |
| плагин `register_command('analyst')` | **да** | да (плагин выполняет смену модели) | да |
| скилл `analyst` | да | нет (запускает обработчик скилла) | нет (то же, что delegate_task) |

Для цели «в подсказках как /new + смена модели этого же топика» — **плагин**
`register_command`. Это мини-код (не правка ядра Hermes), но не настройка — dev-задача.
- quick_commands типы (в `gateway/run.py`): `type: exec` (shell в gateway-процессе,
  env санитизирован) и `type: alias` (редирект на другую команду).

## Почему НЕ подходят альтернативы (для «подумай сильнее в этом топике»)

| Механизм | Контекст топика | Пригодность |
|---|---|---|
| `delegate_task` | нет — только goal+context (lossy), ребёнок стартует с пустого чата | не подходит, если нужен полный тред |
| `cronjob(model={...})` | нет | задержка, отдельное сообщение, не интерактивно |
| профиль `hermes -p` | нет (новая сессия) | не привязан к текущему топику |
| auxiliary (vision/compression/session_search) | нет | фикс-слоты, не универсальный роутинг |
| кастомный `call_llm` (паттерн компрессора) | только собранные messages | аналитик без файлов/скиллов, тред не наследуется; ок для extract-only, плохо для «старшего аналитика» |

`delegate_task` per-call `model` в схеме 0.20.0 **отсутствует**; дети берут
`delegation.model` или родителя. `delegation.model` пустой → субагенты наследуют
дефолтную модель (бессмысленно для «сильнее»), пока не запинить на pro (тогда
ВСЕ субагенты станут pro) либо не патчить 4 точки `tools/delegate_tool.py`
(см. `hermes-cost-optimization/references/delegate-per-call-model-patch.md`) — это код Hermes, апстрим-риск.

## Модели tutu для эскалации (каталог 10.09.2026)

| Модель | In $/M | Out $/M | Ctx | Заметка |
|---|---|---|---|---|
| `deepseek/deepseek-v4-flash-0731` | 0.065 | 0.18 | 1.31M | текущий основной |
| `deepseek/deepseek-v4-pro` | 0.96 | 1.91 | 1.05M | естественный «старший», рекомендован |
| `deepseek/deepseek-v4-pro-0813` | 1.05 | 3.15 | 1.05M | новее, дороже out |
| `qwen/qwen3.6-plus` | 0.325 | 1.95 | 1.0M | дешевле по in, out как у pro |
| `google/gemini-2.5-pro` | 1.25 | 10.00 | 1.05M | дорого для регулярной эскалации |

Дефолт для аналитики: `deepseek/deepseek-v4-pro` (а не 0813 и не Gemini).
`--once` на длинном топике ≈ полный input pro по текущему окну; flash дешевле
~15× по in, ~11× по out — смысл эскалации в редких тяжёлых ходах.

## Ссылки на документацию (проверено архитектором)

- Configuring Models — `/model --once`, aliases, cache reset
- Slash Commands — `/model` в Telegram, `--once`, `/moa`
- Subagent Delegation — изолированный контекст, только goal/context
- Configuration / Quick Commands — alias слэшей
- Plugins — `register_command`
- upstream PRs #36790/#64299/#94312 (per-task route) — НЕ влиты в 0.20.0