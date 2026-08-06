#!/usr/bin/env bash
set -euo pipefail

# Retrain demo script
# Runs the pipeline to train a new challenger, then shows registry state.

HERE=$(cd "$(dirname "$0")" && pwd)
ROOT=$(cd "$HERE/.." && pwd)

cd "$ROOT"

echo "Starting retrain demo: running pipeline (configs/baseline.yaml)"
python -m src.pipeline --config configs/baseline.yaml

echo
echo "Registry versions (latest 10):"
ls -1 registry/versions | tail -n 10 || true

echo
echo "Current champion (champion.json):"
if [ -f registry/champion.json ]; then
  python -m json.tool registry/champion.json || cat registry/champion.json
else
  echo "(no champion.json present)"
fi

echo
echo "Recent audit lines (last 20):"
if [ -f registry/audit.jsonl ]; then
  tail -n 20 registry/audit.jsonl || true
else
  echo "(no registry/audit.jsonl present)"
fi

echo
echo "Retrain demo complete. If you're running the API under Docker Compose, restart the API container to pick up a new champion:"
echo "  docker compose restart api"
