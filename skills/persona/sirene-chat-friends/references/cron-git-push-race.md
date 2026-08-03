# Питфолл: два крона пушат в один git-репозиторий

## Симптом
`Skills git sync FAILED: ! [rejected] (fetch first)` — non-fast-forward push.

## Причина
Два кронджоба работают с одним remote (напр. `hermes-config`):
- `vm_nightly_pipeline` (01:00) — `sync_skills_to_git.sh` пушит из `~/hermes-config`
- `hermes-config-weekly-sync` (02:15) — `sync_hermes_config.sh` пушит из `~/hermes-config-repo`

Один из кронов делает push без предварительного pull. После нескольких запусков клоны расходятся — push отвергается.

## Решение (применено 22.06.2026)
В `sync_skills_to_git.sh` перед `rsync` добавить блок:
```bash
( cd "$REPO" && git fetch origin main --quiet && git pull --rebase origin main 2>&1 | tail -3 ) || echo "[sync_skills] pre-pull warning"
```

Затем ручной `git pull --rebase && git push` чтобы починить уже расшедшийся стейт.

## Общее правило
Любой скрипт, который делает `git push`, должен перед этим делать `git pull --rebase`. Особенно важно когда несколько кронов работают с одним репозиторием.
