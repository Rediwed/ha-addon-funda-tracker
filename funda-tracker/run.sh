#!/bin/sh
# run.sh — HA add-on entrypoint

set -e

VERSION=$(grep '^version:' /app/config.yaml 2>/dev/null | sed 's/version: *"\(.*\)"/\1/' || echo "unknown")
export FUNDA_ADDON_VERSION="$VERSION"

echo "============================================================"
echo "  Funda Tracker Add-on v${VERSION}"
echo "============================================================"
echo ""

exec python3 /app/scheduler.py
