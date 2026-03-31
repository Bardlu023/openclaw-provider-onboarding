#!/usr/bin/env python3
import argparse
import json
import sys
import urllib.request
from pathlib import Path


def fetch_json(url: str, api_key: str):
    req = urllib.request.Request(url)
    req.add_header("Authorization", f"Bearer {api_key}")
    req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def discover_models(base_url: str, api_key: str):
    url = base_url.rstrip("/") + "/models"
    data = fetch_json(url, api_key)
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


def main():
    ap = argparse.ArgumentParser(description="Probe provider model candidates before OpenClaw config patch")
    ap.add_argument("--base-url", required=True)
    ap.add_argument("--api-key", required=True)
    ap.add_argument("--api-style", required=True, choices=["openai-completions", "openai-responses"])
    ap.add_argument("--provider", required=True)
    ap.add_argument("--models", default="")
    ap.add_argument("--models-file")
    ap.add_argument("--list-endpoint", action="store_true")
    args = ap.parse_args()

    models = []
    if args.list_endpoint:
        try:
            models.extend(discover_models(args.base_url, args.api_key))
        except Exception as e:
            print(json.dumps({"warning": f"list endpoint failed: {e}"}, ensure_ascii=False))
    if args.models:
        models.extend([x.strip() for x in args.models.split(",") if x.strip()])
    if args.models_file:
        models.extend(read_models_file(args.models_file))

    models = sorted(dict.fromkeys(models))
    payload = {
        "providerPatch": {
            "models": {
                "providers": {
                    args.provider: {
                        "baseUrl": args.base_url,
                        "apiKey": args.api_key,
                        "api": args.api_style,
                        "models": [
                            {
                                "id": m,
                                "name": m,
                                "api": args.api_style,
                                "reasoning": False,
                                "input": ["text"],
                                "cost": {"input": 0, "output": 0, "cacheRead": 0, "cacheWrite": 0},
                                "contextWindow": 200000,
                                "maxTokens": 8192,
                            }
                            for m in models
                        ],
                    }
                }
            }
        },
        "candidateModels": models,
        "count": len(models),
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
