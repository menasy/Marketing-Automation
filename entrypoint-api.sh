#!/bin/sh
set -e

# Ensure output directory is writable by appuser regardless of host ownership.
# The bind-mount from host may contain files owned by a different UID.
if [ -d /app/output ]; then
    chmod -R a+rw /app/output 2>/dev/null || true
fi

exec uvicorn src.presentation.api.app:app --host 0.0.0.0 --port 8000
