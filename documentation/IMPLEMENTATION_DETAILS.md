# Part 3 Supporting Implementation Details

> This supports the Part 3 implementation and is not part of the two-page Part
> 2 response.

## Current POC components

- `configs/baseline.yaml` defines target policy, chronological split, LightGBM
  parameters, output location, and the `pre_pricing_v1` feature contract.
- `src/training/data.py` validates and joins loan and Clarity inputs. Payment loading is a
  separate outcome-audit path.
- `src/training/labels.py` constructs the resolved funded-loan population and reports
  inconsistent terminal outcomes.
- `src/training/features.py` creates application-time components, enforces permanent
  leakage exclusions, and applies configurable feature contracts.
- `src/training/train.py` trains and evaluates the LightGBM candidate and writes a model,
  ordered feature list, metrics, threshold analysis, confusion matrix, and data
  cutoff metadata.
- `src/training/benchmark.py` uses the same data and split to train an imputed,
  one-hot-encoded, regularized logistic regression and reports a constant
  predictor for context.
- `src/training/evaluate.py` implements common held-out metrics and threshold analysis.
- `src/serving/predictor.py` contains champion loading, prediction contracts,
  FastAPI routes, administration controls, and service metrics.
- `src/serving/api.py` is the environment-configured ASGI entry point.
- `tests/` covers labels, temporal ordering, leakage exclusions, and the
  pre-pricing feature contract.

Run from the repository root:

```bash
python -m pytest -q
python -m src.training.train --config configs/baseline.yaml
python -m src.training.benchmark --config configs/baseline.yaml \
  --output-dir artifacts/prepricing_logistic
```

## Reproducible run contract

Each run should eventually receive a unique run ID and immutable directory:

```text
artifacts/runs/<run-id>/
  model.joblib
  manifest.json
  config.yaml
  features.json
  metrics.json
  threshold_analysis.json
  data_quality.json
```

`manifest.json` should contain source checksums/versions, code commit, dependency
version, target-policy version, feature-contract version, temporal boundaries,
model family and parameters, decision threshold, creation time, gate results,
and status (`candidate`, `rejected`, `champion`, or `retired`). Generated
processed data remains reproducible and outside Git.

## Feature-contract behaviour

The primary contract excludes pricing-derived fields:

```yaml
feature_contract:
  name: pre_pricing_v1
  prediction_point: before_pricing
  exclude:
    - apr
    - originallyScheduledPaymentAmount
```

The system permits an explicit include list or exclusion list, but permanent
forbidden columns cannot be re-enabled. Training saves the final ordered list;
prediction must validate names, order, types, and required category handling
against that same artifact. Contract changes create a new version and a new
candidate rather than mutating a deployed model.

## POC model comparison

All results below use 18,433 training, 4,255 validation, and 5,672 untouched
chronological test rows under `pre_pricing_v1`:

| Model | ROC-AUC | PR-AUC | Log loss |
|---|---:|---:|---:|
| Constant training-rate predictor | 0.500 | 0.716 | 0.664 |
| Logistic regression | 0.724 | 0.837 | 0.562 |
| LightGBM | 0.737 | 0.849 | 0.615 |

LightGBM provides better ranking, but logistic regression has materially better
log loss. Therefore LightGBM is the Part 3 candidate, not an automatically
approved probability model; calibration must be evaluated and improved before
scores drive pricing or expected-loss calculations. The original post-pricing
LightGBM (ROC-AUC 0.732) is a historical ablation reference, not the primary
contract.

## Prediction and serving path

Training and inference must reuse the same contract-aware feature builder to
prevent training-serving skew:

```text
new application
  -> validate request against pre_pricing_v1
  -> retrieve/join available application-time Clarity data
  -> run the shared feature builder
  -> verify ordered names and types against features.json
  -> load/use the approved champion
  -> return risk probability plus model and contract versions
  -> log prediction metadata for monitoring and audit
```

The POC exposes this through a small FastAPI service with Pydantic request
models. The implemented prediction, model, administration, health, readiness,
metrics, and generated OpenAPI routes are catalogued in
[`SERVING_API.md`](SERVING_API.md). The service loads the champion once at
startup and never re-trains during a prediction request. FastAPI is an interface
choice, not a requirement of the model pipeline; a tested Python prediction
interface remains the minimum implementation.

Inference validation should reject missing required fields, invalid types,
out-of-policy ranges, feature-contract mismatches, and unexpected schema
versions. The pre-pricing API must not require APR or scheduled payment. Missing
Clarity data follows the same training behaviour: retain the application, set
`has_clarity_report = 0`, and preserve missing Clarity features for the fitted
pipeline/model to handle.

Serving monitoring adds request volume, latency, invalid-request rate, error
rate, model-loading failures, prediction failures, and model version to the ML
drift and delayed-performance metrics described in Part 2. Raw identifiers and
full applications must not be written to ordinary logs.

## Execution and demonstration contract

The eventual POC should run end-to-end with one command, for example:

```bash
python -m src.training.pipeline --config configs/baseline.yaml
```

An interview demo should show a successful run, generated versioned artifacts,
promotion or rejection, champion loading, a valid prediction, an invalid request,
and a simulated failed candidate that leaves the champion unchanged. Scheduling
or orchestration should be added only after this standalone command is reliable.

Additional serving tests should prove that a saved model reloads with identical
predictions, invalid requests are rejected, unknown categories do not crash the
pipeline, pricing fields are not required, responses include the model version,
and a failed smoke test restores the previous champion pointer.

## Implemented Part 3 vertical slice

- `src.training.pipeline` creates a unique immutable run, trains the challenger, records
  source and artifact checksums, writes data-quality and gate reports, registers
  the version, promotes it atomically, and performs a reload smoke prediction.
- `src.mlops` implements hard/tolerance gates, immutable local versions, a lock,
  atomic champion-pointer replacement, an audit log, and manual/automatic rollback.
  Training and serving depend on a `ModelRegistry` protocol selected by
  `MODEL_REGISTRY_URI`: `file://registry` uses the tested local implementation,
  while `s3://bucket/prefix` is an explicit production extension point for an
  S3 bundle store plus transactional DynamoDB metadata and locking.
- `src.training.features` is shared by training and inference and persists ordered fields,
  logical types, nullability, and training category vocabularies.
- `src.serving.predictor` supplies a framework-independent predictor and versioned FastAPI
  single/batch prediction, model-info, health, readiness, and metrics endpoints.
- `src.monitoring` produces numeric PSI drift and model-version-specific delayed
  outcome reports.
- Tests exercise parity, leakage protection, gates, bundle checksums, promotion,
  rollback after a smoke failure, inference, API limits, drift, and delayed metrics.

The maturity check uses a terminal-status proxy because status-event timestamps
are absent; this limitation is written into every run's `data_quality.json`.
Managed infrastructure and rolling-window policy remain deferred as stated in
the assessment scope.

## Proposed deployment transaction

```text
write complete candidate artifacts
  -> verify checksums and reload model
  -> evaluate every gate
  -> acquire registry lock
  -> atomically replace champion manifest
  -> run prediction smoke test
  -> retain previous champion or roll back pointer on failure
```

No partially written candidate may become deployable. Logs must include run ID,
actor/automation identity, time, reason, gate results, and previous/new versions.
