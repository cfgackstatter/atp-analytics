#!/usr/bin/env bash
# Print the first free TCP port at or above START (default 8000).
# Usage: find-free-port.sh [START] [MAX_TRIES]

set -euo pipefail

START="${1:-8000}"
MAX_TRIES="${2:-30}"

if ! [[ "$START" =~ ^[0-9]+$ ]] || ! [[ "$MAX_TRIES" =~ ^[0-9]+$ ]]; then
  echo "Usage: $0 [START_PORT] [MAX_TRIES]" >&2
  exit 2
fi

port_in_use() {
  local port=$1
  if command -v lsof >/dev/null 2>&1; then
    lsof -tiTCP:"$port" -sTCP:LISTEN >/dev/null 2>&1
    return $?
  fi
  if command -v ss >/dev/null 2>&1; then
    ss -ltnH "sport = :$port" 2>/dev/null | grep -q .
    return $?
  fi
  python3 - "$port" <<'PY'
import socket, sys
port = int(sys.argv[1])
s = socket.socket()
try:
    s.bind(("0.0.0.0", port))
except OSError:
    sys.exit(0)  # in use
else:
    sys.exit(1)  # free
finally:
    s.close()
PY
}

port=$START
tries=0
while (( tries < MAX_TRIES )); do
  if ! port_in_use "$port"; then
    echo "$port"
    exit 0
  fi
  port=$((port + 1))
  tries=$((tries + 1))
done

echo "Error: no free port in range ${START}–$((START + MAX_TRIES - 1))." >&2
exit 1
