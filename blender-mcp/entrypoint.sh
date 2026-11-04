#!/bin/bash
# Container entrypoint: Blender (headless) + MCP server (uvicorn) + nginx.
#
#   nginx :8080  ->  uvicorn 127.0.0.1:8000  ->  Blender bridge 127.0.0.1:9876
#
# Every part is supervised: if Blender dies it is restarted, and if the MCP
# server or nginx dies the container exits so the platform can restart it.
set -uo pipefail

DATA_DIR="${DATA_DIR:-/data}"
BRIDGE_PORT="${BLENDER_BRIDGE_PORT:-9876}"

log() { echo "[boot] $*"; }

mkdir -p "$DATA_DIR"/projects "$DATA_DIR"/renders "$DATA_DIR"/assets \
         "$DATA_DIR"/textures "$DATA_DIR"/exports "$DATA_DIR"/logs "$DATA_DIR"/backups

log "Debian ${DEBIAN_CODENAME:-unknown} | $(. /etc/os-release && echo "$PRETTY_NAME")"

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

start_blender() {
  log "starting headless Blender (bridge 127.0.0.1:${BRIDGE_PORT})"
  /opt/blender/blender -b --factory-startup --noaudio --python /app/blender_bridge.py \
      >>"$DATA_DIR/logs/blender.log" 2>&1 &
  BLENDER_PID=$!
}

# --- Blender ---------------------------------------------------------------
start_blender
for i in $(seq 1 180); do
  if bridge_up; then log "Blender bridge is up after ${i}s"; break; fi
  sleep 1
done
if ! bridge_up; then
  log "WARNING: Blender bridge not reachable yet - the MCP server will report 'degraded'"
fi

# Watchdog: bring Blender back if it crashes or is OOM-killed.
(
  while true; do
    sleep 20
    if ! bridge_up; then
      log "Blender bridge unreachable - restarting Blender"
      pkill -f blender_bridge.py 2>/dev/null
      sleep 2
      start_blender
      for _ in $(seq 1 120); do bridge_up && break; sleep 1; done
    fi
  done
) &
WATCHDOG_PID=$!

# --- MCP server ------------------------------------------------------------
python3 -u /app/mcp_server.py >>"$DATA_DIR/logs/mcp.log" 2>&1 &
APP_PID=$!
tail -n 0 -F "$DATA_DIR/logs/mcp.log" "$DATA_DIR/logs/blender.log" 2>/dev/null &
TAIL_PID=$!

# --- nginx -----------------------------------------------------------------
nginx -g 'daemon off;' >>"$DATA_DIR/logs/nginx.log" 2>&1 &
NGINX_PID=$!
log "nginx listening on 0.0.0.0:${NGINX_PORT:-8080}"

cleanup() {
  kill -TERM "$APP_PID" "$NGINX_PID" "$WATCHDOG_PID" "$TAIL_PID" "${BLENDER_PID:-}" 2>/dev/null
}
trap cleanup TERM INT

wait -n "$APP_PID" "$NGINX_PID"
log "MCP server or nginx exited - stopping the container so the platform restarts it"
cleanup
sleep 2
exit 1
