#!/usr/bin/env bash
set -euo pipefail

# Default values can be overridden at runtime via environment variables
: "${UVICORN_HOST:=0.0.0.0}"
: "${UVICORN_PORT:=8000}"
: "${UVICORN_WORKERS:=2}"
: "${UVICORN_LOG_LEVEL:=info}"

# Provide visibility for debugging deployments
echo "Starting Uvicorn with ${UVICORN_WORKERS} worker(s) on ${UVICORN_HOST}:${UVICORN_PORT}"

exec uvicorn src.main:app \
    --host "${UVICORN_HOST}" \
    --port "${UVICORN_PORT}" \
    --workers "${UVICORN_WORKERS}" \
    --log-level "${UVICORN_LOG_LEVEL}" \
    --proxy-headers \
    --forwarded-allow-ips="*"
