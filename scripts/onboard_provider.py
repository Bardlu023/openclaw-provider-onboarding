#!/usr/bin/env python3
import argparse
import json
import subprocess
import time
import urllib.request
from pathlib import Path

WORKSPACE = Path(r"C:\Users\严志飞\.openclaw\workspace")
OPENCLAW_CONFIG = Path(r"C:\Users\严志飞\.openclaw\openclaw.json")
PROBE_TEMPLATES = {
    "strict-ok": "Return exactly: ok",
    "json-ack": 'Return JSON only: {"ok":true}',
    "classify": "Classify this token as alpha or numeric: 7b",
    "extract": "Extract the single English word from: [signal]",
    "summarize": "Summarize in one lowercase word: stable",
}
PROFILES = {
    "conservative": {"probe": "none", "probe_template": "rotate", "probe_delay_ms": 1500, "probe_max_failures": 1, "max_models": 12},
    "balanced": {"probe": "sample", "probe_template": "rotate", "probe_delay_ms": 1200, "probe_max_failures": 2, "max_models": 20},
    "aggressive": {"probe": "all", "probe_template": "rotate", "probe_delay_ms": 800, "probe_max_failures": 3, "max_models": 50},
}
PREFERRED_MODEL_PATTERNS = [
    "gpt-5.4",
    "gpt-5.3-codex",
    "gpt-5.2-codex",
    "gpt-5",
    "claude-sonnet",
    "claude-opus",
    "claude-haiku",
    "gemini",
    "grok",
    "coder",
    "glm",
    "kimi",
    "deepseek",
]


def run(cmd):
    p = subprocess.run(cmd, cwd=str(WORKSPACE), capture_output=True, text=True, shell=True)
    return p.returncode, p.stdout, p.stderr


def parse_json_with_plugin_noise(raw: str):
    lines = [line for line in raw.splitlines() if not line.startswith("[plugins]")]
    text = "\n".join(lines).strip()
    if not text:
        raise RuntimeError("empty JSON payload")
    return json.loads(text)


def fetch_json(url: str, api_key: str):
    req = urllib.request.Request(url)
    req.add_header("Authorization", f"Bearer {api_key}")
    req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def fetch_post_json(url: str, api_key: str, payload: dict):
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=body, method="POST")
    req.add_header("Authorization", f"Bearer {api_key}")
    req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req, timeout=45) as resp:
        return resp.status, resp.read().decode("utf-8", errors="replace")


def discover_models(base_url: str, api_key: str):
    data = fetch_json(base_url.rstrip("/") + "/models", api_key)
    out = []
    for item in data.get("data", []):
        mid = item.get("id")
        if mid:
            out.append(mid)
    return sorted(dict.fromkeys(out))


def read_models_file(path: str):
    xs = []
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            xs.append(line)
    return xs


def build_provider_models(api_style: str, models: list[str]):
    return [
        {
            "id": m,
            "name": m,
            "api": api_style,
            "reasoning": False,
            "input": ["text"],
            "cost": {"input": 0, "output": 0, "cacheRead": 0, "cacheWrite": 0},
            "contextWindow": 200000,
            "maxTokens": 8192,
        }
        for m in models
    ]


def build_provider_patch(provider: str, base_url: str, api_style: str, api_key: str, models: list[str]):
    return {
        "models": {
            "providers": {
                provider: {
                    "baseUrl": base_url,
                    "apiKey": api_key,
                    "api": api_style,
                    "models": build_provider_models(api_style, models),
                }
            }
        }
    }


def apply_patch(patch: dict, note: str):
    raw = json.dumps(patch, ensure_ascii=False)
    cmd = ["openclaw", "gateway", "config.patch", "--raw", raw, "--note", note]
    code, out, err = run(cmd)
    if code != 0:
        raise RuntimeError(err or out)
    return out


def load_config():
    return json.loads(OPENCLAW_CONFIG.read_text(encoding="utf-8"))


def save_report(path: str | None, result: dict):
    if path:
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        Path(path).write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")


def list_available_for_provider(provider: str):
    code, out, err = run(["openclaw", "models", "list", "--all", "--json"])
    if code != 0:
        raise RuntimeError(err or out)
    data = parse_json_with_plugin_noise(out)
    avail = []
    for m in data.get("models", []):
        key = m.get("key")
        if not key or not key.startswith(provider + "/"):
            continue
        if m.get("available"):
            avail.append(key)
    return sorted(dict.fromkeys(avail))


def pick_probe_prompt(template_name: str, idx: int):
    if template_name == "rotate":
        names = sorted(PROBE_TEMPLATES.keys())
        name = names[idx % len(names)]
        return name, PROBE_TEMPLATES[name]
    if template_name in PROBE_TEMPLATES:
        return template_name, PROBE_TEMPLATES[template_name]
    return "strict-ok", PROBE_TEMPLATES["strict-ok"]


def probe_model_direct(base_url: str, api_key: str, api_style: str, model_id: str, prompt: str):
    if api_style == "openai-responses":
        url = base_url.rstrip("/") + "/responses"
        payload = {"model": model_id, "input": prompt, "max_output_tokens": 6}
    else:
        url = base_url.rstrip("/") + "/chat/completions"
        payload = {
            "model": model_id,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 6,
            "temperature": 0,
        }
    try:
        status, body = fetch_post_json(url, api_key, payload)
        ok = 200 <= status < 300
        return {"ok": ok, "status": status, "bodyPreview": body[:240], "prompt": prompt}
    except Exception as e:
        return {"ok": False, "error": str(e), "prompt": prompt}


def auto_detect_api_style(base_url: str, api_key: str, model_id: str, prompt: str):
    tests = ["openai-responses", "openai-completions"]
    results = {}
    for style in tests:
        results[style] = probe_model_direct(base_url, api_key, style, model_id, prompt)
        if results[style].get("ok"):
            return style, results
    return None, results


def load_existing_allowlist(cfg: dict):
    models = cfg.get("agents", {}).get("defaults", {}).get("models", {})
    if isinstance(models, dict):
        return sorted(models.keys())
    return []


def merge_allowlist(existing: list[str], provider: str, verified: list[str], strategy: str):
    existing_set = set(existing)
    verified_set = set(verified)
    if strategy == "replace-all":
        return sorted(verified_set)
    if strategy == "replace-provider":
        kept = {k for k in existing_set if not k.startswith(provider + "/")}
        return sorted(kept | verified_set)
    if strategy == "merge":
        return sorted(existing_set | verified_set)
    raise ValueError(f"unknown strategy: {strategy}")


def build_final_patch(provider: str, base_url: str, api_style: str, api_key: str, verified_model_ids: list[str], allowlist_keys: list[str], primary: str | None):
    patch = build_provider_patch(provider, base_url, api_style, api_key, verified_model_ids)
    patch.setdefault("agents", {}).setdefault("defaults", {})["models"] = {k: {} for k in allowlist_keys}
    if primary:
        patch["agents"]["defaults"]["model"] = {"primary": primary}
    return patch


def build_rollback_patch(before_cfg: dict):
    return {
        "models": before_cfg.get("models", {}),
        "agents": {
            "defaults": before_cfg.get("agents", {}).get("defaults", {})
        },
    }


def choose_probe_models(models: list[str], primary: str | None, mode: str):
    if mode == "none" or not models:
        return []
    if mode == "all":
        return list(models)
    chosen = []
    if primary:
        p = primary.split("/", 1)[-1]
        if p in models:
            chosen.append(p)
    families = {}
    for m in models:
        fam = m.split("-")[0]
        families.setdefault(fam, m)
    chosen.extend(families.values())
    out = []
    seen = set()
    for m in chosen:
        if m not in seen:
            seen.add(m)
            out.append(m)
    return out


def should_trip_circuit(probe_result: dict):
    status = probe_result.get("status")
    if status in (401, 403, 429):
        return True
    err = (probe_result.get("error") or "").lower()
    if "429" in err or "rate limit" in err or "forbidden" in err or "unauthorized" in err:
        return True
    return False


def score_model(model_id: str):
    s = model_id.lower()
    score = 0
    for i, pat in enumerate(PREFERRED_MODEL_PATTERNS):
        if pat in s:
            score += 100 - i
    if "mini" in s:
        score += 5
    if "codex" in s or "coder" in s:
        score += 12
    if "thinking" in s:
        score -= 3
    if "preview" in s or "beta" in s:
        score -= 4
    return score


def prune_models(models: list[str], max_models: int):
    ranked = sorted(models, key=lambda m: (-score_model(m), m))
    return ranked[:max_models]


def apply_profile_defaults(args):
    prof = PROFILES.get(args.profile)
    if not prof:
        return
    if args.probe is None:
        args.probe = prof["probe"]
    if args.probe_template is None:
        args.probe_template = prof["probe_template"]
    if args.probe_delay_ms is None:
        args.probe_delay_ms = prof["probe_delay_ms"]
    if args.probe_max_failures is None:
        args.probe_max_failures = prof["probe_max_failures"]
    if args.max_models is None:
        args.max_models = prof["max_models"]


def main():
    ap = argparse.ArgumentParser(description="Onboard a provider into OpenClaw, verify usable models, and expose them in /models")
    ap.add_argument("--provider", required=True)
    ap.add_argument("--base-url", required=True)
    ap.add_argument("--api-style", choices=["openai-completions", "openai-responses"])
    ap.add_argument("--api-key", required=True)
    ap.add_argument("--models", default="")
    ap.add_argument("--models-file")
    ap.add_argument("--list-endpoint", action="store_true")
    ap.add_argument("--primary")
    ap.add_argument("--apply", action="store_true", help="Actually patch OpenClaw config")
    ap.add_argument("--strategy", choices=["merge", "replace-provider", "replace-all"], default="replace-provider")
    ap.add_argument("--profile", choices=["conservative", "balanced", "aggressive"], default="balanced")
    ap.add_argument("--probe", choices=["none", "sample", "all"], default=None)
    ap.add_argument("--probe-template", default=None, help="strict-ok|json-ack|classify|extract|summarize|rotate")
    ap.add_argument("--auto-detect-api-style", action="store_true", help="Try responses and chat/completions automatically")
    ap.add_argument("--rollback-on-fail", action="store_true", help="Restore previous config if onboarding fails after apply")
    ap.add_argument("--probe-delay-ms", type=int, default=None)
    ap.add_argument("--probe-max-failures", type=int, default=None)
    ap.add_argument("--max-models", type=int, default=None)
    ap.add_argument("--report-file", help="Write JSON report to this path")
    args = ap.parse_args()
    apply_profile_defaults(args)

    before_cfg = load_config()
    result = {
        "provider": args.provider,
        "baseUrl": args.base_url,
        "strategy": args.strategy,
        "profile": args.profile,
        "rollbackOnFail": args.rollback_on_fail,
        "probeMode": args.probe,
        "probeTemplate": args.probe_template,
        "probeDelayMs": args.probe_delay_ms,
        "maxModels": args.max_models,
    }

    candidate_models = []
    discover_warning = None
    if args.list_endpoint:
        try:
            candidate_models.extend(discover_models(args.base_url, args.api_key))
        except Exception as e:
            discover_warning = str(e)
    if args.models:
        candidate_models.extend([x.strip() for x in args.models.split(",") if x.strip()])
    if args.models_file:
        candidate_models.extend(read_models_file(args.models_file))
    candidate_models = sorted(dict.fromkeys(candidate_models))

    if not candidate_models:
        result["error"] = "No candidate models found. Use --list-endpoint or pass --models / --models-file."
        save_report(args.report_file, result)
        raise SystemExit(result["error"])

    api_style = args.api_style
    detection = None
    first_template_name, first_prompt = pick_probe_prompt(args.probe_template, 0)
    if not api_style and args.auto_detect_api_style:
        api_style, detection = auto_detect_api_style(args.base_url, args.api_key, candidate_models[0], first_prompt)
        result["apiStyleDetection"] = detection
    result["apiStyle"] = api_style
    result["candidateCount"] = len(candidate_models)
    result["candidateModels"] = candidate_models
    result["discoverWarning"] = discover_warning

    if not api_style:
        result["error"] = "API style unresolved. Pass --api-style or use --auto-detect-api-style."
        save_report(args.report_file, result)
        raise SystemExit(result["error"])

    probe_targets = choose_probe_models(candidate_models, args.primary, args.probe)
    direct_probe = {}
    failures = 0
    circuit_open = False
    for i, model_id in enumerate(probe_targets):
        if i > 0 and args.probe_delay_ms > 0:
            time.sleep(args.probe_delay_ms / 1000)
        template_name, prompt = pick_probe_prompt(args.probe_template, i)
        direct_probe[model_id] = probe_model_direct(args.base_url, args.api_key, api_style, model_id, prompt)
        direct_probe[model_id]["template"] = template_name
        if not direct_probe[model_id].get("ok"):
            failures += 1
            if should_trip_circuit(direct_probe[model_id]) or failures >= args.probe_max_failures:
                circuit_open = True
                break
    result["directProbe"] = direct_probe
    result["probeTargets"] = probe_targets
    result["probeCircuitOpen"] = circuit_open

    if args.probe != "none" and probe_targets:
        passed = {m for m, r in direct_probe.items() if r.get("ok")}
        if args.probe == "all":
            candidate_models = [m for m in candidate_models if m in passed]
        else:
            if args.primary:
                p = args.primary.split("/", 1)[-1]
                if p in direct_probe and not direct_probe[p].get("ok"):
                    result["error"] = f"Primary probe failed for {args.primary}."
                    save_report(args.report_file, result)
                    print(json.dumps(result, ensure_ascii=False, indent=2))
                    return
        result["postProbeCount"] = len(candidate_models)
        result["postProbeModels"] = candidate_models
        if not candidate_models:
            result["error"] = "No models survived probe policy."
            save_report(args.report_file, result)
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return

    provider_patch = build_provider_patch(args.provider, args.base_url, api_style, args.api_key, candidate_models)
    result["providerPatchPreview"] = provider_patch

    if not args.apply:
        save_report(args.report_file, result)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return

    try:
        apply_patch(provider_patch, f"已临时写入 provider {args.provider} 以探测可用模型，并重启网关。")
        available_keys = list_available_for_provider(args.provider)
        verified_model_ids = [k.split("/", 1)[1] for k in available_keys]
        if args.max_models is not None and len(verified_model_ids) > args.max_models:
            pruned_ids = prune_models(verified_model_ids, args.max_models)
            available_keys = [f"{args.provider}/{m}" for m in pruned_ids]
            verified_model_ids = pruned_ids
            result["pruned"] = True
            result["prunedTo"] = args.max_models
        else:
            result["pruned"] = False
        existing_allowlist = load_existing_allowlist(load_config())
        merged_allowlist = merge_allowlist(existing_allowlist, args.provider, available_keys, args.strategy)
        final_patch = build_final_patch(args.provider, args.base_url, api_style, args.api_key, verified_model_ids, merged_allowlist, args.primary)

        result["availableCount"] = len(available_keys)
        result["availableModels"] = available_keys
        result["existingAllowlistCount"] = len(existing_allowlist)
        result["finalAllowlistCount"] = len(merged_allowlist)
        result["finalAllowlist"] = merged_allowlist
        result["finalPatch"] = final_patch

        if not available_keys:
            raise RuntimeError("Provider was added but no models resolved as available=true.")

        apply_patch(final_patch, f"已接入 provider {args.provider}，仅保留已验证可用模型，并按 {args.strategy} 策略更新 /models，可在 Telegram 切换。")
        result["status"] = "ok"
    except Exception as e:
        result["status"] = "failed"
        result["error"] = str(e)
        if args.rollback_on_fail:
            rollback_patch = build_rollback_patch(before_cfg)
            result["rollbackPatch"] = rollback_patch
            try:
                apply_patch(rollback_patch, f"provider {args.provider} 接入失败，已自动回滚到之前配置。")
                result["rolledBack"] = True
            except Exception as re:
                result["rolledBack"] = False
                result["rollbackError"] = str(re)
        save_report(args.report_file, result)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        raise SystemExit(1)

    save_report(args.report_file, result)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
