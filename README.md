# openclaw-provider-onboarding

Onboard and verify OpenClaw model providers from API keys, keep only working models, and sync chat-visible model allowlists safely.

## What this skill does

This skill helps OpenClaw integrate third-party model providers without blindly trusting provider catalogs.

It can:

- discover candidate models from a provider `/models` endpoint or a supplied model list
- detect whether a provider speaks `openai-responses` or `openai-completions`
- use layered probing instead of hammering every candidate model
- verify which models actually become usable inside OpenClaw
- prune noisy model catalogs into a smaller, human-usable allowlist
- update `agents.defaults.models` so surfaces like Telegram `/models` can switch to verified models
- roll back automatically if provider onboarding fails after apply

## Included scripts

- `scripts/onboard_provider.py`  
  Full provider onboarding flow with probing, pruning, allowlist sync, and rollback.

- `scripts/provider_model_probe.py`  
  Lightweight provider preflight for candidate model discovery and patch preview.

- `scripts/sync_model_allowlist.py`  
  Rebuild `agents.defaults.models` from the models OpenClaw currently resolves as available.

## Recommended use case

Use this skill when you want to give OpenClaw a new provider API key and have it:

1. figure out what the key can access
2. keep only the models that actually work
3. expose those models cleanly in chat model pickers

## Example

```powershell
python scripts/onboard_provider.py \
  --provider myproxy \
  --base-url https://example.com/v1 \
  --api-key sk-xxx \
  --list-endpoint \
  --auto-detect-api-style \
  --profile balanced \
  --probe-template rotate \
  --max-models 20 \
  --strategy replace-provider \
  --rollback-on-fail \
  --report-file out/myproxy-report.json \
  --apply
```

## Why this exists

Provider catalogs are often noisy, stale, or optimistic. OpenClaw chat pickers also become unpleasant when every possible model is dumped into `/models`.

This skill solves that by treating real usability as the source of truth, then syncing OpenClaw’s visible model set to match.
