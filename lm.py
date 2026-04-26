#!/usr/bin/env python3
"""
lm — Lemonade LLM CLI with CLAUDE.md + memory context injection.

Usage:
  lm "your question or task"
  lm --commit              # generate git commit message from staged diff
  lm --readme              # draft README.md for current directory
  lm --health              # check Lemonade health only
  lm --no-context "prompt" # skip CLAUDE.md/memory injection
  cat file.py | lm "explain this"
"""

import sys
import os
import json
import argparse
import subprocess
from pathlib import Path

try:
    import requests
except ImportError:
    print("Missing dependency: pip install requests", file=sys.stderr)
    sys.exit(1)

LEMONADE_URL = os.getenv("LEMONADE_URL", "http://localhost:8000")
TARGET_MODEL  = os.getenv("LM_MODEL", None)


# ── context loading ────────────────────────────────────────────────────────────

def get_claude_home() -> Path:
    return Path.home() / ".claude"


def load_system_context() -> str:
    claude_home = get_claude_home()
    parts: list[str] = []

    # CLAUDE.md
    claude_md = claude_home / "CLAUDE.md"
    if claude_md.exists():
        parts.append(f"# GLOBAL INSTRUCTIONS (CLAUDE.md)\n\n{claude_md.read_text(encoding='utf-8')}")

    # Memory files — search all project memory dirs
    for memory_dir in sorted(claude_home.glob("projects/*/memory")):
        memory_index = memory_dir / "MEMORY.md"
        if memory_index.exists():
            parts.append(f"# MEMORY INDEX\n\n{memory_index.read_text(encoding='utf-8')}")
        for md_file in sorted(memory_dir.glob("*.md")):
            if md_file.name == "MEMORY.md":
                continue
            parts.append(f"## memory/{md_file.stem}\n\n{md_file.read_text(encoding='utf-8')}")

    return "\n\n---\n\n".join(parts)


# ── health ─────────────────────────────────────────────────────────────────────

def check_health(verbose: bool = False) -> tuple[str | None, str | None]:
    """Returns (model_id, error_message). error_message is None on success."""
    try:
        r = requests.get(f"{LEMONADE_URL}/v1/models", timeout=5)
        r.raise_for_status()
        models = r.json().get("data", [])
        if not models:
            return None, "Lemonade is running but no models are loaded"
        model_id = models[0]["id"]
        if verbose:
            model_list = ", ".join(m["id"] for m in models)
            target = TARGET_MODEL or model_id
            status = "✓" if (not TARGET_MODEL or TARGET_MODEL == model_id) else "!"
            print(f"[OK]    Lemonade at {LEMONADE_URL}")
            print(f"[OK]    Models loaded: {model_list}")
            print(f"[{status}]    Active model: {model_id}  (target: {target})")
        return model_id, None
    except requests.exceptions.ConnectionError:
        return None, f"Lemonade not reachable at {LEMONADE_URL}"
    except Exception as e:
        return None, str(e)


# ── LLM call ───────────────────────────────────────────────────────────────────

def call_lm(prompt: str, system_context: str, model: str, stream: bool = True) -> str:
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "stream": stream,
        "temperature": 0.3,
    }
    if system_context:
        payload["system"] = system_context

    collected = []

    if stream:
        with requests.post(
            f"{LEMONADE_URL}/v1/chat/completions",
            json=payload, stream=True, timeout=180
        ) as r:
            r.raise_for_status()
            for line in r.iter_lines():
                if not line:
                    continue
                text = line.decode() if isinstance(line, bytes) else line
                if not text.startswith("data: "):
                    continue
                data = text[6:]
                if data == "[DONE]":
                    break
                try:
                    chunk = json.loads(data)
                    content = chunk["choices"][0]["delta"].get("content", "")
                    if content:
                        print(content, end="", flush=True)
                        collected.append(content)
                except (json.JSONDecodeError, KeyError):
                    pass
        print()  # final newline
        return "".join(collected)
    else:
        r = requests.post(
            f"{LEMONADE_URL}/v1/chat/completions",
            json=payload, timeout=180
        )
        r.raise_for_status()
        content = r.json()["choices"][0]["message"]["content"]
        print(content)
        return content


# ── task modes ─────────────────────────────────────────────────────────────────

def mode_commit(model: str, context: str) -> None:
    diff = subprocess.run(
        ["git", "diff", "--staged"],
        capture_output=True, text=True
    )
    if not diff.stdout.strip():
        print("[lm] No staged changes. Run: git add <files>", file=sys.stderr)
        sys.exit(1)

    prompt = (
        "Generate a concise git commit message for the following staged diff.\n"
        "Format: one short subject line (≤72 chars), then a blank line, then bullet points "
        "summarising the key changes if non-trivial. Output the commit message only — no intro text.\n\n"
        f"```diff\n{diff.stdout[:8000]}\n```"
    )
    message = call_lm(prompt, context, model, stream=False)

    confirm = input("\n[lm] Commit with this message? [y/N] ").strip().lower()
    if confirm == "y":
        subprocess.run(["git", "commit", "-m", message], check=True)
        print("[lm] Committed.")
    else:
        print("[lm] Aborted.")


def mode_readme(model: str, context: str) -> None:
    cwd = Path.cwd()
    files = sorted(f.relative_to(cwd) for f in cwd.rglob("*")
                   if f.is_file() and not any(
                       part.startswith(".") or part in ("node_modules", "__pycache__", "dist", "build")
                       for part in f.parts
                   ))
    file_list = "\n".join(str(f) for f in files[:80])

    prompt = (
        f"Draft a README.md for the project at '{cwd.name}'.\n"
        f"File structure:\n{file_list}\n\n"
        "Include: project purpose, quick-start, usage, configuration. "
        "Use the m-noris brand tone where relevant. Output markdown only."
    )
    readme_content = call_lm(prompt, context, model, stream=False)

    out = cwd / "README.md"
    if out.exists():
        confirm = input(f"[lm] README.md already exists. Overwrite? [y/N] ").strip().lower()
        if confirm != "y":
            print("[lm] Aborted.")
            return

    out.write_text(readme_content, encoding="utf-8")
    print(f"[lm] Written to {out}")


# ── main ───────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Lemonade LLM CLI with CLAUDE.md + memory context"
    )
    parser.add_argument("prompt", nargs="?", help="Prompt or question")
    parser.add_argument("--file", "-f", help="Read prompt from file")
    parser.add_argument("--model", "-m", help="Override model ID")
    parser.add_argument("--health", action="store_true", help="Health check only")
    parser.add_argument("--commit", action="store_true", help="Generate git commit message")
    parser.add_argument("--readme", action="store_true", help="Draft README.md for cwd")
    parser.add_argument("--no-context", action="store_true", help="Skip CLAUDE.md/memory injection")
    parser.add_argument("--no-stream", action="store_true", help="Disable streaming output")
    args = parser.parse_args()

    # Health check
    model_id, err = check_health(verbose=args.health)
    if err:
        print(f"[ERROR] {err}", file=sys.stderr)
        sys.exit(1)
    if args.health:
        return

    active_model = args.model or TARGET_MODEL or model_id
    context = "" if args.no_context else load_system_context()

    if args.commit:
        mode_commit(active_model, context)
        return

    if args.readme:
        mode_readme(active_model, context)
        return

    # Plain prompt
    prompt = args.prompt
    if args.file:
        prompt = Path(args.file).read_text(encoding="utf-8")
    if not prompt and not sys.stdin.isatty():
        prompt = sys.stdin.read()
    if not prompt:
        parser.print_help()
        sys.exit(1)

    call_lm(prompt, context, active_model, stream=not args.no_stream)


if __name__ == "__main__":
    main()
