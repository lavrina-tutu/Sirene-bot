# Honcho Setup — Status + Plan Deviation

## Current State (as of Aug 13, 2026)

### Docker Containers (~/honcho/)
All 5 services healthy:
- api:8000 → healthy
- database:5432 → healthy  
- deriver → running
- embeddings:8081 → healthy
- redis:6379 → healthy

### Config Changes Made (need review/revert)
1. **docker-compose.yml**: Fixed healthcheck (wget → curl) ✅
2. **~/.hermes/config.yaml**: Set `memory.provider: honcho` (global config, affects default profile)
3. **~/.hermes/profiles/default/honcho.json**: Created with self-hosted config (baseUrl, sessionStrategy: global, pinUserPeer, runtimePeerPrefix)
4. **~/.hermes/profiles/tz-dev/honcho.json**: Created then DELETED (tz-dev should NOT have honcho per TZ)
5. **~/.hermes/profiles/tz-dev/config.yaml**: Had `memory.provider: honcho` added, then REVERTED

### Pending
- Gateway restart needed for default profile to pick up honcho provider
- Test message flow → verify Honcho observes and creates peer data

## TZ / Plan Status
- Original TZ exists (search hermes-honcho-setup skill)
- No formal TZ was created for this specific session
- hermes-feature procedure was NOT followed — actions started without plan/approval
- Need to: create proper TZ with current state, submit for approval, then proceed via hermes-feature blocks

## What Needs Fixing
1. Audit: verify no tz-dev side effects remain
2. Create proper TZ for "Enable Honcho for default profile" 
3. Follow hermes-feature: Block 0 (TZ) → Block 1 (variants) → Block 1A (plan) → approval → execution
4. Only default profile should get honcho integration (per TZ rules)
