#!/usr/bin/env bash
# Runs ON THE VM after `git reset --hard origin/main` (see .github/workflows/deploy.yml).
# Mirrors TradeDashBoard's deploy/deploy.sh shape: flock lock, PREV_SHA rollback, frontend
# build, systemd restart, health poll with rollback on failure. DB migrations are NOT run here —
# same as TradeDashBoard, they're a manual one-time step via the Supabase SQL editor
# (see backend/migrations/001_options_positions.sql).
set -euo pipefail

APP_DIR="/home/ubuntu/optionssimulator-app"
SERVICE="optionssimulator-backend"
LOCK_FILE="/tmp/optionssimulator-deploy.lock"
HEALTH_URL="http://127.0.0.1:8001/api/health"
PREV_SHA="${PREV_SHA:-}"

cd "$APP_DIR"

exec 200>"$LOCK_FILE"
flock -n 200 || { echo "[deploy] ERROR: another deploy is already in progress (lock held on $LOCK_FILE)" >&2; exit 1; }

log() { echo "[deploy] $*"; }

json_field() {
  python3 -c "import sys,json; print(json.load(sys.stdin).get('$1','$2'))" 2>/dev/null || echo "$2"
}

health_snapshot() {
  curl -sf --max-time 3 "$HEALTH_URL" 2>/dev/null || echo '{}'
}

rollback() {
  if [ -n "$PREV_SHA" ]; then
    log "rolling back to $PREV_SHA"
    git reset --hard "$PREV_SHA"
    sudo systemctl restart "$SERVICE" || true
  fi
}

fail() {
  echo "[deploy] ERROR: $*" >&2
  rollback
  exit 1
}

PRE_HEALTH=$(health_snapshot)
log "pre-deploy health: $PRE_HEALTH"

log "installing backend + core dependencies"
source venv/bin/activate
pip install -q -r requirements.txt
pip install -q -r backend/requirements.txt

log "building frontend"
(cd frontend && npm ci && npm run build)

log "running recent market backfill to seed candles and market state"
python3 scripts/backfill_recent_candles.py || true

log "ensuring Alice Blue environment variables are present in .env"
if [ -f .env ]; then
  grep -q "^BROKER=" .env && sed -i 's/^BROKER=.*/BROKER=aliceblue/' .env || echo "BROKER=aliceblue" >> .env
  grep -q "^ALICEBLUE_USER_ID=" .env || echo "ALICEBLUE_USER_ID=2628887" >> .env
  grep -q "^ALICEBLUE_PASSWORD=" .env || echo "ALICEBLUE_PASSWORD=Thalamsd&7781" >> .env
  grep -q "^ALICEBLUE_TOTP_KEY=" .env || echo "ALICEBLUE_TOTP_KEY=NDAWXZFBTOUJKUBDGOSJMJBYZKFYGPDR" >> .env
  grep -q "^ALICEBLUE_APP_CODE=" .env || echo "ALICEBLUE_APP_CODE=82a1c6alep" >> .env
  grep -q "^ALICEBLUE_API_KEY=" .env || echo "ALICEBLUE_API_KEY=8G93PYak2ciy9jBAW9vjV6v7bLUJPvf8kVmFXySPcYqjkclvtKuYc5WIZi7gEQUyDkqfiNsX2lmc7XOpQ1WriuYA3m6D3cKxfZYE" >> .env
fi

log "restarting $SERVICE"
sudo systemctl restart "$SERVICE"

log "polling $HEALTH_URL"
# The daily broker login now happens inside the engine's first loop tick (see
# LiveTrader.ensure_connection_state), not synchronously at process boot — so the health
# endpoint responds "ok" a beat before broker_authenticated catches back up to its pre-deploy
# value. Keep polling (not just the first successful response) until it actually catches up,
# or genuinely fail after the full window instead of false-positive-rolling-back a good deploy.
#
# Only REQUIRE that catch-up if it's actually past today's daily-login gate (08:50 IST, Mon-Fri —
# mirrors DAILY_LOGIN_TIME in src/trader.py). A deploy overnight or on a weekend restarts into a
# process that correctly hasn't logged in yet (by design, not by breakage) and won't until the
# next gate — the broker_authenticated check would otherwise time out and roll back a perfectly
# good deploy every single time outside that window.
IST_HHMM=$(TZ=Asia/Kolkata date +%H%M)
IST_DOW=$(TZ=Asia/Kolkata date +%u)  # 1=Monday .. 7=Sunday
PAST_LOGIN_GATE=0
if [ "$IST_DOW" -le 5 ] && [ "$IST_HHMM" -ge 0850 ] && [ "$IST_HHMM" -lt 1535 ]; then
  PAST_LOGIN_GATE=1
fi

PRE_BROKER=$(echo "$PRE_HEALTH" | json_field broker_authenticated "$(echo "$PRE_HEALTH" | json_field aliceblue_authenticated "$(echo "$PRE_HEALTH" | json_field fyers_authenticated "null")")")
HEALTHY=0
for i in $(seq 1 20); do
  if curl -sf --max-time 3 "$HEALTH_URL" > /tmp/optionssimulator-health-post.json 2>/dev/null; then
    POST_STATUS=$(json_field status "unknown" < /tmp/optionssimulator-health-post.json)
    POST_BROKER=$(json_field broker_authenticated "$(json_field aliceblue_authenticated "null" < /tmp/optionssimulator-health-post.json)" < /tmp/optionssimulator-health-post.json)
    if [ "$POST_STATUS" = "ok" ] && { [ "$PRE_BROKER" != "True" ] || [ "$PAST_LOGIN_GATE" -eq 0 ] || [ "$POST_BROKER" = "True" ]; }; then
      HEALTHY=1
      break
    fi
  fi
  sleep 2
done
[ "$HEALTHY" -eq 1 ] || fail "backend did not become healthy (with broker auth restored) within 40s of restart (journalctl -u $SERVICE)"

POST_HEALTH=$(cat /tmp/optionssimulator-health-post.json)
log "deploy succeeded: $POST_HEALTH"
