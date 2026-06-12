#!/usr/bin/env bash
# Refresh results/odds, rebuild the leaderboard, and push to GitHub Pages.
# Runs from local cron every 20 min (see README). Logs to data/update.log.
set -euo pipefail

REPO="/home/nvelingker/mkeoliya/fifa"
LOG="$REPO/data/update.log"
# push as mkeoliya via the dedicated SSH key (the `gitm` identity)
export GIT_SSH_COMMAND="ssh -o IdentitiesOnly=yes -i /home/nvelingker/mkeoliya/.ssh/id_ed25519"

# heartbeat (proves cron is alive even when we skip), then gate: only
# refresh during match windows / live matches / the daily sync slot
date -u +%Y-%m-%dT%H:%M:%SZ > "$REPO/data/.last_check"
if [ "${FORCE:-0}" = "1" ]; then
  REASON="forced"
else
  REASON=$(python3 "$REPO/pipeline/should_update.py") || exit 0
fi

exec >>"$LOG" 2>&1
echo "=== $(date -u +%Y-%m-%dT%H:%M:%SZ) ($REASON) ==="

# stop after the tournament
if [ "$(date -u +%Y%m%d)" -gt 20260725 ]; then
  echo "tournament over; exiting"
  exit 0
fi

cd "$REPO"
# don't fight a concurrent run
exec 9>"$REPO/data/.update.lock"
flock -n 9 || { echo "another run in progress; exiting"; exit 0; }

git pull --rebase --autostash --quiet origin main || { git rebase --abort 2>/dev/null; echo "pull failed"; exit 1; }

python3 pipeline/results.py
python3 pipeline/kalshi.py
python3 pipeline/scoring.py

git add data/results.json docs/data/
if git diff --cached --quiet; then
  echo "no changes"
else
  git commit --quiet -m "data: refresh results, odds, leaderboard"
  git push --quiet origin main
  echo "pushed"
fi
