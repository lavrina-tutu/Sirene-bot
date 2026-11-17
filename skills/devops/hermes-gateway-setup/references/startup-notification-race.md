# Startup notification race

## Symptoms and diagnosis

After a restart, the gateway may be `active` and Telegram responsive while the home-channel message `♻️ Gateway online — Hermes is back and ready.` is missing. Search `~/.hermes/logs/gateway.log` during the first 1–2 seconds after `[Telegram] Connected`:

```bash
grep -n "startup notification\|send_path_degraded" ~/.hermes/logs/gateway.log | tail -5
```

`Home-channel startup notification failed for telegram:<id>: send_path_degraded` identifies this race.

`_send_home_channel_startup_notifications()` in gateway/run.py sends immediately after `✓ telegram connected`. Each new polling generation in `TelegramAdapter._begin_polling_generation()` in plugins/platforms/telegram/adapter.py sets `self._send_path_degraded = True` until the first successful `getUpdates`. If `adapter.send()` sees the flag, it returns `SendResult(success=False, error="send_path_degraded")` without an HTTP request; without a retry, the notification is lost.

To find when a flag appeared upstream:

```bash
cd ~/hermes-agent
git log -p -S'_send_path_degraded' --oneline | grep -E '^[0-9a-f]{7,}'   # commits changing the occurrence count
git log -p -1 <commit> -- path/to/file.py   # inspect the diff
```

`git log -S<string>` searches changes in the occurrence count of a string. After applying a fix, run the relevant tests on the actual target branch:

```bash
pytest tests/gateway/test_telegram_startup_notification_retry.py tests/gateway/test_telegram_send_path_health.py -x -q
```

A code change on disk requires a gateway restart to take effect. Sasha decides whether to restart and performs it from an external shell; the Linux command is `systemctl --user restart hermes-gateway`. Do not restart the gateway from an agent or cron job.

`gh` authorization may not persist across cron sessions: `gh auth status` can report "not logged into any GitHub hosts" even after `gh auth login --with-token` in an earlier session. Verify authorization for the actual execution environment; use an appropriately provisioned separate skill-specific credential or have the user open the PR manually. Do not put tokens in prompts or documentation.

## Historical context

Upstream commit `b8295cf6f7` ("fix(telegram): gate polling health on getUpdates progress", 13.07.2026) introduced the race. The health flag itself protects against sends during unhealthy polling.

As of 16.07.2026, the decision was to use both a local patch and an upstream PR; the local patch was committed and working, while the PR had not yet been opened. Diagnosis, fix, tests and a push were delegated to an Opus cron job (`enabled_toolsets: [terminal, file]`) on a fork's `fix/<topic>` branch based on clean `main`, separate from `_test-cutover`.

The fix used `_send_with_polling_settle()` around `adapter.send()`: when `SendResult` has `retryable=True`, it waits for polling progress with `asyncio.wait_for(progress.wait(), timeout=15.0)` and retries `send()` once. The feature commit was transferred using `git cherry-pick -x <sha>`, specifically `git checkout _test-cutover && git cherry-pick -x <commit_sha>`; `-x` records the source commit. The merge reported `Auto-merging gateway/run.py` without conflicts, followed by tests on the target branch.

A subsequent cron session lacked the previous `gh` login and could not find the earlier `HERMES_SKILLS_DIGEST_GH_TOKEN` credential. Authorization in one session is not proof of authorization in another.
