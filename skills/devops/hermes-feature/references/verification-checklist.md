# Hermes verification checklist

> Full verification checklist moved from `SKILL.md`.

## Verification Checklist

- [ ] `TZ:finalize` done, AC показан в origin, `GATE:take-into-work` done (`auto-pass: ac-shown`) — фразу «берём в работу» не ждём (императив 28.09)
- [ ] `HF:plan` done + таблица IAC; `GATE:plan-approve` auto (Блок 1А)
- [ ] Бэкап создан в `~/.hermes/_Archives/hermes-backup-YYYYMMDD-HHMMSS/` (Блок 5)
- [ ] Модели: архитектор (cursor-grok-4.6-high) планирует, исполнитель (composer-2.5) пишет/тестирует
- [ ] Cron-субагент: критичные факты из MEMORY переданы явно в промпт
- [ ] Перед каждым side-effect — категория разрешающего сигнала определена (Блок 5Б)
- [ ] Статус «готово»: `GATE:done` always auto после preflight exit 0 (**holds сняты, Q пусты**); отчёт AC — в origin до auto-complete (маркер `AC-delivered: origin`); operator-AC без ✅ при open hold; корень не complete до `GATE:done` done; `HF:plan` + `children=[]` → broken-tail block
- [ ] Все вызовы через Cursor CLI (`agent -p`)
- [ ] Полный документ в `agent -p`: `cat` без head/truncate, либо путь + «прочитай сам», либо явно «часть 1/N»; неполная копия не выдана как полная
- [ ] Новые сущности (если предлагались) — явно вынесены на согласование Саше, не внедрены самостоятельно.
- [ ] На баг-триггер первым шагом оркестратора был **`pipeline init --case BUGFIX`** (фаза `BUG:diagnose` в рецепте) до invoke-role/agent -p; ретро-init нет (инвариант 9)
- [ ] Если готовился вызвать agent -p / cronjob / delegate на баг — slug с фазой `BUG:diagnose` уже в `_state.json` (`pipeline status --slug <slug>`), иначе стоп
- [ ] Новый несекретный конфиг-ключ инструмента — только в `~/WorkVault/Registries/EcosystemConfig.yaml` + `EcosystemConfig.schema.json`; литерал пути/модели/токена в коде и новый per-tool `.env` = дефект; dual-read (`config.overlay.yaml`) запрещён для **новых** tools (сразу `unified_only` через `~/.hermes/lib/usertools_config.py`)
- [ ] Волна eco-config (w1–w4): `probe_battle_venv.py` PASS на боевом python каждого ключа волны; pytest PFS/hermes этот AC не закрывает
