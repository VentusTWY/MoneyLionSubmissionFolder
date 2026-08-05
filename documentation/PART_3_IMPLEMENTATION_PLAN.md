# Part 3 - Automated ML System Implementation Plan

## Goal and definition of done

Build a production-oriented vertical slice in Python that runs independently from immutable data ingestion to a deployed, queryable LightGBM champion. The implementation is complete when one documented command can validate data, train and evaluate a challenger, produce a reproducible candidate bundle, apply promotion gates, update a local registry atomically, smoke-test inference, and leave the previous champion available for rollback.

This document records the implemented Part 3 boundaries, acceptance criteria, test scenarios, and interview demonstration sequence. The vertical slice is implemented in `src/pipeline.py`, `src/mlops.py`, `src/serving.py`, and `src/monitoring.py`.

## Scope

### Required vertical slice

1. Shared, deterministic training/inference feature transformation.
2. Data-quality and outcome-maturity validation.
3. Immutable run and candidate manifests.
4. Champion/challenger promotion gates.
5. Local versioned model registry with atomic promotion and rollback.
6. Framework-independent inference wrapper.
7. FastAPI prediction, model-info, liveness, readiness, and metrics endpoints.
8. Operational and delayed model-monitoring reports.
9. Unit, integration, failure-scenario, and end-to-end tests.
10. Docker packaging and reproducible commands/documentation.

### Deferred for the scope of this assessment

- Managed MLflow registry, DVC remote storage, cloud deployment, Kubernetes, streaming ingestion, an online feature store, canary traffic, and distributed orchestration.
- Broad hyperparameter search or AutoML. Candidate generation is one component; safe operation of model changes is the primary objective.

## Proposed structure

```text
src/
  contracts/       # request, feature-schema, manifest and config models
  data/            # ingestion, snapshot identity, quality and maturity
  features/        # shared deterministic transformer
  training/        # LightGBM trainer, evaluation and candidate creation
  promotion/       # gates and champion/challenger comparison
  registry/        # local immutable versions, champion pointer, rollback
  serving/         # predictor and FastAPI application
  monitoring/      # operational, drift and delayed-performance reports
  pipeline.py      # end-to-end orchestration entry point
configs/
  baseline.yaml
  promotion.yaml
  monitoring.yaml
tests/
  unit/
  integration/
  scenarios/
registry/          # generated locally; excluded from submission if appropriate
Dockerfile
Makefile
```

Existing modules should be refactored incrementally rather than rewritten at once. Each phase must keep the current model-development workflow executable.

## Phased implementation

### Phase 1 - Contracts and training-serving parity

- Split `build_features` into a target-independent `transform_features` and a training-only dataset builder.
- Define request, response, feature-schema, manifest, gate-result, and model-info contracts.
- Record ordered feature names, logical types, nullable fields, category behaviour, prediction point, and contract version.
- Make schema mismatches explicit errors; define controlled handling for missing Clarity reports and unseen categories.

**Acceptance:** identical raw rows generate identical ordered model inputs in training and inference; leakage fields cannot be enabled; malformed requests fail with actionable errors.

### Phase 2 - Reproducible runs and data controls

- Assign a unique run ID and immutable output directory.
- Calculate source and model checksums; capture code revision and dependency versions.
- Produce `manifest.json`, `feature_schema.json`, `config.yaml`, `metrics.json`, and `data_quality.json`.
- Add configurable outcome age/maturity and rolling date windows. Clearly mark the maturity approximation caused by missing status-event history.

**Acceptance:** rerunning a fixed snapshot/config is traceable and materially reproducible; missing columns, duplicate keys, insufficient mature rows, or one-class windows fail before training.

### Phase 3 - Promotion gates and registry

- Compare challenger and champion on identical evaluation rows.
- Implement hard gates for contracts, leakage, maturity, sample size, both classes, artifact reload, and smoke prediction.
- Implement configurable tolerance-based gates for ranking, log loss/calibration, stability, and later business value.
- Register every candidate immutably with accepted/rejected status.
- Promote through an atomic champion-pointer replacement under a simple lock; append an audit event and preserve the previous champion.
- Implement explicit rollback and automatic restoration after a failed post-promotion smoke test.

**Acceptance:** rejected candidates never alter the champion; interrupted promotion cannot expose a partial artifact; rollback restores a previously smoke-tested version.

### Phase 4 - Inference and service layer

- Implement `LoanRiskPredictor.from_registry()` independently of FastAPI.
- Load and validate the champion once at startup.
- Return probability, risk band/decision, model version, and feature-contract version.
- Add `POST /v1/predict`, `POST /v1/predict/batch`, `GET /v1/model`, `GET /health/live`, `GET /health/ready`, and `GET /metrics`.
- Add typed validation, batch limits, request IDs, structured errors, and logs that omit identifiers and sensitive feature values.

**Acceptance:** a promoted model can serve single and batch predictions; corrupt or incompatible artifacts fail readiness; the API does not reload the model per request.

### Phase 5 - Monitoring and packaging

- Expose request count, failures, latency, batch size, missing-feature/Clarity rates, and score-band counts.
- Generate offline feature/score drift reports before labels mature.
- Join mature outcomes later to report ROC-AUC, PR-AUC, log loss/calibration, score-band outcomes, temporal stability, and approved subgroup/business measures.
- Add Docker packaging with pinned dependencies, non-root execution, health check, and a reproducible local command.
- Document architecture, assumptions, commands, example outputs, troubleshooting, time spent, and limitations.

**Acceptance:** metrics identify the serving model version; no raw PII appears in logs; a clean checkout can run tests and the end-to-end demonstration using documented commands.

## Test matrix

### Unit tests

- Feature order/type enforcement and training-serving parity.
- Leakage exclusion, invalid dates, unseen categories, and missing Clarity handling.
- Manifest validation, checksums, gate tolerances, and threshold semantics.
- Registry pointer operations and audit-event contents.

### Integration and scenario tests

1. Valid snapshot produces a candidate, promotion, and successful prediction.
2. Missing required source column stops before training.
3. Insufficient mature outcomes or a one-class window rejects the run.
4. Candidate below a gate leaves the champion unchanged.
5. Feature-contract or checksum mismatch fails candidate validation/readiness.
6. Corrupt model fails reload and cannot be promoted.
7. Failed post-promotion smoke test restores the previous champion.
8. Batch limit and invalid payload return stable API errors.
9. Logs contain request/model IDs but not `anon_ssn` or raw application data.
10. Delayed outcomes produce a version-specific performance report.

## Planned commands and demo

```bash
make test
make pipeline                 # ingest -> train -> gate -> register -> deploy
make serve                    # start service using registry champion
curl localhost:8000/v1/model
curl -X POST localhost:8000/v1/predict ...
make simulate-bad-candidate   # demonstrate gate rejection
make rollback-demo            # promote, fail smoke check, restore champion
```

Interview narrative: a Data Scientist submits or generates a challenger; the MLE-owned system verifies its data and serving contract, evaluates it against the champion, promotes it atomically only after gates and smoke tests pass, serves versioned predictions, monitors immediate operational signals, and evaluates predictive/business performance once outcomes mature.

## Recommended build order and effort allocation

1. Contracts and shared transformation - 20%.
2. Run manifests, data controls, and tests - 20%.
3. Registry, gates, promotion, and rollback - 25%.
4. Predictor and API service - 20%.
5. Monitoring, Docker, end-to-end demo, and documentation - 15%.

Avoid further model tuning unless it resolves a demonstrated calibration or gate failure. The assessment's differentiating evidence should be reproducibility, safe candidate handoff, inference compatibility, deployment transaction integrity, observability, and recovery.
