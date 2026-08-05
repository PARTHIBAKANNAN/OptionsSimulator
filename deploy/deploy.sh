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

log "restarting $SERVICE"
sudo systemctl restart "$SERVICE"

log "polling $HEALTH_URL"
# The daily Fyers login now happens inside the engine's first loop tick (see
# LiveTrader.ensure_connection_state), not synchronously at process boot — so the health
# endpoint responds "ok" a beat before fyers_authenticated catches back up to its pre-deploy
# value. Keep polling (not just the first successful response) until it actually catches up,
# or genuinely fail after the full window instead of false-positive-rolling-back a good deploy.
PRE_FYERS=$(echo "$PRE_HEALTH" | json_field fyers_authenticated "null")
HEALTHY=0
for i in $(seq 1 20); do
  if curl -sf --max-time 3 "$HEALTH_URL" > /tmp/optionssimulator-health-post.json 2>/dev/null; then
    POST_STATUS=$(json_field status "unknown" < /tmp/optionssimulator-health-post.json)
    POST_FYERS=$(json_field fyers_authenticated "null" < /tmp/optionssimulator-health-post.json)
    if [ "$POST_STATUS" = "ok" ] && { [ "$PRE_FYERS" != "True" ] || [ "$POST_FYERS" = "True" ]; }; then
      HEALTHY=1
      break
    fi
  fi
  sleep 2
done
[ "$HEALTHY" -eq 1 ] || fail "backend did not become healthy (with Fyers auth restored) within 40s of restart (journalctl -u $SERVICE)"

POST_HEALTH=$(cat /tmp/optionssimulator-health-post.json)
log "deploy succeeded: $POST_HEALTH"
