---
name: openclaw-provider-onboarding
description: Configure and verify OpenClaw model providers from API keys, discover accessible models, keep only verified working models, and update agents.defaults.models so chat surfaces like Telegram /models can switch to them. Use when onboarding a new provider, auditing which models a key really supports, pruning noisy provider catalogs, rebuilding chat-visible model allowlists, or safely rolling back failed provider integrations.
---

# OpenClaw Provider Onboarding

Onboard model providers into OpenClaw without hand-editing giant config blobs or trusting provider catalogs blindly.

Use this skill for two jobs:

1. **Onboard a new provider from API credentials**
2. **Rebuild or prune chat-visible model allowlists from real availability**

## Core workflow

When a user gives a provider name, base URL, and API key, do this:

1. Discover candidate models from the provider `/models` endpoint when possible, or accept a user-supplied model list.
2. Detect API style automatically when needed.
3. Use layered probing instead of hammering every model.
4. Write a temporary provider config into OpenClaw.
5. Let OpenClaw resolve which models are actually `available=true`.
6. Keep only verified models.
7. Update `agents.defaults.models` so `/models` in Telegram can switch to them.
8. Apply merge or replacement strategy.
9. Roll back automatically if onboarding fails after config was applied.

## Rules

- Do not trust provider marketing lists alone.
- Do not expose a model in `agents.defaults.models` unless it resolves as usable.
- Prefer conservative or balanced probing for unknown relays.
- Avoid flooding relays with full-model direct probes unless the user explicitly wants that.
- Preserve the existing default model unless the user asks to change it.

## Scripts

### `scripts/onboard_provider.py`

Main entrypoint for provider onboarding.

Capabilities:

- discover candidate models from `/models` or user-supplied IDs
- auto-detect `openai-responses` vs `openai-completions`
- use layered probe modes: `none`, `sample`, `all`
- rotate stealth probe templates to avoid one obvious fingerprint
- apply provider intensity profiles: `conservative`, `balanced`, `aggressive`
- rank and prune verified models so the final allowlist stays human-sized
- update `agents.defaults.models` with `merge`, `replace-provider`, or `replace-all`
- write JSON onboarding reports
- auto-rollback on failed apply

Recommended command:

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

Arguments:

- `--provider <name>` required
- `--base-url <url>` required
- `--api-key <key>` required
- `--api-style openai-completions|openai-responses` optional when `--auto-detect-api-style` is used
- `--models <id1,id2,...>` optional
- `--models-file <path>` optional newline-delimited list
- `--list-endpoint` discover candidates via provider `/models`
- `--auto-detect-api-style` try both API styles automatically
- `--profile conservative|balanced|aggressive`
- `--probe none|sample|all`
- `--probe-template strict-ok|json-ack|classify|extract|summarize|rotate`
- `--probe-delay-ms <n>` delay between direct probes
- `--probe-max-failures <n>` circuit-break after repeated failures
- `--max-models <n>` keep only the top-ranked verified models
- `--strategy merge|replace-provider|replace-all`
- `--primary <provider/model>` optional
- `--rollback-on-fail` restore previous config on failed apply
- `--report-file <path>` write onboarding report JSON
- `--apply` actually patch config and restart OpenClaw

## Secondary scripts

### `scripts/provider_model_probe.py`

Build a provider patch preview from a provider key and candidate model list.

Use when you want a lightweight preflight before full onboarding.

### `scripts/sync_model_allowlist.py`

Rebuild `agents.defaults.models` from currently available models.

Use when `/models` visibility drifted from the real provider state and only the allowlist needs repair.
