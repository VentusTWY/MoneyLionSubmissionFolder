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
- The UI supports `Single` and `Batch` modes. Use `leadType: "others"` or `state: "Other"` to indicate new/unmapped categories; the UI will display a warning.
- For full implementation details, model metrics, and caveats see `documentation/`.

> TODO: remove the PDF file from the repo tomorrow and push the final branch.

If you want, I can also add a `DEMO.md` with a one-command demo script or prepare a minimal Docker image for the UI only.

Retraining demo
----------------

To demonstrate retraining during your presentation, run the pipeline to train a new challenger and inspect the registry. The included helper script automates the common steps:

```bash
./scripts/retrain_demo.sh
```

Notes:
- Run the script from the repository root. It requires the Python environment and dependencies used by the pipeline (see above `python -m pip install -r requirements.txt`).
- By default the challenger is derived from `configs/baseline.yaml` with `max_depth=6` and `num_leaves=31`; all other training parameters remain unchanged. Override these for another controlled experiment, for example: `RETRAIN_MAX_DEPTH=4 RETRAIN_NUM_LEAVES=15 ./scripts/retrain_demo.sh`.
- Each pipeline invocation creates a timestamped candidate under `registry/versions/`. The script prints recent versions, the active `registry/champion.json`, and the tail of `registry/audit.jsonl`.
- If Docker Compose is running the API, restart the API container to pick up a new champion: `docker compose restart api`.
