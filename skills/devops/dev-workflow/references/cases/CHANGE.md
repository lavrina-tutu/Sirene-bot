# Кейс CHANGE — эталон полного цикла

Доработка **существующего** инструмента или процесса. Полная норма по фазам — DevWorkflow_TZ **Б18**; здесь — карта для оркестратора.

## Когда выбрать

Саша просит изменить то, что уже есть (ТЗ, pipeline, скилл, USERTOOL). Семейство CHANGE фиксируют на старте; LIGHT — позже через `set-case`, не по инициативе архитектора.

## Рецепт на диске (после `init --case CHANGE`)

```text
TZ:stabilize → TZ:compress → TZ:patch → REV:tz → TZ:finalize
→ GATE:take-into-work
→ [HF:compress]? 
→ HF:plan → REV:plan → GATE:plan-approve
→ HF:backup → HF:impl → HF:test → HF:docs-handoff
→ ORCH:shared-state → GATE:done
```

`TZ:stabilize` и `TZ:compress` для CHANGE **обязательны**. `HF:compress` — по желанию оркестратора (длинное ТЗ). `REV:tz` и `REV:plan` обязательны, кроме явного waive Саши (`flag-waived: Sasha` в state).

Бриф в Telegram — **до** `init`, в `recipe[]` не входит.

## Поток (лучшая практика)

1. Закрытый бриф: периметр, решения, slug.
2. `pipeline init --case CHANGE --slug … --title … --origin-chat … --origin-thread …`
3. Каждый ход: `next` → работа одной фазы → `complete-phase --reason … --evidence …`
4. Между фазами — только `emit-prompt` + `invoke-role` (`context.md`).
5. Уведомления о ходе — origin; поломки CLI — ErrorBus.

## Ключевые выходы фаз

| Фаза | Без чего нельзя complete |
|---|---|
| TZ:stabilize | `tz_path`, `tz_version`, `mtime` в state |
| TZ:compress | `extract.md` + поля `extract_*` в state; coverage PASS |
| TZ:patch / finalize | master-ТЗ на диске; evidence с path+version |
| REV:tz / REV:plan | `REV-*.md` с APPROVE (или цикл REQUEST-CHANGES) |
| GATE:take-into-work | непустой `AC-list.md`, показ в origin |
| HF:plan | план + таблица IAC |
| HF:impl | код; `changed_files` для git-proof |
| HF:test | прогон IAC.verify |
| HF:docs-handoff | документация скилла/ТЗ-секций согласована |
| ORCH:shared-state | манифест/schema/restore — по чеклисту ORCH |
| GATE:done | preflight 0, `AC-report.md` в origin |

## Workspace

- TZ / REV:tz — `TZ_ROOT`.
- HF:* USERTOOL — `USERTOOLS/<Tool>`.
- Пакет DevWorkflow (pipeline + скилл) — два invoke на impl: WorkVault, затем hermes-workspace (`invoke.md`).

## Отличия других кейсов

Не дублируем полный цикл здесь (DRY по ТЗ Б36):

| Кейс | Главное отличие от CHANGE |
|---|---|
| DEV | без stabilize/compress в начале; сразу patch… |
| CHANGE-LIGHT | короче TZ и хвост; без REV по таблице LIGHT |
| BUGFIX | префикс BUG:diagnose + GATE:diagnose-review |
| RESEARCH | только RS:* + GATE:done |
| MIGRATION | MIG:plan вместо HF-хвоста |
| DECOMM | DEC:* + GATE:go (never auto) |
| SKILL-* | workspace skills, SK:preflight, ORCH restore |

Рецепты в коде: `pipeline_recipe.py`.
