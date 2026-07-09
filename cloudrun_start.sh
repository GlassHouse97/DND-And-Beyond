#!/bin/sh
set -eu

redis-server --save "" --appendonly no --protected-mode no &
redis_pid=$!

reflex run --env prod --backend-only &
backend_pid=$!

python - <<'PY'
import socket
import sys
import time

deadline = time.time() + 60
while time.time() < deadline:
    with socket.socket() as sock:
        sock.settimeout(1)
        try:
            sock.connect(("127.0.0.1", 8000))
        except OSError:
            time.sleep(1)
        else:
            sys.exit(0)

print("Reflex backend did not open port 8000 within 60 seconds.", file=sys.stderr)
sys.exit(1)
PY

caddy run --config /app/Caddyfile --adapter caddyfile &
caddy_pid=$!

shutdown() {
    kill "$caddy_pid" "$backend_pid" "$redis_pid" 2>/dev/null || true
}
trap shutdown TERM INT

while true; do
    if ! kill -0 "$backend_pid" 2>/dev/null; then
        wait "$backend_pid"
        exit $?
    fi
    if ! kill -0 "$caddy_pid" 2>/dev/null; then
        wait "$caddy_pid"
        exit $?
    fi
    sleep 5
done
