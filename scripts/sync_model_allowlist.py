#!/usr/bin/env python3
import argparse
import json
import subprocess
import sys
from pathlib import Path

WORKSPACE = Path(r"C:\Users\严志飞\.openclaw\workspace")


def run(cmd):
    p = subprocess.run(cmd, cwd=str(WORKSPACE), capture_output=True, text=True, shell=True)
    return p.returncode, p.stdout, p.stderr


def parse_models_json(raw: str):
    lines = [line for line in raw.splitlines() if not line.startswith("[plugins]")]
    text = "\n".join(lines).strip()
    if not text:
        raise RuntimeError("empty models output")
    return json.loads(text)


def main():
    ap = argparse.ArgumentParser(description="Sync agents.defaults.models from available OpenClaw models")
    ap.add_argument("--mode", choices=["all-available", "configured-available"], default="configured-available")
    ap.add_argument("--provider", action="append", default=[], help="Repeatable provider allowlist, e.g. ice")
    ap.add_argument("--prefix", action="append", default=[], help="Repeatable model key prefix allowlist, e.g. github-copilot/")
    ap.add_argument("--restart", action="store_true", help="Apply via gateway config.patch and restart")
    ap.add_argument("--primary", default=None, help="Optional primary model override")
    args = ap.parse_args()

    code, out, err = run(["openclaw", "models", "list", "--all", "--json"])
    if code != 0:
        sys.stderr.write(err or out)
        raise SystemExit(code)

    data = parse_models_json(out)
    models = data.get("models", [])

    kept = []
    for m in models:
        key = m.get("key")
        if not key or not m.get("available"):
            continue
        if args.mode == "configured-available" and "configured" not in (m.get("tags") or []):
            continue
        provider = key.split("/", 1)[0]
        if args.provider and provider not in args.provider:
            continue
        if args.prefix and not any(key.startswith(p) for p in args.prefix):
            continue
        kept.append(key)

    kept = sorted(dict.fromkeys(kept))
    payload = {"agents": {"defaults": {"models": {k: {} for k in kept}}}}
    if args.primary:
        payload["agents"]["defaults"]["model"] = {"primary": args.primary}

    print(json.dumps({"count": len(kept), "models": kept, "patch": payload}, ensure_ascii=False, indent=2))

    if args.restart:
        patch_json = json.dumps(payload, ensure_ascii=False)
        code, out, err = run([
            "openclaw",
            "gateway",
            "config.patch",
            "--raw",
            patch_json,
            "--note",
            "已通过 model-allowlist-sync 技能同步模型可见列表并重启网关。",
        ])
        if code != 0:
            sys.stderr.write(err or out)
            raise SystemExit(code)
        print("\n=== gateway result ===\n")
        print(out)


if __name__ == "__main__":
    main()
