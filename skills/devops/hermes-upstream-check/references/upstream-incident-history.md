# Incident history and pitfalls

These precedents date from 15–16.07 and 16.09.2026; current conditions are in SKILL.md. Do not automatically apply historical commands or authority.

1. **Check structural/path diff as well as content diff.** On 15.07.2026, `git diff`/`git merge-tree` showed no conflicts, but a modular test failed with `ModuleNotFoundError: No module named 'gateway.platforms.telegram'` after upstream moved the adapter to `plugins/platforms/telegram/adapter.py`. Include `git ls-tree -r <base> -- <dir>` vs `git ls-tree -r origin/main -- <dir>` (or `--find-renames`) for each affected directory, especially `gateway/platforms/`, `plugins/`, `agent/`.
2. **Require fresh explicit restart permission for a specific window on each attempt.** Do not carry permission over to another cycle. After an authorized restart and separately authorized live check, complete the post-FF group + DM, token and effective allowlist checklist before closing acceptance.
3. **Test `upstream_monitor.sh` changes without touching production state.** The script hardcodes `STATE=~/.hermes/upstream-monitor.json` and `REPO=~/hermes-agent`; do not run it directly for testing. Example isolation:
```bash
   rm -rf /tmp/hermes-agent-test && cp -r ~/hermes-agent /tmp/hermes-agent-test
   cd /tmp/hermes-agent-test && git checkout <some-sha-ahead> --quiet
   cp ~/.hermes/upstream-monitor.json /tmp/test-state.json
   sed "s|STATE=\"\$HOME/.hermes/upstream-monitor.json\"|STATE=\"/tmp/test-state.json\"|; \
        s|REPO=\"\$HOME/hermes-agent\"|REPO=\"/tmp/hermes-agent-test\"|" \
        ~/.hermes/scripts/upstream_monitor.sh > /tmp/test_monitor.sh
   bash /tmp/test_monitor.sh
   rm -rf /tmp/hermes-agent-test /tmp/test-state.json /tmp/test_monitor.sh
   ```
   Run at least two scenarios: no update (`last_sha` does not move), and simulated update (`last_sha` advances). Verify production `upstream-monitor.json` is unchanged.
4. **Use `hermes-skills-discovery` for third-party ecosystem skills** (skills.sh/GitHub/clawhub), not for updates of this repository.
5. **Measure ancestry and authorship before interpreting `hermes --version` `+N carried commits`.** The counter does not necessarily represent custom patches.

   > Context (RU): Прецедент 16.07.2026: версия показала «+13271 carried commits» (upstream `5f171e36`, local `03f8f5fe`); Саша спросил, нужны ли эти коммиты или уже неактуальны. Это оказалась история недавно влитого апстрима, а собственного авторства среди них были единицы — маркеры прогресса мерджа, не функциональный код.

```bash
   cd ~/hermes-agent
   git log <local_branch> --not origin/main --author="<our agent author name>" --oneline | wc -l   # actually ours
   git log <local_branch> --not origin/main --oneline | wc -l                                        # total "carried commits" count
   git merge-base --is-ancestor <REPO_BASE_from_version> <local_branch> && echo YES || echo NO       # is the upstream base actually merged?
   bash ~/.hermes/scripts/upstream_monitor.sh   # current diff from last_sha, usually orders of magnitude smaller than "carried commits"
   ```
   If the count is mostly recently merged upstream history, say so; the actual open question may concern only one or two commits above `last_sha` in `upstream-monitor.json`.
6. **Check effective allowlist before investigating forum/prune/multiplex.** On 16.09.2026 `.env` `TELEGRAM_ALLOWED_CHATS=400307920` overrode YAML `400307920,-1004300127777` after FF and restart. `extra_or_secret` precedence is env → YAML extra → default (`3dedb71f2f`, 13.09); DM bypassed group filtering, masking the failure. YAML-only review misses this regression.
7. **Compare bot-id prefixes from both sources after migrate.** YAML `gateway.telegram.token` is last-wins among blocks; runtime `_Cred` overwrites it with nonempty `TELEGRAM_BOT_TOKEN`. On 16.09 the poller used the group admin (`863022`), while YAML held `882117`, a bot outside the group; loss of env would switch the poller.
8. **Avoid diagnostic self-conflict.** Manual `getUpdates` on a live poller's token causes 409; the adapter restarts polling with `drop_pending_updates=True`, losing the queue. Do not use this to identify the poller. `TELEGRAM_ADDITIONAL_STARTUP_CHANNELS` is not an allowlist; cron outbound to a topic is not gateway inbound.
9. **Do not treat step 7 of `references/upstream-merge-steps.md` as delivery smoke.** `hermes doctor` / `status` / `cron list` check import/health. Follow the post-FF checklist in `post-ff-verification.md`; a DM alone does not exercise the group allowlist.
