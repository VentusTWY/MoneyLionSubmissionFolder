# Loan Risk Predictor

`loan-risk-predictor` is a complete, production-shaped prediction application
with a reproducible LightGBM workflow. It trains versioned challengers, applies
promotion gates, maintains an auditable model registry, serves the champion
through FastAPI, and provides the LoanRiskCalculator browser decision UI.

## Contents

- `notebooks/`: executed analysis in notebook and HTML formats.
- `documentation/`: system design, implementation details, target definition,
  data preparation, and model caveats.
- `src/`: ingestion, validation, feature, training, registry, serving, and
  monitoring modules.
- `configs/`: training, promotion-gate, and monitoring configuration.
- `tests/`: automated feature, label, training, serving, and registry tests.
- `ui/`: the LoanRiskCalculator browser interface.

## Prepare the supplied inputs

Place the original assessment files at the following paths. Raw inputs are not
included in the submission archive or Git repository.

```text
data/raw/loan.parquet
data/raw/payment.parquet
data/raw/clarity_underwriting_variables.parquet
```

## Run the pipeline

From the submission directory:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m pytest -q
python -m src.pipeline --config configs/baseline.yaml
```

Generated state is written to:

```text
artifacts/runs/<run-id>/
registry/versions/<run-id>/
registry/champion.json
registry/audit.jsonl
```

Every candidate is registered for audit. A rejected candidate does not change
the champion. A successful promotion atomically updates `champion.json` while
retaining the previous version for rollback.

### Train a second challenger

Every pipeline invocation receives a new timestamped version. After the first
run, execute the same command again to train a second candidate and compare it
with the current champion:

```bash
python -m src.pipeline --config configs/baseline.yaml
```

Inspect every registered version, the active champion, and promotion history:

```bash
ls -1 registry/versions
python -m json.tool registry/champion.json
tail -n 5 registry/audit.jsonl
```

If the challenger passes all quality and performance gates, the champion
pointer moves to the new version and records `previous_version`. If it fails,
the candidate remains registered for audit while the champion is unchanged.
Restart the API after a promotion because it loads the champion once at
startup.

## Start Loan Risk Predictor with Docker

After generating at least one champion, start the complete application from
the submission directory:

```bash
docker compose up --build
```

Docker Compose builds and starts both services:

- Loan Risk Predictor UI (LoanRiskCalculator): `http://localhost:3000`
- FastAPI service: `http://localhost:8000`
- Interactive API documentation: `http://localhost:8000/docs`

The registry is mounted read-only into the API container. The UI waits for the
API health check before starting. Stop both services with `Ctrl+C`, or from
another terminal with:

```bash
docker compose down
```

While the stack is running, check readiness and inspect the active model from a
second terminal:

```bash
curl -s http://localhost:8000/health/ready | python -m json.tool
curl -s http://localhost:8000/v1/model | python -m json.tool
```

Submit a single prediction:

```bash
curl -s -X POST http://localhost:8000/v1/predict \
  -H "Content-Type: application/json" \
  -d '{
    "applicationDate": "2026-08-05T12:00:00Z",
    "loanAmount": 500,
    "leadCost": 25,
    "leadType": "bvMandatory",
    "payFrequency": "B",
    "state": "CA",
    "has_clarity_report": false
  }' | python -m json.tool
```

Submit a batch prediction:

```bash
curl -s -X POST http://localhost:8000/v1/predict/batch \
  -H "Content-Type: application/json" \
  -d '[
    {
      "applicationDate": "2026-08-05T12:00:00Z",
      "loanAmount": 300,
      "leadCost": 15,
      "leadType": "bvMandatory",
      "payFrequency": "B",
      "state": "AK",
      "has_clarity_report": false
    },
    {
      "applicationDate": "2026-08-05T12:00:00Z",
      "loanAmount": 1200,
      "leadCost": 40,
      "leadType": "bvMandatory",
      "payFrequency": "M",
      "state": "CA",
      "has_clarity_report": false
    }
  ]' | python -m json.tool
```

Batch JSON example (for the UI "Batch" mode):

```json
[
  {
    "applicationDate": "2026-08-05",
    "loanAmount": 300,
    "leadCost": 15,
    "leadType": "bvMandatory",
    "payFrequency": "B",
    "state": "AK",
    "has_clarity_report": false
  },
  {
    "applicationDate": "2026-08-05",
    "loanAmount": 1200,
    "leadCost": 40,
    "leadType": "others",
    "payFrequency": "M",
    "state": "Other",
    "has_clarity_report": false
  }
]
```

Note: selecting `"others"` for `leadType` or `"Other"` for `state` signals new/unmapped values and the UI will show a warning.

Prometheus-style metrics are available at `http://localhost:8000/metrics`.

## Run services separately during development

Docker Compose is the recommended production-shaped local workflow. For UI
development with hot reload, first run the API by itself:

```bash
docker compose up --build api
```

Then start the UI in another terminal:

```bash
cd ui
npm install
npm run dev
```

Open `http://localhost:3000`. The UI checks API readiness, displays the active
model and decision threshold, validates application inputs, submits a prediction,
and presents the probability, risk band, recommended action, request ID, and
model version.

For a production UI build:

```bash
cd ui
npm install
npm run build
```

The UI uses `http://localhost:8000` by default. Configure a deployed API before
building with:

```bash
NEXT_PUBLIC_API_BASE_URL=https://api.example.com npm run build
```

Set the API's comma-separated `UI_ORIGINS` environment variable to the exact
deployed UI origins. It defaults to `http://localhost:3000`; wildcard origins
are intentionally not enabled.

## Reference result

On the supplied data, the primary `pre_pricing_v1` LightGBM run uses 18,433
training rows, 4,255 validation rows, and 5,672 chronological test rows. Its
held-out ROC-AUC is approximately 0.737 and PR-AUC approximately 0.849. See the
executed notebook and generated run metadata for complete evidence and caveats.
