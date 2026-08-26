# Part 3 - Automated ML System Implementation

## Objective

Part 3 implements a production-shaped local vertical slice for controlled model
change. It demonstrates how a reproducible LightGBM candidate moves from
validated source data to a queryable champion while preserving traceability,
serving compatibility, and rollback safety.

The implemented path is:

```text
immutable source snapshots
  -> validate the modeling population and joins
  -> build deterministic application-time features
  -> train and evaluate a LightGBM challenger
  -> write and verify a versioned candidate bundle
  -> apply absolute and comparable champion-relative gates
  -> register the candidate immutably
  -> atomically update the champion pointer
  -> reload and smoke-test serving
  -> emit operational metadata and retain rollback state
```

The focus is the MLOps handoff and safety boundary. Managed cloud infrastructure
and business rules that cannot be supported by the supplied data are documented
as production extensions rather than simulated.

## Implementation layout

```text
src/
  training/
    data.py       # source loading, schema checks, and Clarity join
    labels.py     # resolved population and adverse-outcome target
    features.py   # shared transformation and persisted feature schema
    train.py      # temporal split, LightGBM training, and artifacts
    evaluate.py   # predictive and threshold metrics
    benchmark.py  # logistic and constant reference models
    pipeline.py   # end-to-end train, gate, register, and promote orchestration
  serving/
    predictor.py  # predictor, API contracts, routes, logs, and metrics
    api.py        # environment-configured ASGI entry point
  mlops.py        # gates, verification, registry, promotion, and rollback
  monitoring.py   # PSI drift and delayed-performance reports
configs/          # baseline, promotion, and monitoring configuration
tests/            # unit and integration-style tests
registry/         # generated local versions, audit log, and champion pointer
Dockerfile
docker-compose.yml
Makefile
```

The package structure separates offline model development and orchestration
from the online serving runtime. The shared feature transformer remains in the
training package and is imported by serving so both paths use the same persisted
feature contract rather than duplicating transformation logic.

## 1. Contracts and training-serving parity

Training and inference use the same target-independent `transform_features`
function. The training-only `build_features` wrapper removes the target and
returns the model matrix and labels.

Each candidate persists:

- Ordered feature names
- Logical number, boolean, and category types
- Nullability
- Training-time categorical vocabularies
- Feature-contract name and prediction point
- Explicitly excluded fields

Inference reconstructs this exact schema. Missing nullable fields are recreated,
missing required fields produce actionable errors, and unseen categories follow
the saved categorical vocabulary without changing feature order. Missing
Clarity reports are retained and represented through `has_clarity_report`.

Identifiers, repayment fields, outcome fields, and post-pricing fields are
excluded from the pre-pricing contract. A contract cannot explicitly enable a
known leakage field.

FastAPI uses Pydantic request and response models. `applicationDate` accepts an
ISO date or timestamp and rejects malformed values. The remaining model inputs
are checked against the champion's persisted schema, allowing nullable Clarity
fields to remain model-version-specific.

## 2. Reproducible runs and data controls

Every execution receives a timestamped UUID and a new, non-overwriting run
directory. A candidate bundle contains:

```text
manifest.json
config.yaml
model.joblib
features.json
feature_schema.json
metrics.json
threshold_analysis.json
data_cutoff.json
data_quality.json
gate_results.json
smoke_request.json
```

The manifest records the run version and timestamp, Git revision, feature and
target contracts, decision thresholds, source checksums, and checksums for every
tracked candidate artifact. Runtime provenance records:

- Python version
- Installed versions of pandas, PyArrow, LightGBM, scikit-learn, joblib, and
  PyYAML
- The filename and SHA-256 checksum of the pinned `requirements.txt`

This distinguishes the declared dependency set from the environment that
actually executed training.

The pipeline enforces required columns, unique non-null loan identifiers,
unique Clarity join identifiers, many-to-one join cardinality, non-empty
temporal splits, and a resolved population containing both target classes.
`data_quality.json` is assembled from these observed results and contains named
checks, observed counts, and an overall derived pass state.

The untouched test population is represented by a SHA-256 evaluation
fingerprint. It hashes the ordered evaluation identities, outcomes, label
policy, and evaluation configuration without persisting identifiers in the
metrics artifact. Identical fingerprints prove that stored challenger and
champion metrics refer to the same evaluation examples and policy.

## 3. Promotion gates and registry

Configurable absolute gates enforce:

- Minimum test population
- Both target classes
- Minimum ROC-AUC
- Maximum log loss

When a champion exists, the relative ROC-AUC tolerance is applied only if the
champion and challenger evaluation fingerprints match. If either fingerprint is
missing or different, the gate report records that the relative comparison was
not applied; the pipeline does not present metrics from different evaluation
sets as a direct regression comparison.

Every accepted or rejected candidate is copied to a unique version directory.
Before a bundle can be selected, the registry verifies its tracked checksums and
proves that the model can be deserialized by the current runtime.

Promotion is serialized with an exclusive local lock. The champion pointer is
written to a temporary file and atomically replaced, and the audit log records
the actor, reason, timestamp, previous champion, and new champion. The previous
version remains available for rollback.

A serving reload smoke test follows promotion. If it fails, the prior champion
pointer is restored automatically. Manual rollback also verifies and reloads
the target version; a failed rollback smoke test restores the model that was
active before the attempt.

The local registry implements the production boundary without introducing cloud
credentials into the submission. `ModelRegistry` allows a managed artifact and
metadata backend to replace it later.

## 4. Inference and service layer

`LoanRiskPredictor.from_registry()` is independent of FastAPI. It verifies and
loads the champion once when the application starts; ordinary prediction
requests neither reload nor retrain the model. Successful administration calls
reload the selected champion in-process.

Prediction responses contain:

- Adverse-outcome probability
- Low, medium, or high risk band
- Pass, review, or reject decision
- Model version
- Feature-contract version
- Request ID

The API provides single and bounded-batch prediction, active-model metadata,
liveness, readiness, Prometheus metrics, and protected model administration.
The complete endpoint reference is in [`SERVING_API.md`](SERVING_API.md).

A server-generated request ID is returned in the `X-Request-ID` header and in
single, batch-item, and handled error bodies. Prediction calls emit one JSON log
event containing only timestamp, request ID, route, HTTP status, latency, model
version, contract version, result count or decision summary, and error category.
Request bodies, identifiers, and feature values are not logged.

The current readiness strategy is fail-fast: an invalid or corrupt champion
prevents application startup. Once startup succeeds, `/health/ready` reports the
loaded model version.

## 5. Monitoring and packaging

The API exposes Prometheus-format counters for prediction requests, failures,
latency sum, and risk-band counts, labelled by serving model version.

Offline monitoring supports:

- Numeric population stability index reports before labels mature
- Version-specific ROC-AUC, PR-AUC, and log loss after outcomes mature
- An explicit insufficient-class result when delayed outcomes contain only one
  class

The repository includes pinned dependencies, a non-root API container, a
readiness health check, Docker Compose, Make targets, and documented local
commands. Training and serving select the registry through the same
`MODEL_REGISTRY_URI` interface.

## Verification

The automated suite covers:

- Target construction and anomalous-outcome quarantine
- Leakage exclusion and training/inference feature parity
- Invalid dates, unseen categories, and missing nullable Clarity fields
- Temporal splits and repeat-customer overlap reporting
- Stable evaluation fingerprints and comparable relative gates
- Derived data-quality reports
- Runtime and pinned-requirements provenance
- Gate rejection leaving the champion unchanged
- Registry promotion, rollback, checksum failure, and failed-smoke restoration
- Single and batch prediction, batch limits, and model-version responses
- Request IDs in successful and handled error responses
- Metadata-only logs that exclude identifiers and payload values
- Generated OpenAPI response schemas
- Protected administrative promotion and rollback with in-process reload
- Drift detection and model-version-specific delayed performance

Run all tests with:

```bash
make test
```

The verified suite contains 29 passing tests. An isolated end-to-end pipeline
run also produced an accepted candidate with runtime provenance, a non-sensitive
evaluation fingerprint, three passing derived quality checks, and passing
promotion gates.

## Demonstration sequence

Train the model before a timed presentation and use the prepared champion for a
short, deterministic demonstration:

1. Start the stack with `docker compose up --build`.
2. Call `/health/ready` and `/v1/model` to establish the active champion.
3. Submit a valid `/v1/predict` request and identify the probability, decision,
   request ID, model version, and contract version.
4. Submit an invalid request and show its controlled `422` response and request
   ID.
5. List registered candidates through the protected admin API or UI.
6. Promote a prepared candidate and show that `/v1/model` changes without an API
   restart.
7. Roll back and show that the previous champion is restored.
8. Show the audit entry, gate report, evaluation fingerprint, safe JSON log, and
   model-labelled service metrics.

The core commands are:

```bash
make test
make pipeline
make serve
curl -s http://localhost:8000/health/ready
curl -s http://localhost:8000/v1/model
./scripts/retrain_demo.sh
```

## Assumptions and production extensions

The supplied extract exposes current loan status but not a reliable timestamp
for when each outcome became observable. The POC therefore uses terminal status
as an explicitly documented maturity proxy. It does not claim a historically
exact performance window or rolling backtest.

The following require additional data, policy, infrastructure, or stakeholder
approval:

- A business-approved performance window and timestamped outcome history
- Expected-loss or other business-value promotion gates
- Legally approved fairness groups, metrics, and tolerances
- Calibration and stability limits approved for decision use
- Managed artifact storage and registry metadata
- Cloud IAM, Kubernetes, canary traffic, and distributed orchestration
- Production SLOs, retention, disaster recovery, and integration testing

These boundaries are intentional. The POC demonstrates that a candidate can be
validated, reproduced, compared when evidence is genuinely comparable,
registered immutably, promoted safely, served with traceability, and rolled back
without inventing unsupported production policy.
