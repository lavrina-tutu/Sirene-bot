# Контракт BUGFIX/CHANGE на существующий USERTOOL (точечный invoke-role)

Проверено на поезде edit-plan-confluence-apply-padaet-na-post-verifi (BUGFIX): полный рецепт BUGFIX гоняется точечно через invoke-role, и два состояния контракта стоили лишних циклов. Правила ниже экономят их.

## 1. `master_tz: null` / `research-without-master` годится только для первых фаз диагноза

Первая фаза (BUG:diagnose / RS:collect) спокойно идёт без мастера — emit помечает `master_status=absent, master_reason=diagnosis-without-contract`. Но как только рецепт доходит до `TZ:patch`, emit падает:

```
master binding required; DevWorkflow fallback is forbidden
```

если в handoff-contract всё ещё `master_tz: null`. Это НЕ сбой роли и НЕ надо трогать pipeline — контракт нужно переписать между диагнозом и TZ:patch:

- `master_tz: /home/tkachenkoav/WorkVault/Hermes-Backlog/TZ/<Tool>/<Tool>_TZ.md` — СОБСТВЕННЫЙ мастер-ТЗ инструмента (версию и факт чтения архитектор уже зафиксировал в диагнозе; для edit-plan-confluence это `EditPlanConfluence_TZ.md`).
- `master_absence_reason: null`, `master_section: []`.
- путь master'а добавить в `write_scope` фаз `TZ:patch` и `TZ:finalize` — иначе архитектор вносит норму и падает `output outside write_scope: …/<Tool>_TZ.md`.

После правки контракта — заново `emit-prompt` для TZ:patch (старый packet с `master=absent` не переиспользуется).

## 2. handoff-contract требует РОВНО семь ключей, и ошибка не называет пропущенный

`pipeline_context._contract` проверяет `set(value) != {master_tz, master_section, master_absence_reason, write_scope, prohibitions, inputs, outputs}` и падает с неоднозначным:

```
handoff-contract: invalid keys: <path>
```

Недобавленный обязательный ключ (типично `master_section`) неотличим от опечатки. Перед emit локально распарсить блок и сравнить set() с allowed — сэкономит цикл «emit упал → угадай какой ключ»:

```bash
python3 - <<'EOF'
import re, yaml
t = open('<абс-путь>/brief.md', encoding='utf-8').read()
b = re.findall(r"```handoff-contract\s*\n(.*?)```", t, re.S)
allowed = {"master_tz","master_section","master_absence_reason","write_scope","prohibitions","inputs","outputs"}
print("blocks:", len(b))
print("missing:", allowed - set(yaml.safe_load(b[0])))
print("extra:", set(yaml.safe_load(b[0])) - allowed)
EOF
```

## 3. REV:tz-вердикт обязан быть блоком `## Вердикт`, не строкой; иначе `complete` не распознаёт APPROVE

Парсер приёмки (`pipeline_gates.rev_verdict`) ищет секцию, начинающуюся заголовком `## Вердикт`, или `## Evidence` с полем `verdict=…`. Если ревизор записал финал строкой в шапке — напр. `Вердикт: **APPROVE**.` под `# REV:tz …` — `complete-phase` падает:

```
REV verdict unknown or conflict
```

и next возвращает RECONCILE. Признак для диагностики ДО reset: канонический `REV-tz.md` на диске, `context_result`/receipt уже в state → это `rc0-no-complete`, НЕ dead-pid. Лечение: `recover --class rc0-no-complete` → свежий `emit-prompt` → повторный `invoke-role` ревизора, чтобы он дополнил канон блоком `## Вердикт`. Артефакт роли руками не править (исказит принятую запись); `recover --class dead-pid` тут ничего не меняет (state остаётся doing).

Сравнение ожидаемого формата: принятый канон ревизии — `## Вердикт` (заголовок) → пустая строка → `**APPROVE**`. Перед `complete-phase` сверять, что файл содержит такой заголовок, а не просто inline-слово APPROVE.

## 4. Прочее, что работает (проверено в том же поезде)

- `emit-prompt` фаз TZ/HF/BUG/REV — только после `next` выставил фазу `doing/awaiting_invoke=True`; иначе контракт не подхватится.
- Мастер-бамп от TZ:patch: после внесения нормы следующий `emit-prompt` (REV:tz) сам перечитает master и зафиксирует новый sha — ничего дополнительно не синкать.
- `complete-phase` для BUG:diagnose и авто-гейта `GATE:diagnose-review` — evidence = канонический артефакт с реальным sha256 (`sha256sum` до вызова); для авто-гейта роль не нужна, закрывает оркестратор.
