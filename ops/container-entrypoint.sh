#!/bin/sh
set -eu

# API runtime container receives only the least-privilege DATABASE_URL.
# Role bootstrap and migrations run in separate short-lived services.
exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 1
