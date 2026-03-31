# openclaw-provider-onboarding

> Safe provider onboarding and model allowlist sync for OpenClaw.

[![Release](https://img.shields.io/github/v/release/Bardlu023/openclaw-provider-onboarding)](https://github.com/Bardlu023/openclaw-provider-onboarding/releases)
[![License](https://img.shields.io/badge/license-skill-informational)](https://github.com/Bardlu023/openclaw-provider-onboarding)
[![OpenClaw](https://img.shields.io/badge/OpenClaw-skill-blue)](https://github.com/Bardlu023/openclaw-provider-onboarding)

## English

`openclaw-provider-onboarding` helps OpenClaw integrate third-party model providers without blindly trusting provider catalogs.

It can:

- discover candidate models from a provider `/models` endpoint or a supplied model list
- detect whether a provider speaks `openai-responses` or `openai-completions`
- use layered probing instead of hammering every candidate model
- verify which models actually become usable inside OpenClaw
- prune noisy model catalogs into a smaller, human-usable allowlist
- update `agents.defaults.models` so surfaces like Telegram `/models` can switch to verified models
- roll back automatically if provider onboarding fails after apply

### Included scripts

- `scripts/onboard_provider.py`  
  Full provider onboarding flow with probing, pruning, allowlist sync, and rollback.

- `scripts/provider_model_probe.py`  
  Lightweight provider preflight for candidate model discovery and patch preview.

- `scripts/sync_model_allowlist.py`  
  Rebuild `agents.defaults.models` from the models OpenClaw currently resolves as available.

### Recommended use case

Use this skill when you want to give OpenClaw a new provider API key and have it:

1. figure out what the key can access
2. keep only the models that actually work
3. expose those models cleanly in chat model pickers

### Example

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

### Why this exists

Provider catalogs are often noisy, stale, or optimistic. OpenClaw chat pickers also become unpleasant when every possible model is dumped into `/models`.

This skill solves that by treating real usability as the source of truth, then syncing OpenClaw’s visible model set to match.

---

## 中文

`openclaw-provider-onboarding` 用来把第三方模型 provider 更稳地接进 OpenClaw，而不是盲信 provider 自己的模型列表。

它可以：

- 从 provider 的 `/models` 接口或手工候选列表发现模型
- 自动判断 provider 使用的是 `openai-responses` 还是 `openai-completions`
- 使用分层测活，而不是对所有候选模型暴力轰炸
- 验证哪些模型在 OpenClaw 里真的可用
- 把嘈杂的模型目录裁剪成更适合人类使用的 allowlist
- 更新 `agents.defaults.models`，让 Telegram 等聊天界面的 `/models` 可以切换到这些已验证模型
- 如果接入失败，自动回滚配置

### 包含的脚本

- `scripts/onboard_provider.py`  
  完整接入流程：探测、裁剪、同步 allowlist、失败回滚。

- `scripts/provider_model_probe.py`  
  轻量预探测脚本，用来预览 provider patch 和候选模型。

- `scripts/sync_model_allowlist.py`  
  根据 OpenClaw 当前真正可用的模型，重建 `agents.defaults.models`。

### 适合什么场景

当你想给 OpenClaw 塞一个新的 provider API key，并希望它能够：

1. 自动判断这个 key 能访问哪些模型
2. 只保留真正能用的模型
3. 在聊天端以干净可切换的方式暴露这些模型

### 示例命令

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

### 为什么需要这个 skill

很多 provider 的模型目录都很吵、很旧，甚至带点“理论支持但实际不可用”的味道。另一方面，如果把所有模型都直接扔进 OpenClaw 的 `/models`，聊天端体验会迅速变成垃圾场。

这个 skill 的价值就在于：
**把“真实可用性”当作唯一可信来源，然后把 OpenClaw 的可见模型集合同步到这个事实。**
