#!/bin/bash
set -e

cd backend
echo "=== Starting Django (gunicorn) on 127.0.0.1:8000 ==="
gunicorn decisiobi.wsgi:application --bind 127.0.0.1:8000 --workers 1 --timeout 120 --access-logfile - --error-logfile - &
GUNICORN_PID=$!
cd ..

# Wait for Django to be ready (max 60s)
echo "=== Waiting for Django to respond ==="
READY=0
for i in $(seq 1 30); do
  if curl -s -o /dev/null http://127.0.0.1:8000/; then
    READY=1
    echo "=== Django is up ==="
    break
  fi
  if ! kill -0 $GUNICORN_PID 2>/dev/null; then
    echo "!!! Gunicorn exited early. Check logs above."
    exit 1
  fi
  sleep 2
done

if [ "$READY" -ne 1 ]; then
  echo "!!! Django did not become ready in time. Gunicorn logs above."
  exit 1
fi

cd decision-spark
echo "=== Starting Node SSR server ==="
exec node server-node.mjs
