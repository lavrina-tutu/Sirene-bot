# ORCH:shared-state — чеклист cutover (§7)

Фаза ORCH:shared-state — sirene (emit/invoke не нужны; emit даёт «g6: emit forbidden for sirene»). Выполняется оркестратором напрямую только после зелёного отдельного HF:test и HF:docs-handoff.

## Порядок

1. **Граница:** убедиться, что wrappers вышли (state pid None/мёртв, активных invoke нет). Legacy active invocation не kill/re-emit — принимать по сохранённым prepare/receipt/output или диагноз/ожидание.
2. **rollout.json ДО переноса:** `evidence/rollout.json` — ts (с timezone), tested_commit, base_commit, final_mapping (rel/candidate_path/final_path/sha256/bytes каждого изменённого файла), source before/after, предыдущие accepted (slug/phase/packet/verdict). Это release evidence, не флаг YAML.
3. **Перенос только изменённых файлов** из tested candidate в final (P=WorkVault/Registries, K=hermes-workspace/skills) одним комплектом; после каждого copy сверить sha256 с manifest. SAME-файлы не трогать.
4. **Импорты final:** `python3 -c "import pipeline.cli, pipeline.pipeline_gates, pipeline.invoke_role, ..."` — все модули импортируются с final путей.
5. **K commit:** hermes-workspace — `git add` + `commit` изменённых skill-файлов; затем `restore-all-skills.sh` (rc=0).
6. **Installed-smoke на final путях:** exact argv с `--mode installed-smoke --pipeline-root <final P> --skill-root <final K> --evidence <new root>`; PASS = status PASS + required_smoke_complete=true + 14/14 traces + missing=[] failed=[] + fingerprint_before==after; fingerprints обязаны совпасть с tested manifest (сверять с rollout.json).
7. **Реальная загрузка в Hermes-контексте (IAC-18):** штатный `skill_view(name=...)`, затем `file_path="references/context.md"` и `"references/invoke.md"` — через tools, не внешний Python. Зафиксировать resolved paths и SHA (сверка с tested manifest).
8. **IAC-19:** изменены только файлы final allowlist; master/инвентарь/глоссарий/canon/YAML/digest/manifest/core/jobs/чужие артефакты не трогать.
9. **Evidence:** `evidence/ORCH-shared-state-IAC17-19.md` (или аналогичный) со сводкой: rollout, N/N verified, K commit, restore, installed-smoke summary path, skill_view trace. Затем `complete-phase` с evidence path=этот файл.

## Питфоллы

- После complete ORCH `next` может упасть «rework: requirement authorization required», если в handoff-contract остался неconsumed `purpose=rework-request` — пометить consumed (см. SKILL.md Инвариант №18).
- НЕ объявлять candidate installed до cutover; installed-mode во второй tmp-установке НЕ засчитывает IAC-17/18.
- Не переносить `_state.json`/journal/queue из архива при rollback; откат возвращает только backup-owned пути.
- Skill-файлы hermes-workspace коммитятся ОТДЕЛЬНО от pipeline-файлов WorkVault: K — git-репозиторий, P — не git; git-status проверяется в K.
