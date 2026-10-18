---
name: workvault-sync-infra
description: "Inbox: итоги и решения из стенограммы"
version: 1.0.1
author: agent
license: MIT
platforms: [linux]
metadata:
  hermes:
    tags: [WorkVault, rclone, systemd, ownCloud, Inbox, sync]
    related_skills: [obsidian, tz-workflow]
---

# WorkVault Sync Infrastructure (VM)

WorkVault lives on ownCloud and is mirrored to the VM (`~/WorkVault`) via two independent systemd user timers with **different sync directions** — conflating them is the recurring failure mode.

## ⚠️ NEVER hand-type `rclone sync` for WorkVault — data-loss incident 15.07.2026

**Rule: to sync WorkVault, always trigger the existing systemd service — never invoke `rclone sync` directly with your own `--exclude` flags.**

```bash
systemctl --user start owncloud-sync.service
```

**What went wrong (15.07.2026):** the agent ran `rclone sync ~/WorkVault owncloud:WorkVault --exclude ".obsidian/**" --exclude "WorkVault_backup/**"` by hand instead of using the service, without first reading this skill. `rclone sync` is bidirectional-with-deletion: any cloud folder not present locally (or not covered by the exclude list) gets deleted. The hand-rolled exclude list was missing `Inbox/**` and other real entries from `~/.config/rclone/workvault-exclude.lst` — result: 164 files / 17 directories deleted on the ownCloud side (`Hermes-Backlog/_Done`, `Hermes-Backlog/MigrationToVM`, `Tools/AggregateFromMeetings/_archive`, parts of `Inbox/personal-ai-assistant-master`). Partial recovery was possible from `~/WorkVault_backup` (a stale, non-synced local mirror) but some files (Inbox subtree) had no backup at all.

**Why the service call is safe and the hand-typed command is not:**
- The service's `ExecStart` already points at `--exclude-from=~/.config/rclone/workvault-exclude.lst` — the real, maintained exclude list, kept in sync with what the Inbox pull-timer manages.
- A hand-typed `--exclude` list is always a guess reconstructed from memory — it will miss entries (as it did here) and `rclone sync`'s destructive side runs before anyone notices.
- If you need a one-off / immediate sync (not waiting for the timer), `systemctl --user start owncloud-sync.service` runs the exact same job on demand — there is no manual-rclone use case this doesn't cover.

**If you ever think you need to run `rclone sync` with custom flags for WorkVault: stop, that is the signal you haven't read this skill yet.** Read it, use the service call, or if a genuinely new one-off sync scenario is needed, get explicit confirmation from Sasha before running anything destructive against the cloud copy.

**Recovery path if a destructive sync already happened:** rclone's WebDAV backend against ownCloud does NOT support `CleanUp`/trash (`rclone backend features owncloud:` → `"CleanUp": false`) — you cannot restore deleted files via rclone itself. Options, in order: (1) ownCloud's own web UI trash (Files → Deleted files) — usually the most complete, needs Sasha's login, not the rclone technical account; (2) `~/WorkVault_backup` — a separate, NOT-synced local mirror that may hold stale-but-recoverable copies of some paths; (3) accept partial loss for anything not covered by either.

## Overview

Two services, two different semantics:

| Timer | Direction | Command | Purpose |
|---|---|---|---|
| `owncloud-sync.timer` → `.service` | Bidirectional `rclone sync ~/WorkVault owncloud:WorkVault` | Push local WorkVault changes to cloud, pull cloud changes locally | General vault content |
| `owncloud-inbox-pull.timer` → `.service` | One-way `rclone copy owncloud:WorkVault/Inbox ~/WorkVault/Inbox` | Pull-only, every ~10min | Laptop→VM intake drop folder |

`rclone copy` (inbox-pull) never deletes destination files even if the source changes/disappears — durable one-way landing zone. `rclone sync` (main sync) is destructive both ways — that's why `Inbox/**` is explicitly excluded from it (see below), otherwise the bidirectional sync would fight the pull timer over the same folder.

## When to Use

- User reports a file dropped into WorkVault/Inbox from the laptop never showed up on the VM
- Diagnosing "two Inbox folders" or any duplicate-folder confusion in WorkVault
- Setting up or modifying the Inbox intake mechanism
- Any question about how WorkVault stays in sync between laptop and VM

## Config Files (must stay consistent with each other)

- `~/.config/systemd/user/owncloud-sync.service` — main bidirectional sync, `--exclude-from=~/.config/rclone/workvault-exclude.lst`
- `~/.config/systemd/user/owncloud-inbox-pull.service` — `ExecStart` hardcodes the cloud source path, e.g. `rclone copy "owncloud:WorkVault/Inbox" ~/WorkVault/Inbox`
- `~/.config/rclone/workvault-exclude.lst` — must contain `Inbox/**` so the main sync never touches what the pull timer manages

**Hard rule: exactly one `Inbox` folder, both locally and in the cloud.** Never create a second/alternate Inbox (e.g. differently-named) without the user's explicit decision — a duplicate-Inbox incident happened and was cleaned up on 13.07.2026 (a stale/near-empty cloud folder with a different name had drifted into the pull-timer's `ExecStart`, while the real, actively-edited folder sat un-pulled).

## Diagnostic Pattern

1. **Confirm the cloud side has exactly one folder:**
   ```bash
   source ~/USERTOOLS/ConfluenceSync/.env   # rclone owncloud creds
   rclone lsf owncloud:WorkVault --dirs-only | grep -i inbox
   ```
   If this returns more than one Inbox-like name, that's the bug — one of them is stale/orphaned.

2. **Compare against what the pull service actually points at:**
   ```bash
   systemctl --user cat owncloud-inbox-pull.service | grep ExecStart
   ```
   The path inside must match exactly the one true cloud folder from step 1.

3. **Check for silent failures in the pull log** (a mismatched folder name fails quietly every ~10min without alerting anyone):
   ```bash
   tail -30 ~/.local/share/hermes/logs/owncloud-inbox-pull.log
   # Look for: "directory not found" repeated on every cycle
   ```

4. **Fix:** point `ExecStart` in the `.service` file at the correct folder name (`patch`), remove the matching stale exclude-list line if present, `rclone purge` the orphaned cloud folder, then:
   ```bash
   systemctl --user daemon-reload
   systemctl --user start owncloud-inbox-pull.service   # run once now, don't wait for the next timer tick
   tail -10 ~/.local/share/hermes/logs/owncloud-inbox-pull.log   # confirm status=0/SUCCESS, no "directory not found"
   ```
   Also diff the freshly-pulled local file content against what you expect (e.g. the newest edit on the cloud side) to confirm the fix actually pulled the *right* source, not just that the command exited 0.

## ownCloud WebDAV filename byte-limit is LOWER than the local filesystem limit

The main `owncloud-sync.timer` (bidirectional `rclone sync`) can fail with:
```
Failed to copy: unchunked simple update failed: File name is too long.:
OCA\DAV\Connector\Sabre\Exception\FileNameTooLong: 400 Bad Request
```
even when the file is perfectly legal on the VM's local filesystem. **Do not trust the local FS limit (XFS/ext4/btrfs `Namelen=255`) as the sync-safe limit** — the ownCloud WebDAV server enforces its own, much lower and less predictable ceiling. Confirmed empirically (13.07.2026, incident originated in MoveFromFF's Cyrillic meeting-title filenames): server accepted up to ~220 bytes reliably, 224–228 bytes was an unstable border, and ≥229–230 bytes reliably threw `FileNameTooLong`. The instability itself is a clue the server is likely counting something beyond the raw basename (full path, DB row constraint, URL-encoded form) — don't tune a fix to sit right at the empirical edge.

**Diagnostic technique — binary-search the real limit directly against the live server**, don't guess from docs or the local FS `stat -f` output:
```bash
mkdir -p /tmp/oc_test && cd /tmp/oc_test
python3 -c "
import subprocess, os
def try_len(total_bytes):
    suffix = '.md'; name = 'Z'
    while len((name+suffix).encode('utf-8')) < total_bytes: name += 'ы'
    while len((name+suffix).encode('utf-8')) > total_bytes: name = name[:-1]
    fname = name + suffix
    with open(fname, 'w') as f: f.write('test')
    r = subprocess.run(['rclone', 'copyto', fname, f'owncloud:WorkVault/_test/{fname}'], capture_output=True, text=True, timeout=30)
    os.remove(fname)
    return len(fname.encode('utf-8')), r.returncode == 0
for tb in [200, 220, 224, 228, 230, 240]:
    print(try_len(tb))
"
rclone purge owncloud:WorkVault/_test/   # always clean up test folder afterward
```
Any tool that constructs filenames destined for this sync (MoveFromFF, ProtocolFromSummary, any future WorkVault-writing USERTOOLS instrument) must budget for a byte-length safety margin well below the unstable 224–230 zone — e.g. cap at ~180 bytes, not 255. Apply the fix at the filename-construction layer (truncate on a UTF-8 char boundary, never mid-character), and re-verify with a real `rclone copyto` of the newly-generated name before considering the fix done — a passing local unit test is not proof the server will accept it.

## Common Pitfalls

1. **Assuming the local `WorkVault/Inbox` directory is authoritative for "which folder is correct".** The local folder is just whatever the pull timer last copied — if it's pointed at the wrong/stale cloud folder, the local copy will look plausible (has files, has a README) while silently missing the user's actual recent edits. Always verify against the cloud side (`rclone lsf`) and the service's `ExecStart`, not just "does the local folder have stuff in it".
2. **Forgetting to update the exclude-list when renaming/removing a cloud folder.** If the exclude list still references a folder name that no longer exists, that's harmless (rclone just doesn't match anything), but it's dead config — clean it up in the same edit so future readers don't chase a phantom reference.
3. **Not verifying end-to-end after a fix.** `systemctl daemon-reload` alone doesn't prove the fix works — the `.service` unit file is only re-read on next invocation. Always follow with a manual `systemctl --user start <service>` + log tail + content diff before considering the fix done.

## Verification Checklist

- [ ] `rclone lsf owncloud:WorkVault --dirs-only | grep -i inbox` returns exactly one folder
- [ ] `owncloud-inbox-pull.service` `ExecStart` path matches that one folder exactly
- [ ] `workvault-exclude.lst` has no stale/orphaned folder-name entries
- [ ] Manual service run confirms `status=0/SUCCESS` and no `directory not found` in the log
- [ ] Local file content matches the expected latest cloud edit (not just "a file exists")
- [ ] Any orphaned cloud folder removed (`rclone purge`) only after confirming it's genuinely unused
