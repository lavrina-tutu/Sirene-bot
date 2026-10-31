# Self-Hosted Honcho: Troubleshooting Notes

## Embeddings healthcheck: wget missing (Aug 2026)

The `ghcr.io/huggingface/text-embeddings-inference:cpu-1.9` image does not include `wget`.
The default healthcheck in `docker-compose.yml` uses `wget` and fails forever:
`/bin/sh: 1: wget: not found`

The container is actually running fine (logs show "Ready") but marked `unhealthy`,
which blocks api/deriver startup (they `depends_on: embeddings condition: service_healthy`).

**Fix:**
```yaml
# docker-compose.yml, embeddings service:
test: ["CMD-SHELL", "curl -sf http://localhost:80/health > /dev/null || exit 1"]
```
Then `docker compose up -d embeddings` to recreate.

## pgvector dim mismatch (Aug 2026)

Alembic migrations create default 1536-dim columns. The `.env` may set
`EMBEDDING_VECTOR_DIMENSIONS=384` for `intfloat/multilingual-e5-small`.
API crashes at startup with `StartupValidationError`.

**Fix:**
```bash
# 1. Run the config script (NOT via uv run — see below)
docker compose run --rm --entrypoint "" api \
  sh -c "/app/.venv/bin/python scripts/configure_embeddings.py --yes"
# 2. Recreate api to get fresh DB connection pool
docker compose down api && docker compose up -d api --no-deps
# 3. Bring up deriver
docker compose up -d deriver --no-deps
```

## `uv run` broken — missing honcho-ai workspace

`pyproject.toml` lists `honcho-ai` in `[dependency-groups].dev` and
`[tool.uv.sources]` but the `honcho-ai/` directory is absent from the repo.
All `uv run ...` commands fail with:
```
Failed to parse entry in group `dev`: `honcho-ai`
`honcho-ai` references a workspace ... but is not a workspace member
```

**Workaround:** use `/app/.venv/bin/python` directly instead of `uv run python`.

## Gateway restart after memory.provider change

With `multiplex_profiles: true`, new sessions pick up the provider change on their next start. No gateway restart required — confirmed on 2026-08-13.
