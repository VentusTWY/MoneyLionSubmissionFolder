# Loan Risk Predictor — Demo Quickstart

This repository contains a production-shaped LightGBM scoring and serving demo. The long-form implementation and design documents are in `documentation/`. This `README.md` is a concise demo-runner for presentations.

Prerequisites

- Python 3.11+ and `pip` (or use the provided Docker Compose stack)
- Node 22+ (for the UI) if running the UI locally

Quick demo (fastest with Docker Compose)

```bash
# Build and start both API and UI
docker compose up --build

# Check readiness and model
curl -s http://localhost:8000/health/ready | python -m json.tool
curl -s http://localhost:8000/v1/model | python -m json.tool

# Single prediction example
curl -s -X POST http://localhost:8000/v1/predict \
  -H "Content-Type: application/json" \
  -d '{"applicationDate":"2026-08-05T12:00:00Z","loanAmount":500,"leadCost":25,"leadType":"bvMandatory","payFrequency":"B","state":"CA","has_clarity_report":false}' | python -m json.tool

# Batch prediction example (POST the JSON array)
curl -s -X POST http://localhost:8000/v1/predict/batch \
  -H "Content-Type: application/json" \
  -d '[{"applicationDate":"2026-08-05","loanAmount":300,"leadCost":15,"leadType":"bvMandatory","payFrequency":"B","state":"AK","has_clarity_report":false}]' | python -m json.tool
```

Run UI locally (optional)

```bash
cd ui
npm install
npm run dev
# open http://localhost:3000
```

Minimal required inputs

- Place raw input files under `data/raw/`:
  - `loan.parquet`
  - `payment.parquet`
  - `clarity_underwriting_variables.parquet`

Notes

- The UI supports `Single` and `Batch` modes. Both category selectors display
  **Other / unmapped** consistently; batch API values remain
  `leadType: "others"` and `state: "Other"`.
- For full implementation details, model metrics, and caveats see `documentation/`.

## Registry backend configuration

Training and serving select the model registry through one URI:

```bash
# Self-contained demo (the default)
export MODEL_REGISTRY_URI=file://registry

# Production extension point (intentionally not installed in this demo)
export MODEL_REGISTRY_URI=s3://loan-risk-models/registry
```

`file://registry` selects the tested local registry with immutable version
directories, atomic champion-pointer replacement, locking, audit history, and
rollback. The same URI is accepted by the pipeline's `--registry` option and by
the API environment. Plain filesystem paths remain supported for tests and local
scripts.

The `s3://` value currently fails with an explicit production-backend message;
it does not silently emulate local filesystem semantics. The intended adapter
stores immutable model bundles in versioned S3 objects and uses DynamoDB (or an
equivalent transactional metadata store) for champion-pointer updates and
promotion locking. This keeps the demo credential-free while making the
production replacement boundary visible and testable.

## Retraining demo

Running the pipeline again to demo training a new challenger and inspect the registry. The included helper script automates the common steps:

```bash
./scripts/retrain_demo.sh
```

Notes:

- Run the script from the repository root. It requires the Python environment and dependencies used by the pipeline (see above `python -m pip install -r requirements.txt`).
- By default the challenger is derived from `configs/baseline.yaml` with `max_depth=6` and `num_leaves=31`; all other training parameters remain unchanged. Override these for another controlled experiment, for example: `RETRAIN_MAX_DEPTH=4 RETRAIN_NUM_LEAVES=15 ./scripts/retrain_demo.sh`.
- Each pipeline invocation creates a timestamped candidate under `registry/versions/`. The script prints recent versions, the active `registry/champion.json`, and the tail of `registry/audit.jsonl`.
- If Docker Compose is running the API, restart the API container to pick up a new champion: `docker compose restart api`.

## Admin model operations

The scoring UI always uses the approved champion; model changes are made through the admin workflow. For local POC use, it runs in admin mode by default. To protect the API, set a non-empty secret before starting it:

```bash
export ADMIN_API_KEY='use-a-long-random-secret'
docker compose up --build
```

An operator can inspect registered versions, then promote a version or roll back to the previous champion. When a key is configured, enter it in the **Model operations** panel. Each change requires an actor and reason and is appended to `registry/audit.jsonl`. The API reloads the verified champion in-process before it confirms the change, so a container restart is not required for this workflow.

Never expose the admin API key through `NEXT_PUBLIC_*` UI configuration or commit it to the repository. For a production deployment, replace this shared-key POC control with your organisation's authenticated identity provider and role-based access controls.
