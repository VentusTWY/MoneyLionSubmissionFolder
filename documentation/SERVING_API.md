# Serving API reference

The Loan Risk API serves the approved registry champion over HTTP. The examples
below assume the local default base URL, `http://localhost:8000`. All request
and response bodies are JSON unless another content type is shown.

The interactive OpenAPI documentation is available at `/docs`, the alternative
ReDoc view at `/redoc`, and the machine-readable schema at `/openapi.json` while
the service is running. Those generated pages are the source of truth for the
wire schema; this page records intended usage and operational access boundaries.

## Endpoint inventory

| Method | Path | Access | Purpose |
| --- | --- | --- | --- |
| `POST` | `/v1/predict` | Service client | Score one application with the active champion. |
| `POST` | `/v1/predict/batch` | Service client | Score a bounded JSON array of applications. |
| `GET` | `/v1/model` | Service client | Report the active model, contract, and decision thresholds. |
| `GET` | `/v1/admin/models` | Administrator | List registered model versions and concise evaluation metadata. |
| `POST` | `/v1/admin/models/{version}/promote` | Administrator | Promote and load a verified model version. |
| `POST` | `/v1/admin/models/rollback` | Administrator | Restore and load the previous champion. |
| `GET` | `/health/live` | Platform/internal | Confirm that the API process is running. |
| `GET` | `/health/ready` | Platform/internal | Confirm that the champion loaded and report its version. |
| `GET` | `/metrics` | Monitoring/internal | Return Prometheus-format serving metrics. |

Admin routes require the `X-Admin-API-Key` header. Health and metrics routes
should be exposed only to the load balancer, orchestrator, and monitoring
systems in production. The public ingress should publish only the client routes
that its consumers need.

## Prediction endpoints

### `POST /v1/predict`

The request must include `applicationDate`. The active model's persisted feature
schema determines the remaining required fields. For the bundled champion, the
client-supplied non-null fields are `payFrequency`, `loanAmount`, `state`,
`leadType`, and `leadCost`. Nullable history and Clarity fields may be omitted.
`has_clarity_report` may also be omitted; the service derives it from the
presence of Clarity fields. `applicationDate` accepts an ISO date or timestamp.
It cannot be later than the current UTC date. Do not send post-decision or
repayment fields.

```bash
curl -s -X POST http://localhost:8000/v1/predict \
  -H 'Content-Type: application/json' \
  -d '{
    "applicationDate": "2026-08-05T12:00:00Z",
    "loanAmount": 500,
    "leadCost": 25,
    "leadType": "bvMandatory",
    "payFrequency": "B",
    "state": "CA",
    "has_clarity_report": false
  }'
```

Successful response (`200`):

```json
{
  "adverse_probability": 0.23,
  "risk_band": "low",
  "decision": "pass",
  "model_version": "20260807T013638Z-8a8adcfe",
  "feature_contract_version": "pre_pricing_v1",
  "request_id": "3f9236f3-407f-4e8d-a45c-98fd7eb2252f"
}
```

`risk_band` is `low`, `medium`, or `high`. `decision` is `pass`, `review`, or
`reject`, according to the active model's thresholds. The identifiers and
version values in this example are illustrative.

Invalid JSON, a missing `applicationDate`, or an invalid request shape returns
`422`. Feature-contract failures, including missing required model features or
an invalid application date, also return `422` with a `detail` message. Handled
error bodies include `request_id` for support correlation.

### `POST /v1/predict/batch`

Send a JSON array whose elements follow the single-prediction contract:

```bash
curl -s -X POST http://localhost:8000/v1/predict/batch \
  -H 'Content-Type: application/json' \
  -d '[{"applicationDate":"2026-08-05","loanAmount":300,"leadCost":15,"leadType":"bvMandatory","payFrequency":"B","state":"AK"}]'
```

A successful response (`200`) is an array of prediction results in input order.
Batch results contain the same fields as a single result. Every item contains
the shared request ID for that batch call. The default limit is 100 items and is
configured with `PREDICTION_BATCH_LIMIT`; a larger batch returns `413`.

### `GET /v1/model`

Returns `model_version`, `feature_contract_version`, `decision_threshold`,
`review_threshold`, and `reject_threshold` for the in-memory champion. This is
the preferred endpoint for clients that need to record which model is serving.

## Administrative endpoints

Set `ADMIN_API_KEY` on the API and pass the same secret in the
`X-Admin-API-Key` request header. A missing or incorrect key returns `403`. If
the server has no admin key configured, admin requests return `503`.

### `GET /v1/admin/models`

Returns a `models` array. Each item includes its version, creation time, feature
contract, status, available `roc_auc`, `pr_auc`, and `log_loss` metrics, and the
`is_active` and `is_previous` flags.

### `POST /v1/admin/models/{version}/promote`

Promotes a registered version only after bundle verification and a serving
reload smoke test. Replace `{version}` with the exact registry version and send
the accountable actor and reason:

```bash
curl -s -X POST http://localhost:8000/v1/admin/models/20260807T013638Z-8a8adcfe/promote \
  -H 'Content-Type: application/json' \
  -H "X-Admin-API-Key: $ADMIN_API_KEY" \
  -d '{"actor":"Model Risk","reason":"Approved after challenger review"}'
```

### `POST /v1/admin/models/rollback`

Restores the previous champion, verifies it, and reloads it in the running API:

```bash
curl -s -X POST http://localhost:8000/v1/admin/models/rollback \
  -H 'Content-Type: application/json' \
  -H "X-Admin-API-Key: $ADMIN_API_KEY" \
  -d '{"actor":"On-call MLE","reason":"Rollback after serving regression"}'
```

Both mutation routes return the new `champion` pointer on success. The actor
must be 2–120 characters and the reason 5–500 characters. Validation errors
return `422`; missing versions, conflicts, or failed verification/reload return
`409`. Promotion and rollback actions are appended to `registry/audit.jsonl`.

## Operational endpoints

Successful and handled-error responses include an `X-Request-ID` header.
Prediction calls also emit a metadata-only JSON log containing the UTC
timestamp, request ID, route, HTTP status, latency, model version,
feature-contract version, result count or decision summary, and error category.
Payloads, identifiers, and feature values are not logged.

- `GET /health/live` returns `{"status":"live"}` when the process can answer.
- `GET /health/ready` returns `{"status":"ready","model_version":"..."}`.
  Container and load-balancer readiness checks should use this route.
- `GET /metrics` returns Prometheus text containing prediction request, failure,
  latency-sum, and score-band counters labelled by model version.

The model is loaded once at service startup and reloaded after a successful
admin promotion or rollback. Changing the registry champion outside these admin
routes requires restarting the API process before it serves the new model.

## Runtime configuration

| Variable | Default | Meaning |
| --- | --- | --- |
| `MODEL_REGISTRY_URI` | `file://registry` | Registry from which the champion is loaded. |
| `PREDICTION_BATCH_LIMIT` | `100` | Maximum applications accepted by one batch request. |
| `ADMIN_API_KEY` | unset | Server-side secret enabling administrative routes. |
| `UI_ORIGINS` | `http://localhost:3000` | Comma-separated browser origins allowed by CORS. |
