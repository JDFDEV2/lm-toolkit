#!/usr/bin/env python3
"""
health.py — Lemonade LLM health checker.

Exits 0 if healthy, 1 if unreachable or wrong model loaded.
Use as a pre-flight check in scripts or Claude Code hooks.
"""

import os
import sys

try:
    import requests
except ImportError:
    print("[FAIL] Missing dependency: pip install requests", file=sys.stderr)
    sys.exit(1)

LEMONADE_URL  = os.getenv("LEMONADE_URL", "http://localhost:8000")
TARGET_MODEL  = os.getenv("LM_MODEL", "Llama-3.2-3B-Hybrid")


def check() -> bool:
    try:
        r = requests.get(f"{LEMONADE_URL}/v1/models", timeout=5)
        r.raise_for_status()
        models = r.json().get("data", [])

        if not models:
            print(f"[WARN] Lemonade is running at {LEMONADE_URL} but no models are loaded.")
            print(f"[WARN] Open the Lemonade app and load '{TARGET_MODEL}'.")
            return False

        model_ids = [m["id"] for m in models]
        active    = model_ids[0]

        print(f"[OK]   Lemonade running at {LEMONADE_URL}")
        print(f"[OK]   Models available: {', '.join(model_ids)}")

        if TARGET_MODEL and TARGET_MODEL not in model_ids:
            print(f"[WARN] Target model '{TARGET_MODEL}' is not loaded.")
            print(f"[WARN] Currently active: {active}")
            print(f"[WARN] Load '{TARGET_MODEL}' in the Lemonade app.")
            return False

        print(f"[OK]   Target model '{TARGET_MODEL}' is active.")
        return True

    except requests.exceptions.ConnectionError:
        print(f"[FAIL] Lemonade not reachable at {LEMONADE_URL}")
        print(f"[FAIL] Make sure the Lemonade app is running on this machine.")
        return False
    except Exception as e:
        print(f"[FAIL] Unexpected error: {e}", file=sys.stderr)
        return False


if __name__ == "__main__":
    ok = check()
    sys.exit(0 if ok else 1)
