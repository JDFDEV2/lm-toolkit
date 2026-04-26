# Claude Code + lm-toolkit: How Tasks Are Routed

## Tools Overview

| Tool | Where it runs | Purpose |
|---|---|---|
| **Claude Code** | Local or server SSH session | Complex tasks: code changes, debugging, multi-file edits, server ops |
| **`lm`** | Local Git Bash (or server) | Routine tasks: explanations, commit messages, README drafts, quick Q&A |
| **`cronguard`** | Server (cron / TacticalRMM) | Run any scheduled command with approval gate + push notification |
| **`lm-log`** | Local Git Bash | View history of all `lm` calls |
| **`lm-health`** | Local Git Bash | Verify Lemonade is running and right model is loaded |

---

## When to Use What

### Use Claude Code for:
- Implementing or fixing code across multiple files
- Debugging errors and tracebacks
- Server administration (nginx, Docker, SSH, UFW)
- Security work, deployments, migrations
- Anything that needs tool use (file edits, bash, web search)

```
# Examples — ask Claude Code:
"Fix the auth bug in user.py"
"Deploy the new Formbricks config to the server"
"Review the nginx config for security issues"
```

### Use `lm` for:
- Explaining code or configs
- Drafting README, changelog, docstrings
- Generating git commit messages from staged diff
- Quick status summaries or "what does X mean" questions
- Anything where a fast local answer is good enough

```bash
# Examples — run lm directly:
lm "explain what this nginx config block does"
lm --commit                        # generate commit message from git diff
lm --readme                        # draft README.md for current directory
cat error.log | lm "summarize the errors"
```

---

## How the Local LLM Gets Context

Every `lm` call automatically injects two things as system context before your prompt:

1. **`~/.claude/CLAUDE.md`** — global instructions: shell rules, project conventions, GitHub workflow, delegation guidelines
2. **`~/.claude/projects/*/memory/*.md`** — all memory files: user profile, project overview, branding, server services, environment setup

This means `lm` already knows about m-noris, the Hetzner server, the active services, and how to behave — without you having to repeat it.

To skip context injection (faster, for simple one-off questions):
```bash
lm --no-context "what is a Docker bridge network?"
```

---

## cronguard: Scheduled Jobs with Approval

Every cronguard job follows this flow:

```
cron fires
   → sends push notification to ntfy.sh/jf-cronguard
   → waits for your approval (default: 300s timeout)
   → on approval: runs the command, logs output
   → sends completion notification (✓ success or ✗ failed)
```

**Subscribe:** Install the ntfy app → subscribe to topic `jf-cronguard`

**Example crontab entry:**
```bash
# Every Sunday at 02:00 — backup Postgres
0 2 * * 0 /root/.local/bin/cronguard \
  --name "Weekly DB Backup" \
  --plan "Dumps all Postgres DBs to /backups/ and prunes files older than 30 days" \
  --cmd  "pg_dumpall > /backups/pg_$(date +\%F).sql && find /backups -name '*.sql' -mtime +30 -delete" \
  --ntfy jf-cronguard \
  --timeout 600
```

**Approve/reject a pending job (on the server):**
```bash
ls ~/.cronguard/queue/          # see pending jobs
touch ~/.cronguard/queue/JOB_ID.approved
touch ~/.cronguard/queue/JOB_ID.rejected
```

Logs are written to `~/.cronguard/logs/`.

---

## Health Check and Usage Logs

**Check Lemonade is running:**
```bash
lm-health
# [OK]   Lemonade running at http://localhost:8000
# [OK]   Target model 'Qwen2.5-3B-Instruct-FLM' is active
```

**Override the model for a single call:**
```bash
LM_MODEL=Qwen3-VL-4B-Instruct-FLM lm "describe this screenshot" < image.png
```

**View usage log:**
```bash
lm-log              # last 20 calls
lm-log --stats      # totals: calls, time, output chars
lm-log --all        # full history
lm-log --tail       # live, follows new entries
```

Log file location: `~/.lm-toolkit/usage.log` (one JSON line per call)

---

## Model Capability Limits

The 3B Qwen models are fast and free but suited for **short, concrete tasks only**:

| Good fit | Poor fit |
|---|---|
| Commit messages from a diff | Writing structured reference docs |
| Explaining a single function | Multi-step debugging |
| Quick "what does X mean" | Architecture decisions |
| Summarising a log file | Anything requiring tool use |

For anything complex, use Claude Code. The local LLM saves API cost and latency for the routine 20% of tasks.
