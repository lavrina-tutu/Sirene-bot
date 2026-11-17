

## Historical source (superseded where it conflicts with SKILL.md; not current instruction)

## Headless VM: non-interactive login

On a server/VM (no browser, e.g. for pipeline roles) the browser OAuth flow
(`codex login` → localhost:1455) does not apply. Auth options, mutually
exclusive by billing/model set:

| Method | Command | Best for |
|---|---|---|
| ChatGPT Business/Enterprise access token | `printenv CODEX_ACCESS_TOKEN \| codex login --with-access-token` | automation, no browser; workspace identity |
| Device code (beta) | `codex login --device-auth` | SSH user with TTY; requires admin "Enable device code" |
| Platform API key | `printenv OPENAI_API_KEY \| codex login --with-api-key` | API-key billing; **different model catalog** than ChatGPT login |
| Copy `~/.codex/auth.json` | `scp` from a browser machine | quickest; file = password |

`~/.codex/auth.json` is plaintext **or** OS keyring; on a Linux VM without a
keyring set `cli_auth_credentials_store = "file"`. Verify with `codex login
status`. Admins may need Codex Local + token/device-code toggles enabled; on
Enterprise/Edu GPT-6.1 Sol is off by default.

### config.toml pitfalls (headless login)

For the file credential store, `cli_auth_credentials_store = "file"` must be a
**top-level** key — putting it inside a `[cli_auth]` section makes `codex login`
fail with `invalid type: map, expected a string`. Same rule for a `[model]`
section: bare `model = "gpt-6.1-sol"` is what the loader expects; a
`[model] model = "…"` section also trips the same error. When smoke-failing on
config syntax, strip the config down to the single top-level credential key and
drive the model via the `-m` flag on `codex exec` rather than fighting the
loader. `[approval_policy] mode = "…"` as a map is likewise rejected — a plain
top-level string is the accepted shape.

### Device-code flow (headless, no token yet)

`codex login --device-auth` is interactive: it prints a URL (`.../codex/device`)
and a one-time code, then waits. Run it as a background PTY process
(`terminal(..., background=true, pty=true)`), then read the code back from
`process(action="log")` and relay it to the user to type into the browser
(valid ~15 min). During Art, poll/log again to confirm the session completed
before `codex login status` / smoke. Confirming from a code shown by the device
auth is exactly what the CLI instructs; the code is long-lived enough to pass
to the user, never a real password.
