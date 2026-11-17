# Profile routing (profile_routes + multiplex_profiles)

Follow [SKILL.md](../SKILL.md); Sasha decides on and performs gateway restarts from an external shell.

## Required flag: `gateway.multiplex_profiles: true`

`profile_routes` in `config.yaml` is ignored without `multiplex_profiles: true`. The gate in `gateway/run.py::_profile_name_for_source` returns `None` for every message:

```python
if not getattr(config, "multiplex_profiles", False):
    return None
```

Without the flag, messages go to the default profile even with correct `profile_routes`; the flag is not enabled by default and there is no error.

```yaml
gateway:
  multiplex_profiles: true   # Required for profile_routes
  profile_routes:
    - name: hermesdev-topic
      platform: telegram
      chat_id: '-1004300127777'
      thread_id: '4'
      profile: tz-dev
```

## Target profile requirements

1. The model must be set: `hermes profile list` shows `—` if absent. Use `hermes config set model <model> --profile <name>` or edit `~/.hermes/profiles/<name>/profile.yaml`.
2. The profile must exist on disk and appear in `hermes profile list`. Otherwise the gateway logs a warning and falls back to the default.
3. `multiplex_profiles` and `profile_routes` are read at startup, so changes require a restart. Sasha decides whether to restart and does it externally.

## Diagnosis

```bash
# 1. Check multiplex_profiles
python3 -c "import yaml; c=yaml.safe_load(open('~/.hermes/config.yaml'.replace('~',__import__('os').path.expanduser('~')))); print('multiplex_profiles:', c.get('gateway',{}).get('multiplex_profiles','NOT SET'))"

# 2. Check profile_routes
python3 -c "import yaml; c=yaml.safe_load(open('~/.hermes/config.yaml'.replace('~',__import__('os').path.expanduser('~')))); print('profile_routes:', c.get('gateway',{}).get('profile_routes','NOT SET'))"

# 3. Check that the profile and model exist
hermes profile list
```

On successful routing, the session key in `gateway.log` contains `agent:<profile>:telegram:...` instead of `agent:main:telegram:...`. If it remains `agent:main`, the flag may be unset or the gateway may not have been restarted.

## Existing sessions and `/new`

A topic may already have an active `default` session with `agent:main` from before `multiplex_profiles` was enabled. `/new` creates a new session for the new routing. The gateway does not switch the profile of existing sessions; routing applies to new incoming messages after a restart with `multiplex_profiles: true`.
