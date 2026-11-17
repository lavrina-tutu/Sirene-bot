# Model and reasoning verification

Historical example from 13–14.08.2026. Check current code/API for model support, parameters, and per-cron effort. Do not send an external request without authorization.

## Model unavailable for API key (HTTP 400)

For an agent cron failing with `RuntimeError: HTTP 400: model "<name>" is not allowed for this API key`, inspect `model` and `provider` in `jobs.json`. Within authorized change scope, the historical fix used `hermes cron edit <id> --model <available_model> --provider <provider>`. The subcommand is `edit`, not `update` (the source lists `list|create|add|edit|pause|resume|run|remove|rm|delete|status|runs|history|notepad|tick`; verify current CLI).

Do not append a thinking level to the model slug: `deepseek/deepseek-v4-pro-low` is a mistaken combination, while `deepseek/deepseek-v4-pro` is the model and `reasoning_effort` is a separate parameter. The incorrect slug historically caused this HTTP 400.

## Historical reasoning configuration

The source listed levels `none | minimal | low | medium | high | xhigh | max | ultra`, configured in `config.yaml` via global `agent.reasoning_effort` or per-model `agent.reasoning_overrides: {model: level}`. It described the gateway payload as `reasoning: {enabled: true, effort: <level>}` and model-based resolution via `resolve_reasoning_config(cfg, model)` in `cron/scheduler.py`. At that time it claimed there was no per-cron setting in cronjob, `hermes cron edit` (only `--model`/`--provider`), or the `cron:` config section. Confirm these claims in the current code/API.

Under those historical constraints, lowering reasoning globally or per model also affected chat using that model; isolation required a different cron model, such as `google/gemini-2.5-flash-lite` for backlog-analyst. Verify current options before applying this conclusion.

> Context (RU): Прецедент 13–14.08.2026 — `backlog-collector` падал из-за `deepseek-v4-pro-low`. Живой curl к gateway: `deepseek/deepseek-v4-pro` + `reasoning: {enabled:true, effort:"low"}` → 200; `deepseek-v4-pro-low` → 400 «model not allowed».
