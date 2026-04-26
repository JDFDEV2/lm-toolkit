#!/usr/bin/env python3
"""
delegate.py — Task complexity classifier for Claude Code ↔ Lemonade routing.

Classifies a prompt as 'routine' or 'complex' using keyword heuristics.
Exits 0 for routine (delegate to lm), exits 1 for complex (use Claude).

Usage (from Claude Code hook or shell):
  python delegate.py "what is the status of nginx?"   # → routine, exit 0
  python delegate.py "fix the auth bug in user.py"    # → complex, exit 1
  python delegate.py --explain "your prompt"          # prints label + reason
"""

import sys
import re
import argparse

# Prompts matching any of these → ROUTINE (local LLM)
ROUTINE_PATTERNS = [
    r"\b(what is|what are|explain|describe|summarize|list|show|display)\b",
    r"\b(status|health|check|ping|verify|confirm)\b",
    r"\b(how does|how do|how to)\b",
    r"\b(git log|git status|git diff|git show)\b",
    r"\b(read|open|view|look at|look up)\b",
    r"\b(document|docstring|readme|changelog|comment)\b",
    r"\b(translate|reword|rephrase|draft|write a|write the)\b",
    r"\b(commit message|pr description|release note)\b",
]

# Prompts matching any of these → COMPLEX (use Claude)
COMPLEX_PATTERNS = [
    r"\b(fix|debug|resolve|solve|diagnose|investigate)\b",
    r"\b(implement|add|create|build|develop|set up|setup)\b",
    r"\b(refactor|rewrite|restructure|redesign|migrate)\b",
    r"\b(deploy|configure|install|upgrade|downgrade)\b",
    r"\b(error|exception|traceback|crash|broken|failing|not working)\b",
    r"\b(security|vulnerability|auth|authentication|permission)\b",
    r"\b(database|schema|migration|query)\b",
    r"\b(performance|optimize|slow|bottleneck)\b",
]


def classify(prompt: str) -> tuple[str, str]:
    """Returns ('routine'|'complex', reason)."""
    p = prompt.lower()

    for pattern in COMPLEX_PATTERNS:
        if re.search(pattern, p):
            return "complex", f"matched complex keyword: {pattern}"

    for pattern in ROUTINE_PATTERNS:
        if re.search(pattern, p):
            return "routine", f"matched routine keyword: {pattern}"

    # Default: short prompts → routine, long → complex
    word_count = len(prompt.split())
    if word_count <= 12:
        return "routine", f"short prompt ({word_count} words) — defaulting to routine"
    return "complex", f"long prompt ({word_count} words), no routine signal — defaulting to complex"


def main() -> None:
    parser = argparse.ArgumentParser(description="Classify a prompt as routine or complex")
    parser.add_argument("prompt", help="The prompt to classify")
    parser.add_argument("--explain", action="store_true", help="Print label and reason")
    args = parser.parse_args()

    label, reason = classify(args.prompt)

    if args.explain:
        print(f"label:  {label}")
        print(f"reason: {reason}")
    else:
        print(label)

    # Exit code: 0 = routine, 1 = complex
    sys.exit(0 if label == "routine" else 1)


if __name__ == "__main__":
    main()
