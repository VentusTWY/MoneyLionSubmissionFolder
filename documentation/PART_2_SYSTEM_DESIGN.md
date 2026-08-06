# Part 2 - Automated Loan-Risk ML System Design

> **Scope.** A production-oriented ML lifecycle for continuous LightGBM updates. Logical components are platform-independent; a concrete AWS deployment uses S3, container jobs/services on EKS or ECS, EventBridge scheduling, and CloudWatch/Prometheus. Part 3 preserves the same interfaces locally with Parquet snapshots, a Python orchestrator, filesystem registry, and containerised API, so it runs without cloud credentials.

## Context

A production-oriented ML lifecycle for continuous LightGBM updates can be grounded by a concise operational context: the model is scored before pricing, uses application-time features only, and should support immutable challenger training, gated promotion, and safe online inference.

## Four pipelines, two connected lifecycles

![Hand-drawn architecture showing the model update, online decision, monitoring feedback, rollback, and CI/CD lifecycles](images/part2_ml_architecture.png)

The system lifecycle follows a clear loop: data ingest → training / candidate evaluation → gated promotion → production serving → monitoring & alerting → retraining / batch jobs. That feedback loop is the core of the ML Ops design.

```text
+-------------------+      +-----------------+      +-----------------------------+
|  Raw data / S3    | ---> |  Training / CI  | ---> |  Model Registry / ECR / S3  |
|  snapshots        |      |  pipeline       |      |  (versioned artifacts)      |
+-------------------+      +-----------------+      +-------------+---------------+
                                                              |           ^
                                                              |           |
                                                              v           |
                                                      +-----------------------+  |
                                                      |  EKS / Kubernetes     |  |
                                                      |  FastAPI serving API  |  |
                                                      +----------+------------+  |
                                                                 |              |
                                                                 v              |
                                                       +----------------+      |
                                                       | Internal ALB   |      |
                                                       +-------+--------+      |
                                                                 |               |
                                                                 v               |
                                                      +----------------------+  |
                                                      |  LoanRiskCalculator   |--+
                                                      |  UI / Browser         |
                                                      +----------------------+
                                                                 |
                                                                 v
                                                       +----------------------+
                                                       | Monitoring / Alerting|
                                                       |  (Prometheus/Grafana)|
                                                       +----------------------+

+-------------------+      +-----------------+      +-----------------------------+
|  Retrain / Batch  | ---> |  Job Orchestration| ---> |  Registry / Audit logs      |
|  Jobs / Cron      |      |  (EKS Jobs/Batch) |      |  (registry/audit.jsonl)     |
+-------------------+      +-----------------+      +-----------------------------+
```

The model uses **offline batch learning**: scheduled or evidence-triggered runs train immutable challengers only from mature outcomes, and continuous training never bypasses deployment gates. New applications use **synchronous online inference** because a score is required before pricing. Stored predictions are later joined to mature outcomes for offline evaluation and the next update. Training and serving import the same deterministic feature transformer; its versioned schema records names, order, types, category handling, and prediction point, and a mismatch fails closed. Code or configuration changes follow a separate CI/CD path: unit, integration, contract, leakage, artifact, and end-to-end tests build versioned pipeline/service images before approval.

## Steps and controls

1. **Ingest and validate.** Read immutable, identified snapshots and record checksums, schemas, row counts, date ranges, and code/config versions. Enforce required types, unique non-null loan IDs, unique Clarity IDs, many-to-one joins, valid binary fields, and leakage exclusions. Quarantine contradictory terminal outcomes; fail on missing columns, duplicate keys, or incompatible schemas.

2. **Build training data.** Generate application-time features under `pre_pricing_v1`. New applications may enter population-drift reports immediately, but become supervised examples only after an approved performance window and resolved outcome. Use rolling chronological train, validation, and untouched test windows; fit learned transformations only on training data.

3. **Evaluate and gate.** Compare the LightGBM challenger with constant/logistic benchmarks and the deployed champion on identical rows. Hard gates cover schema, leakage, maturity, sample size, and inference compatibility. Configurable gates cover ROC-AUC, PR-AUC, log loss/calibration, recent-period stability, approved subgroup behaviour, and business value when costs exist. Use tolerances or confidence intervals for sampling noise. A failed candidate remains auditable but cannot change production.

4. **Register and promote.** Store immutable, versioned dataset and model records containing checksums, code/config/dependency versions, source cutoffs, target and feature policies, ordered schema, threshold, metrics, and gate results. Verify checksums, reload the model, and run contract and smoke predictions before atomically changing the champion pointer. Record actor, time, reason, and previous/new versions; preserve the previous champion for rollback.

5. **Deploy and serve safely.** Because a new application needs its score before pricing, use synchronous online inference rather than cached batch predictions. Run replicated API containers in Kubernetes on EKS behind an internal AWS ALB ingress. The API loads the approved champion from S3 and registry metadata at startup; readiness and liveness probes fail if the manifest, checksum, dependency, or contract compatibility checks do not pass. The service should be deployed into separate `dev`, `staging`, and `prod` namespaces with Kubernetes RBAC, network policies, and resource quotas.

6. **Infrastructure and deployment architecture.** A concrete system-design section should describe the full ML Ops stack rather than only the serving layer.

- **Docker/ECR:** Build container images for training, evaluation, and serving. Use a CI pipeline to create images from `Dockerfile` artifacts, tag by commit hash and version, scan for vulnerabilities, and push them to Amazon ECR. Store image metadata alongside model metadata to enable traceable rollbacks.
- **CI/CD:** Use GitHub Actions, AWS CodeBuild/CodePipeline, or similar to run tests and package artifacts. Pipelines should execute unit tests, integration tests, data contract checks, schema validation, and pipeline smoke tests before promoting images to staging or production. A deployment pipeline should apply Kubernetes manifests or Helm charts to EKS and optionally run a canary rollout with traffic validation.
- **Training and batch jobs:** Use EKS `Job` or `CronJob` resources (or AWS Batch) for retraining and evaluation. Schedule retrains from EventBridge / Argo Workflows, and run them on compute node groups with spot or on-demand scaling as appropriate. Training jobs read from S3 snapshots and write versioned artifacts back to S3 and the registry.
- **Artifact storage:** Use S3 for raw input snapshots, processed feature data, training artifacts, model binaries, and registry manifests. Enable bucket versioning and lifecycle policies. Store `registry/versions/<run-id>/` metadata and model payloads in S3 or an object store with strong consistency and immutability controls.
- **Registry & metadata:** Persist model registry state in a versioned file store with an atomic champion pointer, as in the current architecture, and optionally back it with DynamoDB or RDS for queryable metadata and auditability. Keep an append-only audit log (`registry/audit.jsonl`) for every candidate and promotion decision.
- **Serving contract:** The runtime API should enforce schema and feature contract compatibility on startup, accept only the approved champion, and expose health/ready endpoints. Use `GET` for read-only endpoints like `/v1/model`, `/health/ready`, `/health/live`, and `/metrics` because they return metadata or service status without a request body. Use `POST` for `/v1/predict` and `/v1/predict/batch` because prediction input is structured, potentially large, and should not be encoded in a URL. Responses should include model and feature contract versions, score, risk band, and decision path.
- **Monitoring & observability:** Use Prometheus/Grafana on EKS for application and infrastructure metrics, and CloudWatch for logs and alerts. Monitor request volume, latency (p50/p95/p99), error rate, resource usage, feature missingness, schema drift, score distribution, and model stability. Alert on retraining failures, promotion anomalies, and production regressions.
- **Security & compliance:** Use AWS IAM roles for service accounts, restrict ECR and S3 access with least privilege policies, and manage secrets through AWS Secrets Manager or SSM Parameter Store. Use TLS certificates from AWS ACM for ingress, enforce origin restrictions for the UI, and scan images in ECR.
- **Rollback and operational readiness:** Keep the previous champion available for rollback. A successful promotion updates `registry/champion.json` atomically while preserving the prior version. The operational runbook should include steps to restart API pods, rollback a deployment, and validate a new champion before resuming traffic.

7. **Monitor and improve.** Securely store prediction ID, timestamp, score/decision, model/contract versions, data-quality indicators, and latency - not raw identifiers or unrestricted payloads. Immediately monitor traffic, failures, p50/p95/p99 latency, resources, missingness, Clarity coverage, and feature/score drift. Join prediction records to access-controlled mature outcomes for discrimination, calibration, score-band outcomes, business value, time slices, and approved subgroups. Alerts prompt investigation; drift alone never promotes a model and every retraining trigger still passes all gates.

## Principal limitations and decisions required

Outcomes exist only for historically funded loans, so performance cannot be established for rejected applicants and may shift when approval policy changes. The extract lacks timestamped status history, making a minimum-age maturity rule only a POC approximation. Business, risk, data, and legal owners must approve ambiguous outcomes, maturity window, threshold/costs, fairness policy, cadence, service SLOs, fallback, retention, and gate limits. Production identity, encryption, auditability, high availability, regional recovery, and infrastructure integration require environment-specific validation.
