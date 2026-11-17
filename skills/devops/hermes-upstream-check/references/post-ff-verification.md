Apply within the restrictions of SKILL.md and only within authorized scope. Commands and examples refer to the original version; check configuration values and roles against current state.

## After FF: multi-platform delivery verification (required)

> Context (RU): Прецедент 16.09.2026: git-FF `v2026.9.14` + тесты зелёные + рестарт gateway → DM жив, топики группы молчат. Реальный inbound группы умер на allowlist-гейте (env-over-YAML); это увидели только живым сообщением в группе.

The attempt verdict requires git-FF and, if restarted, PASS of this checklist. DM-only, `hermes doctor`, and cron outbound to a topic do not prove group inbound. Step 7 of `references/upstream-merge-steps.md` (`hermes doctor` / `status` / `cron list`) checks import/health, not delivery; do not close the attempt on that basis.

### When restart is allowed

- Restart is not part of git execution (see upstream-incident-history.md). FF leaves old bytecode in memory until Sasha explicitly authorizes a specific restart window.
- Restart loads both new code and disk configuration into the process. Editing `.env`/`config.yaml` without restart leaves disk and runtime different; do not declare it fixed.
- After an authorized restart, the agent runs this checklist. Live Telegram getUpdates/smoke requires Sasha's explicit permission for restart and checking; otherwise restrict work to disk audit and existing inbound logs.
- Do not run concurrent `getUpdates` on the production token while gateway polls: 409 triggers `_handle_polling_conflict` + `drop_pending_updates=True` and loses the queue. Identify the poller from `gateway.log` / `gateway_state.json`, not by intercepting long-poll.

### Disk audit (immediately after FF, before restart)

Compare effective values, not YAML alone.

| Check | Method | PASS |
|---|---|---|
| Code vs process | `gateway_state.json` `code_sha` vs `git rev-parse HEAD` | SHA differs before restart as expected; matches afterward. |
| Token audit | bot-id prefix of `TELEGRAM_BOT_TOKEN` in `~/.hermes/.env` and `profiles/default/.env` vs `gateway.telegram.token` in YAML | Same bot, admin of «Сирень Workspace» (`863022…` / `sirene_vm_bot`). YAML `882117…` (AlexHermesLocal1) is a hazard: runtime `_Cred` takes env, but without env the poller switches to a bot outside the group. |
| Allowlist | `TELEGRAM_ALLOWED_CHATS` in both `.env` vs `telegram.allowed_chats` in YAML | Effective set contains DM `400307920` and group `-1004300127777`. Env wins over YAML when set (`extra_or_secret`, `gateway/platforms/_shared.py`). |
| Distinguish keys | `TELEGRAM_ADDITIONAL_STARTUP_CHANNELS` / `TELEGRAM_HOME_CHANNEL` | Neither is the inbound allowlist. |
| Topic snapshot | `bash ~/.hermes/skills/devops/tutu-telegram-delivery/scripts/restore_telegram_topics.sh check` | Exit 0; on mismatch use `dry-run`, then `apply` only by explicit decision. |
| Multiplex | `gateway.multiplex_profiles` and profiles with their own telegram `.env` | A second poller on the same token causes 409. Skeletons without telegram `.env` do not start Telegram. |

For risk analysis criterion 1, search the upstream diff if adapters/platforms changed: `extra_or_secret`, `TELEGRAM_ALLOWED_`, `allowed_chats`, `env → YAML`, `get_scoped_secret`. Compare our `.env`, not just YAML. Commit class `3dedb71f2f` (13.09.2026, env-first) was absent from base `d01cc627` and arrived in the 16.09 merge; YAML-only review missed it.

### Live smoke after restart (when separately authorized)

Check at least two channels:

1. **DM** `400307920`: confirm a reply. This alone is insufficient: `_should_process_message` returns `True` immediately for private messages and does not test the group allowlist.
2. **Group** «Сирень Workspace» `-1004300127777`: send a message in a live canonical topic (catalog: `tutu-telegram-delivery/references/sirene-workspace-topics.yaml`). In `gateway.log` after restart verify `inbound` with `chat=-1004300127777` and a reply in the same `message_thread_id`.
3. Do not count cron/topic notifications: outbound uses Bot API directly, bypassing gateway inbound.
4. If group is silent while DM works, first check effective allowlist and poller token, before forum routing / prune sessions / multiplex. Look for adapter WARNING `Dropped inbound` if the patch is merged.

Check the current topic list in the canonical catalog.

### Config migration without losing the multi-token setup

`hermes config migrate` (16.09: 33→44) does not write `.env`. A narrow `TELEGRAM_ALLOWED_CHATS` in `.env` survived migration and overrode correct YAML after restart. The YAML token also remained unchanged (backup 11:56 = `882117…`); “restore our defaults” restored display/delegation/curator (`all/50/3/30/90`), not telegram.

Before migrate:

```bash
cp -a ~/.hermes/config.yaml ~/.hermes/config.yaml.bak-<date>
cp -a ~/.hermes/.env ~/.hermes/.env.bak-<date>
cp -a ~/.hermes/profiles/default/.env ~/.hermes/profiles/default/.env.bak-<date>
```

After migrate and before gateway restart, diff backup against live (IDs only, never full secrets):

```bash
python3 - <<'PY'
import yaml
from pathlib import Path
def bot_id(s):
    s = (s or "").strip(); return s.split(":",1)[0] if s else ""
live = yaml.safe_load(Path.home().joinpath(".hermes/config.yaml").read_text())
print("version", live.get("_config_version"))
print("yaml_token_id", bot_id((live.get("gateway") or {}).get("telegram", {}).get("token")))
print("yaml_allowed", (live.get("telegram") or {}).get("allowed_chats"))
print("multiplex", (live.get("gateway") or {}).get("multiplex_profiles"))
PY
# Compare bot-id prefixes and allowlists from both .env files with YAML without printing full tokens.
```

Recovery rules after migrate:

- Poller must be the group admin bot (`TELEGRAM_BOT_TOKEN` / `863022…`). Set YAML `gateway.telegram.token` to the same ID; do not retain a second fallback bot.
- Effective `allowed_chats` must include the group. Prefer policy in YAML and remove `TELEGRAM_ALLOWED_CHATS` from `.env` (`.env` holds secrets). If retained, its CSV must include the group, or env-over-YAML will cut inbound again.
- Do not treat “restore defaults” as covering the telegram setup. Restore canonical topics with `restore_telegram_topics.sh apply`, not manually, subject to explicit authorization.
