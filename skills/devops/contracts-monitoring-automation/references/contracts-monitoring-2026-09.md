# ContractAssistant — архив сессии 2026-09-08

## Общая задача
Автоматизация знаний и ответов по договорам ТУТУ: хранить канон фактов в `WorkVault/Entities/Contracts/` и авто-готовить проекты ответов на вопросы из JIRA-комментариев/Loop/почты. Пост наружу — только после явного OK Саши.

## Артефакты сессии
| Артефакт | Путь |
|---|---|
| ТЗ ContractAssistant | `~/WorkVault/Hermes-Backlog/TZ/ContractAssistant/ContractAssistant_TZ.md` v0.3.0 |
| Пофайловый план | `.../ContractAssistant/appendix_impl-plan_20260908.md` |
| USERTOOL | `~/USERTOOLS/ContractAssistant/` (пакет `contractassistant/`, scripts `ca_watch.py`/`ca_post.py`) |
| Скилл (user-owned) | `~/hermes-workspace/skills/productivity/contract-assistant/SKILL.md` |
| Канон фактов | `WorkVault/Entities/Contracts/` (зонтик + Rules/ + `<slug>/<slug>.md` + artifacts/) |
| MoveFromLoop ТЗ | v0.4.5 (строка предупреждения «CA не подключать в mfl_*») |

## Открытые вопросы ТЗ Q1-Q7 — решения
- Q1/Q7: пост наружу только по OK Саши; `auto_post:false` + `auto_post_slugs:[]`; CLI + скилл в v0.1.
- Q2: детей договоров в entities.json НЕ заносим (только файлы под зонтиком).
- Q3: вложенность `Entities/Contracts/<slug>/`.
- Q4: Loop-контур — DM-allowlist + @упоминания.
- Q5: Exchange — почта триггер (вопрос → схема; не вопрос → уведомление).
- Q6: эталон Qlever + параллельный новый договор.
- Q8 (вариант 2, по кронам): два своих крона CA, MFL не трогать.

## Варианты встраивания CA в кроны (компрессор + вердикт архитектора)
1. **Как ExchangeMonitor** (встроить в `mfl_urgent_check.py`/`mfl_digest.py`) — **отказано**: ломает SLO MFL «<30с» (Hermes отдаёт stdout после exit); другой ЖЦ (JIRA + свой watermark + окно 8-20 + classify + OK-гейт); `no_agent` vs `ca_answer`-LLM.
2. **Гибрид** (MFL сбрасывает события в `inbox.jsonl` CA) — отказано как единственный poll: MFL не тянет JIRA-комментарии; фильтры не совпадают с контуром Q4.
3. **Свои job + свой state** — **принято** (вариант 2 Саши). Два `no_agent` job со сдвигом расписания.

## Итоговые кроны CA (созданы 08.09.2026)
| Крон | Job ID | Расписание | Режим |
|---|---|---|---|
| CA urgent | aa2b8a24b735 | `1-59/3 8-20 * * 1-5` | `ca_watch.py` (no_agent, urg) |
| CA digest | edc92b6708d7 | `5 8-20 * * 1-5` | `ca_watch.py --mode digest` |
- script в `~/.hermes/scripts/ca_watch.py` (копия из USERTOOLS, хардкод `_ROOT`)
- deliver → `telegram:-1004300127777:6556` (единый Messages-топик с MFL)
- БЕЗ `--apply`/`--sasha-ok`; окно 8-20 как защита; fail-quiet → ErrorBus `--tool ContractAssistant`
- Существующие кроны MFL `f61b26cbbdf5`/`2865cc674493` не затронуты

## Ключевые техники
- **Водяной знак двигается на пустом тике** (`max_ts if had else tick_now`) — иначе вечный lookback.
- **Статус-без-цитаты = unknown**: сумма/ИНН/комиссия отвечать только с `cite` на секцию агрегата/регламента.
- Поля Service Desk (`customfield_42092` ЗК, `customfield_42094` решение) **не редактируются через REST** (PUT sdesk→500, PUT api/2→400) — через API только комментарий.
- Регламент закупок: до 5 млн — согласование владельца бюджета + ГД юрлица, Комиссия не нужна (обоснование «комиссия не проводилась»).