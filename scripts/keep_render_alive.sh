#!/usr/bin/env bash
# Amour AI - Render Keep-Alive Script
# Pings the backend every 9 minutes to keep the Render server warm and prevent spin-down.

TARGET_URL="https://amour-ai-d6a8.onrender.com/api/memory/status/"
INTERVAL=540  # 9 minutes (Render free tier spins down after 15 min of inactivity)
LOG_FILE="${HOME}/Library/Logs/amour_keepalive.log"

mkdir -p "$(dirname "$LOG_FILE")"

echo "[$(date '+%Y-%m-%d %H:%M:%S')] Starting Amour AI Render Keep-Alive monitor..." >> "$LOG_FILE"

while true; do
    TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')
    HTTP_CODE=$(curl -s -m 30 -o /dev/null -w "%{http_code}" "$TARGET_URL" 2>/dev/null)
    if [ "$HTTP_CODE" = "200" ]; then
        echo "[$TIMESTAMP] SUCCESS: Render server is awake (HTTP 200)" >> "$LOG_FILE"
    else
        echo "[$TIMESTAMP] NOTICE: Server responded with HTTP ${HTTP_CODE:-FAILED}" >> "$LOG_FILE"
    fi
    sleep "$INTERVAL"
done
