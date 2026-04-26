#!/usr/bin/env bash
# cronguard.sh — Approval-first cron job wrapper.
#
# Before running any command, this script:
#   1. Generates a summary of what will happen
#   2. Sends a push notification via ntfy.sh (optional but recommended)
#   3. Waits for your approval (touch an approval file)
#   4. Executes the command and logs the result
#   5. Sends a completion notification
#
# Usage:
#   cronguard.sh --name "Backup DB" \
#                --plan "Dumps PostgreSQL to /backups/db_$(date +%F).sql.gz" \
#                --cmd  "pg_dump mydb | gzip > /backups/db_$(date +%F).sql.gz" \
#                --ntfy jf-cronguard \
#                --timeout 600
#
# Approve a pending job:
#   touch ~/.cronguard/queue/JOB_ID.approved
#
# Reject a pending job:
#   touch ~/.cronguard/queue/JOB_ID.rejected
#
# List pending jobs:
#   ls ~/.cronguard/queue/*.json 2>/dev/null | xargs -I{} cat {}
#
# Environment variables (override with export or in crontab):
#   NTFY_TOPIC   — ntfy.sh topic name (no https:// prefix)
#   NTFY_HOST    — defaults to https://ntfy.sh (use your own for self-hosted)
#   QUEUE_DIR    — defaults to ~/.cronguard/queue
#   LOG_DIR      — defaults to ~/.cronguard/logs
#   TIMEOUT      — seconds to wait for approval (default: 300)

set -euo pipefail

# ── defaults ──────────────────────────────────────────────────────────────────
NAME=""
PLAN=""
CMD=""
NTFY_TOPIC="${NTFY_TOPIC:-}"
NTFY_HOST="${NTFY_HOST:-https://ntfy.sh}"
TIMEOUT="${TIMEOUT:-300}"
QUEUE_DIR="${QUEUE_DIR:-$HOME/.cronguard/queue}"
LOG_DIR="${LOG_DIR:-$HOME/.cronguard/logs}"
AUTO_APPROVE="${AUTO_APPROVE:-0}"  # set to 1 to skip approval (not recommended)

# ── arg parsing ───────────────────────────────────────────────────────────────
while [[ $# -gt 0 ]]; do
  case "$1" in
    --name)         NAME="$2";        shift 2 ;;
    --plan)         PLAN="$2";        shift 2 ;;
    --cmd)          CMD="$2";         shift 2 ;;
    --ntfy)         NTFY_TOPIC="$2";  shift 2 ;;
    --ntfy-host)    NTFY_HOST="$2";   shift 2 ;;
    --timeout)      TIMEOUT="$2";     shift 2 ;;
    --auto-approve) AUTO_APPROVE=1;   shift   ;;
    --queue-dir)    QUEUE_DIR="$2";   shift 2 ;;
    --log-dir)      LOG_DIR="$2";     shift 2 ;;
    *) echo "Unknown option: $1"; exit 1 ;;
  esac
done

[[ -z "$NAME" ]] && { echo "[cronguard] ERROR: --name required"; exit 1; }
[[ -z "$CMD"  ]] && { echo "[cronguard] ERROR: --cmd required";  exit 1; }
[[ -z "$PLAN" ]] && PLAN="(no plan provided)"

# ── setup ─────────────────────────────────────────────────────────────────────
JOB_ID="${NAME//[^a-zA-Z0-9_-]/_}_$(date +%Y%m%d_%H%M%S)"
mkdir -p "$QUEUE_DIR" "$LOG_DIR"

JOB_FILE="$QUEUE_DIR/$JOB_ID.json"
LOG_FILE="$LOG_DIR/$JOB_ID.log"
APPROVED_FILE="$QUEUE_DIR/$JOB_ID.approved"
REJECTED_FILE="$QUEUE_DIR/$JOB_ID.rejected"

# ── write pending job ─────────────────────────────────────────────────────────
cat > "$JOB_FILE" << JSON
{
  "id":      "$JOB_ID",
  "name":    "$NAME",
  "plan":    "$PLAN",
  "cmd":     "$CMD",
  "created": "$(date -Iseconds)",
  "status":  "pending",
  "timeout": $TIMEOUT
}
JSON

echo "[cronguard] Job queued: $JOB_ID"
echo "[cronguard] Name:    $NAME"
echo "[cronguard] Plan:    $PLAN"
echo "[cronguard] Command: $CMD"
echo ""

# ── notification ──────────────────────────────────────────────────────────────
notify() {
  local title="$1" body="$2" priority="${3:-default}"
  if [[ -n "$NTFY_TOPIC" ]]; then
    curl -sf \
      -H "Title: $title" \
      -H "Priority: $priority" \
      -d "$body" \
      "$NTFY_HOST/$NTFY_TOPIC" > /dev/null || true
  fi
}

notify \
  "cronguard: approval needed — $NAME" \
  "Plan: $PLAN

Command: $CMD

To approve: touch $APPROVED_FILE
To reject:  touch $REJECTED_FILE

Timeout: ${TIMEOUT}s" \
  "high"

echo "[cronguard] Notification sent (topic: ${NTFY_TOPIC:-none})"
echo "[cronguard] Waiting for approval (timeout: ${TIMEOUT}s)..."
echo "[cronguard]   Approve: touch $APPROVED_FILE"
echo "[cronguard]   Reject:  touch $REJECTED_FILE"
echo ""

# ── auto-approve shortcut ─────────────────────────────────────────────────────
if [[ "$AUTO_APPROVE" -eq 1 ]]; then
  echo "[cronguard] AUTO_APPROVE=1 — skipping approval gate"
  touch "$APPROVED_FILE"
fi

# ── approval loop ─────────────────────────────────────────────────────────────
ELAPSED=0
POLL=10

while [[ $ELAPSED -lt $TIMEOUT ]]; do
  if [[ -f "$APPROVED_FILE" ]]; then
    echo "[cronguard] APPROVED at $(date '+%H:%M:%S') — executing..."
    break
  fi
  if [[ -f "$REJECTED_FILE" ]]; then
    echo "[cronguard] REJECTED — skipping job."
    rm -f "$JOB_FILE" "$REJECTED_FILE"
    echo "=== REJECTED: $NAME — $(date -Iseconds) ===" >> "$LOG_FILE"
    notify "cronguard: job rejected — $NAME" "Job '$NAME' was rejected and will not run."
    exit 0
  fi
  sleep $POLL
  ELAPSED=$((ELAPSED + POLL))
done

# ── timeout ───────────────────────────────────────────────────────────────────
if [[ ! -f "$APPROVED_FILE" ]]; then
  echo "[cronguard] TIMEOUT — no approval received within ${TIMEOUT}s. Skipping."
  rm -f "$JOB_FILE"
  echo "=== TIMEOUT: $NAME — $(date -Iseconds) ===" >> "$LOG_FILE"
  notify "cronguard: job timed out — $NAME" "Job '$NAME' was not approved within ${TIMEOUT}s and was skipped."
  exit 1
fi

# ── execute ───────────────────────────────────────────────────────────────────
{
  echo "=== START: $NAME ==="
  echo "Time:    $(date -Iseconds)"
  echo "Command: $CMD"
  echo "───────────────────────────────"
} >> "$LOG_FILE"

set +e
bash -c "$CMD" 2>&1 | tee -a "$LOG_FILE"
EXIT_CODE=${PIPESTATUS[0]}
set -e

{
  echo "───────────────────────────────"
  echo "Exit code: $EXIT_CODE"
  echo "Finished:  $(date -Iseconds)"
  echo "=== END: $NAME ==="
  echo ""
} >> "$LOG_FILE"

# ── cleanup & result notification ─────────────────────────────────────────────
rm -f "$JOB_FILE" "$APPROVED_FILE"

if [[ $EXIT_CODE -eq 0 ]]; then
  echo "[cronguard] SUCCESS (exit 0)"
  notify "cronguard: ✓ $NAME succeeded" "Job completed successfully.\nLog: $LOG_FILE"
else
  echo "[cronguard] FAILED (exit $EXIT_CODE)"
  notify "cronguard: ✗ $NAME FAILED (exit $EXIT_CODE)" \
    "Job failed with exit code $EXIT_CODE.\nLog: $LOG_FILE" "urgent"
fi

exit $EXIT_CODE
