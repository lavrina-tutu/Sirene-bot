---
name: honcho-self-hosted-ops
description: "Use when: troubleshooting self-hosted Honcho Docker."
version: 1.0.0
author: agent
tags: [hermes, honcho, docker, pgvector, embeddings, troubleshooting]
platforms: [linux]
metadata:
  hermes:
    tags: [hermes, honcho, docker, pgvector, embeddings, troubleshooting]
    related_skills: [hermes-honcho-setup]
---

# Honcho Self-Hosted Ops

Troubleshooting and maintenance for a self-hosted Honcho (Docker Compose).
Path: `~/honcho/`. Services: api:8000, deriver, database:5432, embeddings:8081, redis:6379.

## Known Pitfalls

### 1. Embeddings healthcheck: wget missing

The `ghcr.io/huggingface/text-embeddings-inference:cpu-1.9` image does not include `wget`.
Healthcheck in `docker-compose.yml` uses `wget` → fails forever with `/bin/sh: 1: wget: not found`.
Container is actually running fine (logs show "Ready") but marked `unhealthy`, which blocks api/deriver startup.

**Fix:** replace `wget` with `curl` in the healthcheck:

```yaml
# Before:
test: ["CMD-SHELL", "wget -qO- http://localhost:80/health || exit 1"]
# After:
test: ["CMD-SHELL", "curl -sf http://localhost:80/health > /dev/null || exit 1"]
```

Then `docker compose up -d embeddings` to recreate the container.

### 2. pgvector dim mismatch: api crashes on startup

If the DB was created with default 1536-dim vectors but `.env` sets `EMBEDDING_VECTOR_DIMENSIONS=384` (matching `intfloat/multilingual-e5-small`), the api fails at lifespan:

```
StartupValidationError: public.documents.embedding dim (1536) does not match
EMBEDDING_VECTOR_DIMENSIONS (384). Run `uv run python scripts/configure_embeddings.py`
```

**Resolution order:**
1. Verify embeddings container is healthy first (pitfall #1 above)
2. Run `configure_embeddings.py --yes` via `docker compose run`:
   ```bash
   docker compose run --rm --entrypoint "" api \
     sh -c "/app/.venv/bin/python scripts/configure_embeddings.py --yes"
   ```
   Note: `uv run` fails because `honcho-ai` is listed in `[dependency-groups].dev` but not present as a workspace member. Use the direct venv python path.
3. Recreate the api container (it caches a stale pool):
   ```bash
   docker compose down api && docker compose up -d api --no-deps
   ```
4. Bring up deriver:
   ```bash
   docker compose up -d deriver --no-deps
   ```

**Why recreate api after the script?** The api startup validator (`src/startup/embedding_validator.py`) runs inside the container's process. Even though the ALTER succeeded in a separate run container, the api container may hold stale connections or the entrypoint may re-introspect in a way that returns cached values. Recreating guarantees a fresh connection pool.

### 3. `uv run` broken due to missing `honcho-ai` workspace member

`pyproject.toml` lists `honcho-ai` in `[dependency-groups].dev` and `[tool.uv.sources]` but the `honcho-ai/` directory doesn't exist in the repo. Any `uv run ...` command fails:

```
Failed to parse entry in group `dev`: `honcho-ai`
`honcho-ai` references a workspace ... but is not a workspace member
```

**Workaround:** use `/app/.venv/bin/python` directly instead of `uv run python`.

## Quick Diagnostics

```bash
# All containers status
docker compose ps

# Embeddings logs (check for "Ready")
docker compose logs --tail=20 embeddings

# API crash reason
docker compose logs --tail=40 api

# Verify pgvector dim in DB
docker compose exec -T database psql -U postgres -d postgres -c \
  "SELECT c.relname, a.atttypmod FROM pg_attribute a
   JOIN pg_class c ON a.attrelid = c.oid
   JOIN pg_namespace n ON c.relnamespace = n.oid
   WHERE n.nspname = 'public' AND a.attname = 'embedding'
   AND c.relname IN ('documents', 'message_embeddings');"

# Check healthcheck failure reason
docker inspect honcho-embeddings-1 --format='{{json .State.Health}}' | python3 -m json.tool
```

## Expected healthy state

All 5 services healthy (deriver has no healthcheck, shows "Up"):

| Service | Port | Expected Status |
|---|---|---|
| api | 127.0.0.1:8000 | Up (healthy) |
| database | 127.0.0.1:5432 | Up (healthy) |
| deriver | — | Up |
| embeddings | 127.0.0.1:8081 | Up (healthy) |
| redis | 127.0.0.1:6379 | Up (healthy) |

## Full startup sequence (fresh install)

```bash
cd ~/honcho

# 1. Start all services
docker compose up -d --build

# 2. Fix embeddings healthcheck if needed (see pitfall #1)

# 3. Fix dim mismatch if api crashes (see pitfall #2)

# 4. Verify all healthy
docker compose ps
curl http://localhost:8000/health
```
