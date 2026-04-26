#!/usr/bin/env python3
"""
log.py — View lm-toolkit usage log.

Usage:
  lm-log              # show last 20 entries
  lm-log --all        # show everything
  lm-log --stats      # summary: total calls, tokens, time saved
  lm-log --tail       # follow new entries (like tail -f)
"""

import json
import sys
import time
import argparse
from pathlib import Path

LOG_FILE = Path.home() / ".lm-toolkit" / "usage.log"

COLS = "{ts:<22} {mode:<8} {elapsed:>5}s  {chars:>6} chars  {prompt}"


def read_entries() -> list[dict]:
    if not LOG_FILE.exists():
        return []
    entries = []
    for line in LOG_FILE.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            try:
                entries.append(json.loads(line))
            except json.JSONDecodeError:
                pass
    return entries


def print_entries(entries: list[dict]) -> None:
    if not entries:
        print("No usage logged yet. Run: lm \"hello\"")
        return
    print(f"{'Timestamp':<22} {'Mode':<8} {'Time':>6}  {'Output':>11}  Prompt")
    print("─" * 90)
    for e in entries:
        print(COLS.format(
            ts=e.get("ts", "?"),
            mode=e.get("mode", "?"),
            elapsed=e.get("elapsed", 0),
            chars=e.get("chars", 0),
            prompt=e.get("prompt", "")[:60],
        ))


def print_stats(entries: list[dict]) -> None:
    if not entries:
        print("No usage logged yet.")
        return

    total      = len(entries)
    total_time = sum(e.get("elapsed", 0) for e in entries)
    total_chars= sum(e.get("chars",   0) for e in entries)

    by_mode: dict[str, int] = {}
    for e in entries:
        m = e.get("mode", "?")
        by_mode[m] = by_mode.get(m, 0) + 1

    print(f"lm-toolkit usage summary")
    print(f"─────────────────────────")
    print(f"Total calls    : {total}")
    print(f"Total time     : {total_time:.0f}s  (~{total_time/60:.1f} min)")
    print(f"Total output   : {total_chars:,} chars")
    print(f"By mode        : {', '.join(f'{k}={v}' for k,v in sorted(by_mode.items()))}")
    if total > 0:
        print(f"Avg per call   : {total_time/total:.1f}s,  {total_chars//total} chars")


def tail_log() -> None:
    print(f"Watching {LOG_FILE}  (Ctrl+C to stop)")
    print(f"{'Timestamp':<22} {'Mode':<8} {'Time':>6}  {'Output':>11}  Prompt")
    print("─" * 90)
    last_size = LOG_FILE.stat().st_size if LOG_FILE.exists() else 0
    try:
        while True:
            if LOG_FILE.exists():
                size = LOG_FILE.stat().st_size
                if size > last_size:
                    with LOG_FILE.open(encoding="utf-8") as f:
                        f.seek(last_size)
                        for line in f:
                            line = line.strip()
                            if line:
                                try:
                                    e = json.loads(line)
                                    print(COLS.format(
                                        ts=e.get("ts", "?"),
                                        mode=e.get("mode", "?"),
                                        elapsed=e.get("elapsed", 0),
                                        chars=e.get("chars", 0),
                                        prompt=e.get("prompt", "")[:60],
                                    ))
                                except json.JSONDecodeError:
                                    pass
                    last_size = size
            time.sleep(1)
    except KeyboardInterrupt:
        pass


def main() -> None:
    parser = argparse.ArgumentParser(description="View lm-toolkit usage log")
    parser.add_argument("--all",   action="store_true", help="Show all entries")
    parser.add_argument("--stats", action="store_true", help="Show usage summary")
    parser.add_argument("--tail",  action="store_true", help="Follow new entries")
    parser.add_argument("-n", type=int, default=20, help="Number of entries to show (default: 20)")
    args = parser.parse_args()

    if args.tail:
        tail_log()
        return

    entries = read_entries()

    if args.stats:
        print_stats(entries)
        return

    subset = entries if args.all else entries[-args.n:]
    print_entries(subset)
    if not args.all and len(entries) > args.n:
        print(f"\n  … {len(entries) - args.n} older entries hidden. Use --all to see everything.")


if __name__ == "__main__":
    main()
