#!/usr/bin/env bash
set -euo pipefail

ROOT=/home/sage/scripts/sagerock-marketing-tools
mkdir -p "$ROOT/logs"
exec >> "$ROOT/logs/weekly_ads_email.log" 2>&1

MONITOR_CONFIG="/home/sage/.config/sagerock-cron-monitor.env"
if [ -r "$MONITOR_CONFIG" ]; then
  # shellcheck disable=SC1090
  source "$MONITOR_CONFIG"
fi

heartbeat() {
  local state="$1"
  local message="$2"
  if [ -z "${CRON_MONITOR_URL:-}" ] || [ -z "${CRON_MONITOR_TOKEN:-}" ]; then
    return 0
  fi
  curl -fsS --max-time 15 \
    -X POST \
    -H "Authorization: Bearer $CRON_MONITOR_TOKEN" \
    -H "Content-Type: application/json" \
    --data "{\"status\":\"$state\",\"message\":\"$message\"}" \
    "$CRON_MONITOR_URL/heartbeat/weekly-google-ads-review" >/dev/null ||
    echo "WARNING: Cron Monitor heartbeat failed"
}

cd "$ROOT"
source venv/bin/activate
if python weekly_ads_email.py; then
  heartbeat healthy "Weekly Google Ads report generated and accepted for delivery"
else
  STATUS=$?
  heartbeat failed "Weekly Google Ads report exited with status $STATUS"
  exit "$STATUS"
fi
