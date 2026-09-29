#!/usr/bin/env bash
# Unattended upkeep: web-refresh the meta snapshot when >21 days old, ingest any
# new files in knowledge/opponent/raw/, commit. Safe to run daily from cron.
#   crontab:  17 9 * * *  /path/to/Rainbow/scripts/auto.sh --push
set -euo pipefail
cd "$(dirname "$0")/.."
{
  echo "== $(date -Is)"
  git pull --ff-only --quiet || echo "git pull skipped (not fast-forward or offline)"
  python3 scripts/coach.py auto "$@"
} 2>&1 | tee -a auto.log
