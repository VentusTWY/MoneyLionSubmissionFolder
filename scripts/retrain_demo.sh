#!/usr/bin/env bash
set -euo pipefail

# Retrain demo script
# Trains a depth-constrained challenger, then shows registry state.

HERE=$(cd "$(dirname "$0")" && pwd)
ROOT=$(cd "$HERE/.." && pwd)

cd "$ROOT"

BASE_CONFIG=${RETRAIN_BASE_CONFIG:-configs/baseline.yaml}
MAX_DEPTH=${RETRAIN_MAX_DEPTH:-6}
NUM_LEAVES=${RETRAIN_NUM_LEAVES:-31}
PYTHON=${PYTHON:-python}
CHALLENGER_CONFIG=$(mktemp "${TMPDIR:-/tmp}/loan-risk-retrain.XXXXXX")
trap 'rm -f "$CHALLENGER_CONFIG"' EXIT

# Derive the challenger from the baseline so that the experiment changes only
# tree complexity. The pipeline copies this effective config into the immutable
# run and registry bundles before this temporary file is removed.
"$PYTHON" - "$BASE_CONFIG" "$CHALLENGER_CONFIG" "$MAX_DEPTH" "$NUM_LEAVES" <<'PY'
import sys
from pathlib import Path

import yaml

base_path, output_path, max_depth_value, num_leaves_value = sys.argv[1:]
try:
    max_depth = int(max_depth_value)
    num_leaves = int(num_leaves_value)
except ValueError as exc:
    raise SystemExit("RETRAIN_MAX_DEPTH and RETRAIN_NUM_LEAVES must be integers") from exc

if max_depth <= 0 or num_leaves <= 1:
    raise SystemExit("RETRAIN_MAX_DEPTH must be positive and RETRAIN_NUM_LEAVES must exceed 1")
if num_leaves > 2**max_depth:
    raise SystemExit("RETRAIN_NUM_LEAVES must not exceed 2^RETRAIN_MAX_DEPTH")

with Path(base_path).open(encoding="utf-8") as handle:
    config = yaml.safe_load(handle)
config["model"]["max_depth"] = max_depth
config["model"]["num_leaves"] = num_leaves
Path(output_path).write_text(
    yaml.safe_dump(config, sort_keys=False),
    encoding="utf-8",
)
PY

echo "Starting retrain demo from $BASE_CONFIG"
echo "Challenger overrides: max_depth=$MAX_DEPTH, num_leaves=$NUM_LEAVES"
"$PYTHON" -m src.pipeline --config "$CHALLENGER_CONFIG"

echo
echo "Registry versions (latest 10):"
ls -1 registry/versions | tail -n 10 || true

echo
echo "Current champion (champion.json):"
if [ -f registry/champion.json ]; then
  "$PYTHON" -m json.tool registry/champion.json || cat registry/champion.json
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
