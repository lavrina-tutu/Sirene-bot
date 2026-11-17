

## Historical source (superseded where it conflicts with SKILL.md; not current instruction)

## Питфолл 5: CLI-агент требует git — в USERTOOLS нет корневого репо

`invoke-role` (codex CLI) не запускается вне git-репозитория. Корень `~/USERTOOLS` — НЕ git-репо (внутри тулы лежат вложенные `.git`). Либо работать в `~/WorkVault` (git-adv), либо временно `git init` в корне USERTOOLS ради раскатки и после `rm -rf .git`. Не забыть: временный корневой `.git` вызовет drift `usertool_not_in_manifest` в `render_manifest.py --check-drift` — убрать его после.

Всегда независимо верифицировать результат codex-исполнителя по реальному строю: `grep -rl usertools_env`, реальные smoke-прогоны на нужных venv, `git diff` конфигов (секреты не попали в коммит), сверка снятых ключей с центральным `.env`.
- Двухступенчато: fuzzy (порог 80%, `SequenceMatcher`) по задачам с тем же `assignee_userkey` →
  LLM batch для остатка. Промпт кодирует правило: «разные исполнители = разные задачи, даже при
  100% совпадении текста».
- **Пробел:** `_llm_check_tasks` строит пул `all_published` из ВСЕХ исполнителей; фильтр «тот же
  исполнитель» держится только текстом промпта, не структурно. Надёжно — программно отфильтровать
  пул по `assignee_userkey` перед LLM-вызовом (per-candidate пул).
