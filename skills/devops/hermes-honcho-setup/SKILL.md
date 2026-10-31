---
name: hermes-honcho-setup
description: "Use when: self-hosting Honcho for Hermes."
version: 1.2.0
author: agent
tags: [hermes, honcho, memory, self-hosted, multi-profile]
platforms: [linux]
---

# Hermes Honcho Setup

Self-hosted Honcho memory integration with Hermes Agent across multiple profiles.

## Architecture
Honcho runs via Docker Compose: 4 services (api:8000, deriver, PostgreSQL+pgvector:5432, Redis:6379). Requires LLM API key — server won't start without it. All models must support tool calling.

## Setup Flow

### 1. Install Honcho
```bash
git clone https://github.com/plastic-labs/honcho.git ~/honcho
cd ~/honcho
cp .env.template .env
cp docker-compose.yml.example docker-compose.yml
```

### 2. Configure LLM Provider
Honcho has 4 components requiring LLM calls. Use tiered models via OpenRouter for cost optimization:

| Component | Model | Tier | Frequency |
|---|---|---|---|
| Deriver | `google/gemini-2.5-flash-lite` | Light | Every message |
| Summary | `google/gemini-2.5-flash-lite` | Light | Every 20/60 messages |
| Dialectic (low/med) | `google/gemini-2.5-flash` | Light | Per Hermes turn |
| Dialectic (high/max) | `anthropic/claude-haiku-4-5` | Medium | Complex queries |
| Dream | `google/gemini-2.5-flash` | Light | Every ~8 hours |

### 3. Start Services
```bash
docker compose up -d --build
curl http://localhost:8000/health  # verify
```

### 4. Configure Hermes Profile (default only)
```bash
hermes config set memory.provider honcho --profile default
```

Create `~/.hermes/honcho.json` (default profile's `$HERMES_HOME`):
```json
{
  "baseUrl": "http://localhost:8000",
  "workspace": "hermes",
  "peerName": "<descriptive-id>",
  "hosts": {
    "hermes": {
      "enabled": true,
      "aiPeer": "hermes",
      "workspace": "hermes",
      "recallMode": "hybrid",
      "observation": {
        "user": {"observeMe": true, "observeOthers": true},
        "ai": {"observeMe": true, "observeOthers": true}
      }
    }
  },
  "pinUserPeer": true,
  "runtimePeerPrefix": "telegram_"
}
```

### 5. Other Profiles (example)
- Each profile needs its own `honcho.json` at `$HERMES_HOME/honcho.json`
- Leave `memory.provider` unset → built-in memory only
- Use profile-specific honcho.json (not global `~/.honcho/config.json`) so other profiles don't see it
- **Session strategy:** `sessionStrategy: "global"` for shared memory across all Telegram topics

### 6. Activate Provider
```bash
hermes config set memory.provider honcho
# Then restart the gateway to activate
```

## Self-Hosted Troubleshooting

Common issues (healthcheck failures, pgvector dim mismatch, `uv run` broken) → see `references/self-hosted-troubleshooting.md`.

## Key Concepts

### peerName
Internal database identifier for user grouping across Hermes profiles. Not used in dialogue. Format: descriptive (e.g., `honchodb-sasha`).

### Multi-Peer Model
- One workspace (shared environment)
- One user peer (the human, shared across profiles)
- One AI peer per Hermes profile (independent representations)

## Pitfalls
- **Server fails without LLM key** — Honcho won't start without at least one provider configured
- **Tool calling required** — all models must support function calling; models <14B often fail
- **Profile isolation** — put honcho.json in profile-specific location, not global, to avoid cross-profile activation
- **Deriver essential** — background worker that processes messages; without it, no memory formation occurs
- **Embedding fallback** — if embedding API key empty, falls back to backup provider credentials
- **`HONCHO_API_KEY` error on self-hosted** — `hermes memory status` shows `✗ HONCHO_API_KEY` when `honcho.json` is missing or lacks `baseUrl`. The plugin defaults to cloud mode (`app.honcho.dev`); for self-hosted, create `honcho.json` with `"baseUrl": "http://localhost:8000"` — no actual API key needed.
