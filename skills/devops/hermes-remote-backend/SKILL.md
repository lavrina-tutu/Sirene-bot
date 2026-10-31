---
name: hermes-remote-backend
description: "Remote Hermes Desktop connection via hermes serve."
version: 1.0.0
author: agent
tags: [hermes, serve, dashboard, remote, desktop, backend, nftables, systemd, auth]
platforms: [linux]
---

# Hermes Remote Backend (hermes serve)

When the user wants to use **Hermes Desktop on another machine** (e.g. a Windows
laptop) against the Hermes agent that actually lives on this Linux VM
(sessions, memory, skills, crons, project files), you stand up a
`hermes serve` backend on the VM and point the Desktop app at it. Verified
end-to-end on `hermes-agents.devel.tutu.ru` under Hermes v0.20.0 (2026-08-14).

This is a DIFFERENT process from the messaging **gateway** (Telegram/Discord/…).
The desktop backend and the messaging gateway run independently.

## Triggers
- "connect Desktop to the Hermes on the VM / remotely"
- "remote gateway / remote backend / hermes serve / dashboard"
- Hermes Desktop on a laptop showing the local agent instead of the VM agent

## Key mental model
- Hermes Desktop by default starts its OWN local agent. To use the VM's agent,
  point the app at the VM's `hermes serve` backend instead (Settings → Gateway →
  Remote gateway → URL + sign in).
- `hermes serve` = dashboard/JSON-RPC/WebSocket backend (port 9119 default).
  `hermes dashboard` = same backend + browser UI.
- The remote backend reads/writes `~/.hermes/.env` (API keys) and can run
  commands — security is the primary consideration (auth + firewall scope).
- The backend must be UP and reachable; Desktop does not start it for you.
  Run under systemd/tmux. Non-loopback `--host` auto-engages the auth gate.

## Auth provider choice
- **username/password (basic)** — trusted network only (corp VPN / Tailscale).
  Single shared credential. Do NOT expose to public internet.
- **OAuth (Nous Portal)** — anything reachable beyond own machine.
  Register with `hermes dashboard register`, sign in via Nous Research.

## Verified setup (username/password path)

### 1. Credentials in `~/.hermes/.env` (chmod 600)
```
HERMES_DASHBOARD_BASIC_AUTH_USERNAME=admin
HERMES_DASHBOARD_BASIC_AUTH_PASSWORD=<strong>
HERMES_DASHBOARD_BASIC_AUTH_SECRET=$(openssl rand -base64 32)
```
`SECRET` = stable session-signing key; without it you get logged out on every
backend restart. Backup `.env` before editing.
> Pitfall: `.env` may contain `%` — a bash one-liner with unescaped `%` can trip
> the command blocklist. Append via a small python script (or `openssl rand` for
> SECRET). Let the systemd unit read secrets via `EnvironmentFile=%h/.hermes/.env`.

### 2. Pre-build web UI for `--skip-build`
`hermes serve` in non-interactive (systemd) context should run with
`--skip-build`, which needs an existing build (absent on a fresh git-install):
```bash
cd ~/hermes-agent/web && npm install --no-audit --no-fund && npm run build
# output lands in hermes_cli/web_dist/ — check "web_dist PRESENT"
```
Run build in background with notify (~1-2 min).

### 3. systemd user unit `~/.config/systemd/user/hermes-serve.service`
```ini
[Unit]
Description=Hermes Dashboard backend (hermes serve) - remote desktop access
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
EnvironmentFile=%h/.hermes/.env
ExecStart=%h/hermes-agent/.venv/bin/hermes serve --host 0.0.0.0 --port 9119 --skip-build
Restart=on-failure
RestartSec=5

[Install]
WantedBy=default.target
```
```bash
systemctl --user daemon-reload
systemctl --user enable --now hermes-serve.service
systemctl --user status hermes-serve.service --no-pager
ss -tlnp | grep 9119   # LISTEN 0.0.0.0:9119
```

### 4. nftables lockdown — restrict 9119 to the trusted range
`/etc/nftables.conf` (no default-drop on other traffic):
```
table inet hermes_dash {
    chain input {
        type filter hook input priority filter; policy accept;
        iif lo accept
        ip saddr 10.254.0.0/16 tcp dport 9119 accept
        tcp dport 9119 reject with icmp port-unreachable
    }
}
```
```bash
sudo install -m 644 /tmp/conf /etc/nftables.conf
sudo systemctl enable nftables
sudo nft -f /etc/nftables.conf
```

> **Pitfall: `nft -f` APPENDS to the running table — it does NOT replace.**
> On reload, without deleting the table first, the old (stale) `reject` line
> masks the `iif lo accept` you added. Always:
> `sudo nft delete table inet hermes_dash 2>/dev/null; sudo nft -f /etc/nftables.conf`
> then `sudo nft list table inet hermes_dash` to verify the clean result.
>
> **Pitfall: an allow-only rule that forgets loopback makes 127.0.0.1:9119 refuse.**
> Include `iif lo accept` FIRST in the chain or local curl checks fail.

## Verification
```bash
curl -s http://127.0.0.1:9119/api/status | python3 -m json.tool
# want: auth_required true, auth_providers ["basic"], auth_flows ["cookie"],
#       gateway_running + gateway_state present (independent process)
```
Auth (cookie flow — NOT basic-auth header):
```bash
curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:9119/api/sessions   # 401 unauth
curl -s -c cookies.txt -X POST http://127.0.0.1:9119/auth/password-login \
  -H 'Content-Type: application/json' \
  -d '{"provider":"basic","username":"admin","password":"<pw>"}'            # 200 ok:true
curl -s -b cookies.txt -o /dev/null -w "%{http_code}\n" http://127.0.0.1:9119/api/sessions  # 200
```
> The login route is `/auth/password-login` (POST JSON, field `provider` REQUIRED).
> `/api/login` and bare `/auth/login` POST return 401/405/422 — not the path.

## Desktop side (Windows laptop)
1. Install Hermes Desktop (`hermes desktop` or installer from docs).
2. Settings → Gateway → **Remote gateway**.
3. Remote URL: `http://<host>:9119` (hostname fine, e.g. `http://hermes-agents.devel.tutu.ru:9119`).
4. Sign in → Save and reconnect.
Sessions survive restarts only when `HERMES_DASHBOARD_BASIC_AUTH_SECRET` is set.

## Client-side reachability (laptop / git-bash)
- `ping -n 1 hermes-agents.devel.tutu.ru` confirms hostname→VM.
- Before serve is up, curl to 9119 = **connection refused** — expected. After
  serve+firewall, curl returns JSON.
- `ss` does **not** exist in git-bash (Windows). Run it on the Linux VM.