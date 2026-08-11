#!/bin/bash
# Free disk before pulling large base images (Playwright ~few GB).
set -euo pipefail
echo "[prebuild] Disk before prune:"
df -h /
if command -v docker >/dev/null 2>&1; then
  docker image prune -af || true
  docker builder prune -af || true
  docker system prune -af || true
fi
echo "[prebuild] Disk after prune:"
df -h /
