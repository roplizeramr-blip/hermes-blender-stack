#!/bin/bash
# Container entrypoint: Blender (headless) + MCP server (uvicorn) + nginx.
#
#   nginx :8080  ->  uvicorn 127.0.0.1:8000  ->  Blender bridge 127.0.0.1:9876
#
# Startup order matters: nginx and the MCP server come up FIRST so the
# platform health check always gets an answer, while Blender boots in the
# background. The MCP server reports "degraded" until the bridge is ready.
# Every part is supervised: if Blender dies it is restarted, and if the MCP
# server or nginx dies the container exits so the platform can restart it.
set -uo pipefail

DATA_DIR="${DATA_DIR:-/data}"
BRIDGE_PORT="${BLENDER_BRIDGE_PORT:-9876}"
NGINX_PORT="${NGINX_PORT:-8080}"

log() { echo "[boot] $*"; }

mkdir -p "$DATA_DIR"/projects "$DATA_DIR"/renders "$DATA_DIR"/assets \
         "$DATA_DIR"/textures "$DATA_DIR"/exports "$DATA_DIR"/logs "$DATA_DIR"/backups \
  2>/dev/null || log "WARNING: could not create the data directories under $DATA_DIR"

# Fall back to /tmp when the volume is not writable, so logs never vanish.
LOG_DIR="$DATA_DIR/logs"
if ! touch "$LOG_DIR/.probe" 2>/dev/null; then
  LOG_DIR=/tmp/blender-mcp-logs
  mkdir -p "$LOG_DIR" 2>/dev/null
  log "WARNING: $DATA_DIR/logs is not writable - logging to $LOG_DIR"
fi
rm -f "$LOG_DIR/.probe" 2>/dev/null
BLENDER_LOG="$LOG_DIR/blender.log"
MCP_LOG="$LOG_DIR/mcp.log"
NGINX_LOG="$LOG_DIR/nginx.log"
: >"$BLENDER_LOG" 2>/dev/null
: >"$MCP_LOG" 2>/dev/null
: >"$NGINX_LOG" 2>/dev/null

log "Debian ${DEBIAN_CODENAME:-unknown} | $(. /etc/os-release 2>/dev/null && echo "$PRETTY_NAME")"
log "data dir: $DATA_DIR | logs: $LOG_DIR"

# --- helpers ---------------------------------------------------------------
bridge_up() {
  python3 - "$BRIDGE_PORT" <<'PY'
import socket, sys
try:
    socket.create_connection(("127.0.0.1", int(sys.argv[1])), 2).close()
except OSError:
    sys.exit(1)
PY
}

dump_blender_log() {
  echo "[blender] --- last log lines ---"
  tail -n 25 "$BLENDER_LOG" 2>/dev/null | sed 's/^/[blender] /'
}

start_blender() {
  log "starting headless Blender (bridge 127.0.0.1:${BRIDGE_PORT})"
  /opt/blender/blender -b --factory-startup --noaudio --python /app/blender_bridge.py \
      >>"$BLENDER_LOG" 2>&1 &
  BLENDER_PID=$!
  sleep 3
  if ! kill -0 "$BLENDER_PID" 2>/dev/null; then
    log "ERROR: Blender exited immediately"
    dump_blender_log
  fi
}

# --- log streaming ---------------------------------------------------------
# Tail the Blender/MCP logs into the container log from the very first second,
# so a Blender start-up failure is visible without needing the MCP server.
tail -n 0 -F "$BLENDER_LOG" "$MCP_LOG" 2>/dev/null &
TAIL_PID=$!

# --- Blender ---------------------------------------------------------------
start_blender

# --- nginx -----------------------------------------------------------------
# Started immediately: the public port must answer while Blender is still
# booting, otherwise the platform's health check sees a dead app and restarts it.
nginx -g 'daemon off;' >>"$NGINX_LOG" 2>&1 &
NGINX_PID=$!
log "nginx listening on 0.0.0.0:${NGINX_PORT}"

# --- MCP server ------------------------------------------------------------
python3 -u /app/mcp_server.py >>"$MCP_LOG" 2>&1 &
APP_PID=$!

# --- bridge readiness + watchdog -------------------------------------------
(
  for i in $(seq 1 300); do
    if bridge_up; then
      echo "[boot] Blender bridge is up after ${i}s"
      break
    fi
    sleep 1
  done
  if ! bridge_up; then
    echo "[boot] WARNING: Blender bridge not reachable yet - the MCP server reports 'degraded'"
    dump_blender_log
  fi
  # Watchdog: bring Blender back if it crashes or is OOM-killed.
  while true; do
    sleep 20
    if ! bridge_up; then
      echo "[boot] Blender bridge unreachable - restarting Blender"
      pkill -f blender_bridge.py 2>/dev/null || true
      sleep 2
      start_blender
      for _ in $(seq 1 120); do bridge_up && break; sleep 1; done
    fi
  done
) &
WATCHDOG_PID=$!

cleanup() {
  kill -TERM "$APP_PID" "$NGINX_PID" "$WATCHDOG_PID" "$TAIL_PID" "${BLENDER_PID:-}" 2>/dev/null
}
trap cleanup TERM INT

wait -n "$APP_PID" "$NGINX_PID"
log "MCP server or nginx exited - stopping the container so the platform restarts it"
cleanup
sleep 2
exit 1
