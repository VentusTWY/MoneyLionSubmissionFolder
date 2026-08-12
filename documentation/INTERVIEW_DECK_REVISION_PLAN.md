# Loan Risk Predictor — Interview Deck Revision Plan

This document digests the mentor feedback, reviews the current nine-slide image export, and converts the deck into a Markdown content plan. It is a planning artifact only: no slide or architecture-diagram files have been changed.

## Communication job

By the end, interviewers for the Senior Machine Learning Engineer role should understand that this is not only a LightGBM experiment: it is a safe, reproducible ML workload from application-time data to a versioned champion model, scalable inference, monitoring, alerting, and rollback. The candidate owns the ML-system design and delivery while partnering with the MLOps function on the shared AWS, Docker, Kubernetes, CI/CD, and observability platform.

## Executive digest of the mentor feedback

The requested direction is sound:

1. Make the system architecture AWS-native and visual. Use official AWS service icons and short labels instead of paragraphs inside boxes.
2. Add concrete technology choices to every operational path: S3, SageMaker Processing/Training, SageMaker Model Registry, SageMaker real-time endpoint, CloudWatch, SNS, Slack, ECR, EKS, IAM, and Terraform.
3. Rebalance the story toward production ML engineering. The interviewers should see modeling judgment plus orchestration, contracts, repeatability, promotion, observability, scaling, and recovery. Platform implementation should be described as collaboration with MLOps Engineers, not as a separate platform being built single-handedly by this role.
4. Add the missing modeling evidence: label distribution by chronological split, LightGBM-versus-baseline results, metric rationale, calibration caveat, and threshold trade-off.
5. Make the repository look intentionally organized around data, model, serving, and infrastructure concerns.
6. Treat distributed training and Kubernetes as conditional scaling tools, not automatic signs of production maturity.

The best opening move is to fix the content hierarchy before rebuilding visuals. First agree the claim and words for each slide; then redraw the AWS diagram with icons.

## Role alignment: Senior ML Engineer versus the MLOps function

The [current Gen Digital posting](https://jobs.ashbyhq.com/gen-digital/6df99df3-bbd5-4a49-b413-66ff7790a428) confirms a separate MLOps engineering function. It says the Senior ML Engineer will:

- own and lead the end-to-end architecture, orchestration, and delivery of ML systems and pipelines;
- lead technical discussions with MLOps Engineers and Data Scientists;
- design and monitor experiments and metrics independently;
- monitor, optimise, and maintain production ML solutions;
- enforce test-driven development and engineering practices.

This changes the emphasis, but it does **not** remove production architecture from the presentation. The strongest positioning is:

> I own the ML workload, its contracts, evidence, and production behaviour. I collaborate with the MLOps lead/team to deploy it on their paved-road infrastructure and to agree operational controls.

Use this responsibility split in the presentation and interview answers:

| Area | Senior ML Engineer — lead/own | MLOps lead/team — partner/platform owner | Data Scientists — partner/domain owner |
|---|---|---|---|
| Problem and target | Frame business problem; define prediction point and executable target contract | Advise how contracts are represented and deployed | Challenge target validity and business meaning |
| Features and data | Define leakage-safe feature logic, validation, and training/serving parity | Provide data/orchestration primitives and production access patterns | Propose and evaluate feature hypotheses |
| Experiments | Design reproducible experiments, splits, metrics, baselines, and conclusions | Provide experiment-tracking platform and compute integration | Explore models and interpret evidence |
| Training pipeline | Own pipeline logic, artifacts, tests, gates, and failure behaviour | Provide/operate workflow, compute, registry, IAM, and CI/CD platform | Supply or review candidate methodology |
| Serving contract | Own input/output schema, preprocessing, model-loading behaviour, thresholds, and model-version traceability | Provide/operate endpoint or Kubernetes deployment primitives, scaling, networking, and secrets | Validate decision semantics and model behaviour |
| Monitoring | Define feature/score/performance metrics, label joins, thresholds, and investigation logic | Provide telemetry, alert routing, dashboards, on-call integration, and platform SLOs | Investigate statistical/model degradation |
| Promotion and rollback | Define evidence gates, compatibility checks, smoke tests, and model rollback requirements | Implement/operate deployment controls, access control, registry integrations, and release automation | Review model evidence where governance requires it |

Avoid these two extremes:

- **Too platform-heavy:** “I will independently build and own EKS, networking, IAM, Terraform modules, CI/CD, and the observability platform.” That ignores the separate MLOps function.
- **Too modeling-only:** “I hand a model file to MLOps and my job is finished.” That conflicts with the posting's end-to-end ownership, production maintenance, and system-design expectations.

The architecture diagram should therefore show **system responsibility boundaries**, not pretend that every AWS box is personally administered by the Senior ML Engineer. A small legend can distinguish:

- **ML workload ownership:** target, feature pipeline, training logic, evaluation, gates, serving contract, model-quality monitoring.
- **Shared MLOps platform:** orchestration runtime, registry service, deployment infrastructure, cluster/endpoint scaling, IAM, secrets, telemetry, and alert delivery.
- **Data Science collaboration:** feature/model hypotheses, experimental review, and domain validation.

## Important corrections and nuances

### 1. False negatives versus false positives

The positive class in this project is an **adverse repayment outcome**.

- False negative: an adverse loan is predicted safe and may pass.
- False positive: a good loan is predicted risky and may be stopped or sent to review.

Therefore, “better to stop a borderline loan than pass a high-risk one” means the system should be willing to tolerate **more false positives to reduce false negatives**. It does not mean that false negatives are preferred.

At the current illustrative threshold of `0.50`, the test confusion matrix contains:

| Actual / predicted | Predicted good | Predicted adverse |
|---|---:|---:|
| Actual good | 918 | 691 false positives |
| Actual adverse | 851 false negatives | 3,212 |

This gives adverse-class recall of about `79.1%` and precision of about `82.3%`. A lower threshold such as `0.45` increases adverse recall to about `87.5%`, but also flags more good loans. Do not call `0.45` optimal: the final threshold needs the business costs of a missed bad loan, unnecessary review/rejection, capital, recovery, and customer impact.

Suggested interview wording:

> Because adverse outcome is the positive class, I would optimize the operating threshold to reduce false negatives, while accepting a controlled increase in false positives. I show the trade-off rather than claiming that 0.50 is a business-optimal threshold.

### 2. The data does not show a conventional minority adverse class

The resolved modeling cohort contains 28,360 rows:

| Split | Rows | Adverse rate |
|---|---:|---:|
| Train | 18,433 | 53.6% |
| Validation | 4,255 | 72.0% |
| Test | 5,672 | 71.6% |
| Overall | 28,360 | 60.0% |

The important finding is not “few high-risk examples.” It is that adverse prevalence rises materially in later periods. That strengthens the case for:

- chronological rather than random evaluation;
- monitoring target/score/feature distributions by time window;
- comparing PR-AUC against the period-specific positive-class prevalence;
- avoiding blind SMOTE or class weighting;
- choosing the threshold against business costs and recent-period performance.

If the interviewers ask about imbalance, say that imbalance was checked, but the adverse class is not the minority in this resolved funded-loan cohort. The more material risk is temporal distribution shift and selection bias from training only on historically funded loans.

### 3. LightGBM justification should be precise

Avoid saying that LightGBM is inherently “for time-series data.” The chronological split is an evaluation design; LightGBM itself does not understand time unless time-derived features and validation order are supplied.

Use these reasons instead:

- It captures nonlinear interactions and threshold effects common in tabular credit-risk features.
- It handles mixed numeric/categorical application data and missing values efficiently.
- It trains quickly and serves cheaply for a structured dataset of this size.
- It provides feature-importance and SHAP-compatible diagnostics, subject to appropriate governance.
- It improves ranking over the constant and logistic baselines on the untouched chronological test set.

Keep the caveat: logistic regression has better log loss, so the raw LightGBM probabilities require calibration assessment before pricing or expected-loss use.

### 4. S3, Model Registry, and DynamoDB have different jobs

Do not present DynamoDB as the model-artifact store.

- S3: immutable model bundles, evaluation reports, and data snapshots.
- SageMaker Model Registry: model versions, lineage, approval state, and promotion workflow.
- DynamoDB: optional transactional champion pointer, idempotency keys, promotion lock, or audit metadata when those controls are not fully represented by the managed registry workflow.

The current repository already exposes this boundary through `MODEL_REGISTRY_URI`: local filesystem for the POC; S3 plus transactional metadata as the production extension.

### 5. “SNS to Slack” needs an explicit bridge

Use this path on the diagram:

```text
CloudWatch alarm / pipeline failure / drift event
  -> SNS topic
  -> Amazon Q Developer in chat applications
  -> Slack #ml-alerts
```

A Lambda is useful only when the alert payload needs custom enrichment, deduplication, routing, or a direct webhook integration. Avoid the vague label “Airflow Lambda.” If Airflow is part of the company stack, show Amazon MWAA/Airflow as the orchestrator and Lambda as a separate event handler.

AWS documents that Amazon Q Developer in chat applications consumes SNS notifications and forwards them to Slack channels: [AWS documentation](https://docs.aws.amazon.com/chatbot/latest/adminguide/what-is.html).

## Current slide-by-slide review

### Current slide 1 — Loan Risk Predictor ML System Design

Current job: title and identity.

Keep:

- Minimal title slide.
- Existing clean visual language.

Improve:

- Add a one-line positioning statement: **“A governed path from application data to a scalable champion model.”**
- Correct the company/assessment naming if “Gen” is only a placeholder.
- Do not add AWS icons here; save them for the architecture.

### Current slide 2 — LightGBM Machine Learning Model Definition

Current content:

- Target: probability of adverse repayment.
- Good: Paid Off Loan.
- Bad: Internal Collection, External Collection, Settled Bankruptcy, Charged Off.
- Ambiguous outcomes excluded.

Keep:

- The three-part target / good / bad composition.
- The explicit exclusion of ambiguous statuses.

Improve:

- Retitle as a claim: **“The model predicts adverse repayment before pricing.”**
- State the population in one line: funded loans with mature, unambiguous outcomes.
- Add the selection-bias caveat in the footer: the model estimates risk conditional on the historical funding policy.
- Remove “LightGBM” from the slide title; target definition is model-independent.
Therefore, “better to stop a borderline loan than pass a high-risk one” means the system should be willing to tolerate **more false positives to reduce false negatives**. It does not mean that false negatives are preferred.


### Current slide 3 — Model Design, Leakage Controls & Evaluation

Current content:

- Pre-pricing prediction point.
- APR and scheduled-payment fields excluded.
- Label built from `loanStatus`; payment records used for consistency.
- Application-date features and important Clarity / prior-payoff features.
- ROC-AUC, PR-AUC, and log loss definitions.

Problem: this slide is doing four jobs at once and the bottom-right metric list lacks the model results and metric-selection logic.

Improve by splitting it into two slides:

1. **“The feature contract prevents decision and repayment leakage.”**
   - prediction point;
   - excluded post-decision fields;
   - shared training/serving feature contract;
   - chronological split.
2. **“LightGBM improves ranking; calibration remains the main caveat.”**
   - label distribution by split;
   - compact model comparison;
   - threshold trade-off;
   - why each metric matters.

Suggested metric rationale:

- ROC-AUC: threshold-independent ranking across good and adverse outcomes.
- PR-AUC: adverse-class precision/recall; compare it with the 71.6% test prevalence.
- Log loss: probability quality and penalty for confident mistakes.
- Recall at an operating threshold: business protection against missed adverse loans.
- Calibration: required before interpreting scores as true probabilities.


### Current slide 4 — Automated ML System Design

Current content:

- CI/CD control plane.
- Offline training pipeline.
- Online serving pipeline on EKS.
- Monitoring and retraining loop.
- SageMaker Model Registry and S3.

Keep:

- The separation of software deployment, model training, serving, and monitoring.
- The closed-loop idea.

Improve:

- Replace generic boxes with official AWS icons and reduce every node to 2–4 words.
- Choose one primary inference story. The mentor direction says SageMaker should serve the champion; use a SageMaker real-time endpoint as the primary model-serving component. EKS can host the product/API integration layer if the company requires Kubernetes.
- Add orchestration: EventBridge schedule or MWAA/Airflow starts the batch feature/training workflow.
- Add feature storage: S3 offline features and, only if low-latency feature reuse is required, SageMaker Feature Store online/offline stores.
- Add alert delivery: CloudWatch/EventBridge -> SNS -> Amazon Q Developer in chat applications -> Slack.
- Add an explicit idempotency/version label near the training workflow.
- Keep security present but visually quiet: IAM/KMS/VPC boundary as a footer or side rail.
- Avoid showing both “model served directly on EKS” and “model served by SageMaker endpoint” unless the diagram labels one as an alternative. Two champion-serving paths create ambiguity.
- Add a subtle ownership legend: the Senior ML Engineer owns the ML workload and contracts; the MLOps team supplies and operates shared platform capabilities. Do not turn the architecture slide into an organisational chart.

Recommended slide title: **“AWS separates retraining, governed promotion, and low-latency serving.”**

### Current slide 5 — Promotion Controls

Current content:

- Gate the candidate.
- Change the champion atomically.
- Smoke test and restore on failure.
- YAML/JSON implementation snippets.

Keep:

- Evidence -> promotion -> recovery sequence.
- Atomicity, audit actor/reason, and rollback.

Improve:

- Replace three code screenshots with one small “POC proof” strip or move them to an appendix. The interview-facing slide should emphasize control outcomes.
- Map the POC to AWS underneath each stage:
  - evidence: SageMaker Processing/Evaluation + pipeline condition;
  - promotion: SageMaker Model Registry approval;
  - recovery: endpoint deployment guardrail + previous approved version.
- Add data/contract compatibility and calibration/threshold approval to the gates.
- State that a monitoring event can trigger retraining but never bypass promotion gates.

Recommended title: **“Only evidence-backed candidates can replace the champion.”**

### Current slide 6 — Monitoring & Observability

Current content:

- Live service signals in seconds/minutes.
- PSI before labels mature.
- Delayed performance after mature outcomes.

Keep:

- The three time horizons; this is one of the strongest slides.

Improve:

- Add concrete AWS destinations without overcrowding:
  - endpoint/API logs and metrics -> CloudWatch;
  - drift/performance job -> SageMaker Processing or scheduled container;
  - alarm/event -> SNS -> Slack;
  - investigation may trigger a Step Functions/MWAA pipeline run.
- Add model version and feature-contract version to every monitoring event.
- Add an alert policy statement: alerts create an investigation/retraining ticket; they do not auto-promote.
- Consider “feature drift, score drift, delayed outcome quality” rather than PSI alone. PSI is a signal, not proof of degradation.

Recommended title: **“Monitoring separates service failure, drift, and delayed model quality.”**

### Current slide 7 — Safety boundaries proven by this proof-of-concept

Current content:

- 28 tests.
- One versioned champion.
- Managed registry/cloud/SLOs/approved thresholds as next steps.

Keep:

- Clear separation between implemented and future production work.

Improve:

- Replace the large generic cards with a compact “Proven locally / Production extension” comparison.
- Mention the actual capabilities, not only counts:
  - shared feature contract;
  - immutable artifacts/checksums;
  - failed promotion leaves champion unchanged;
  - reload smoke test and rollback;
  - model-version-labelled metrics.
- Update the test count only after rerunning the current suite.
- Add Terraform as the next implementation step, but phrase it as provisioning infrastructure rather than “infrastructure functions.”

Recommended title: **“The POC proves the safety boundaries; AWS supplies the managed runtime.”**

### Current slide 8 — User Interface Demo

Current content:

- Scoring workspace.
- Restricted model-operations page.

Keep:

- Both screenshots; they make the system concrete.

Improve:

- Retitle as a claim: **“Every decision is traceable; every model change is controlled.”**
- Add two or three numbered callouts on the screenshots:
  1. probability, risk band, request ID, model version;
  2. active champion and contract;
  3. operator identity, reason, promote, and rollback.
- Use the live demo to show the detail; do not add explanatory paragraphs to the slide.

### Current slide 9 — Thank You

Current job: close.

Problem: it ends on a generic phrase rather than resolving the technical story.

Replace with a conclusion slide:

**Title:** “Automation does not mean automatic trust.”

**Three closing claims:**

- Reproducible evidence before promotion.
- One approved, versioned champion in serving.
- Monitoring can trigger investigation and retraining; only gates and approval can change production.

Then add a small **Questions** line. This gives the audience a concise thesis to challenge in discussion.

## Proposed revised deck in Markdown

This is the recommended content sequence. It expands the current nine slides to eleven by adding explicit data/model evidence and a dedicated scaling story. If time is tight, combine slides 7 and 8.

### Slide 1 — Loan Risk Predictor ML System Design

**Subtitle:** A governed path from application data to a scalable champion model

**Footer:** Ventus Tan Wei Yang | ML Engineering assessment

**Speaker focus:** The submission covers target design, evidence, automated retraining, controlled promotion, online serving, observability, and rollback.

### Slide 2 — The model predicts adverse repayment before pricing

**Target:** Probability that a funded loan reaches an adverse repayment outcome.

**Good outcome:** Paid Off Loan.

**Adverse outcome:** Internal Collection, External Collection, Settled Bankruptcy, or Charged Off.

**Scope line:** Train only on funded loans with mature, unambiguous outcomes; exclude ambiguous statuses.

**Caveat:** Performance is conditional on the historical funding policy.

### Slide 3 — The feature contract prevents decision and repayment leakage

**Prediction point:** Before pricing and before the lending decision.

**Excluded:** APR, scheduled payment, approval/origination fields, final status, payment records, and raw identifiers.

**Engineered:** Month, day of week, and hour from application time; application-time Clarity and prior-loan signals.

**Control:** The same versioned feature builder and ordered schema are used in training and inference.

**Evaluation:** Chronological train/validation/test split.

### Slide 4 — Later cohorts are riskier, so evaluation must be time-aware

**Visual:** Three bars or a chronological band.

| Train | Validation | Test |
|---:|---:|---:|
| 53.6% adverse | 72.0% adverse | 71.6% adverse |

**Takeaway:** The adverse class is not a small minority. The material issue is temporal prevalence shift, which makes random splitting and generic oversampling inappropriate defaults.

**Speaker focus:** Monitor prevalence and feature/score distributions by time; compare PR-AUC with the current prevalence baseline.

### Slide 5 — LightGBM improves ranking; calibration remains the main caveat

| Model | ROC-AUC | PR-AUC | Log loss |
|---|---:|---:|---:|
| Constant predictor | 0.500 | 0.716 | 0.664 |
| Logistic regression | 0.724 | 0.837 | **0.562** |
| LightGBM | **0.737** | **0.849** | 0.615 |

**Why LightGBM:** nonlinear interactions, mixed tabular features, missing-value handling, efficient training and inference, and improved ranking.

**Decision caveat:** Logistic regression has better log loss. Assess/calibrate LightGBM probabilities before using them for pricing or expected loss.

**Threshold note:** To reduce missed adverse loans, lower the threshold only after agreeing the cost of false negatives and false positives.

### Slide 6 — AWS separates retraining, governed promotion, and low-latency serving

**Visual only; use official AWS icons.**

```text
EventBridge / MWAA
  -> S3 versioned snapshot
  -> SageMaker Processing: validation + feature build
  -> SageMaker Training: LightGBM challenger
  -> evaluation gates
  -> SageMaker Model Registry + S3 artifacts
  -> approved champion
  -> SageMaker real-time endpoint
  -> product/API clients

Endpoint + pipeline events
  -> CloudWatch / scheduled quality jobs
  -> SNS
  -> Amazon Q Developer in chat applications
  -> Slack
```

**CI/CD rail:** GitHub Actions -> tests/scans -> ECR -> Terraform deployment.

**Security rail:** IAM, KMS, VPC, secrets, least privilege.

### Slide 7 — Idempotent pipelines make retries safe and models reproducible

**Run identity:** hash/data version + Git SHA + configuration/feature-contract version.

**Idempotency:** retries with the same run key reuse or fail safely; they do not create conflicting versions or promote twice.

**Versioning:** immutable S3 data/model paths, unique Model Registry version, saved metrics and dependency manifest.

**Promotion:** condition gates -> approval -> atomic champion change -> reload smoke test -> rollback on failure.

**Audit:** actor, reason, previous version, new version, timestamp, and evaluation fingerprint.

### Slide 8 — Scale each bottleneck independently

**Training:** For 28k rows, a single SageMaker CPU training job is sufficient. Scale vertically first. Use distributed LightGBM/data partitioning only when measured runtime or memory exceeds the training SLO; reserve model-parallel patterns for models that cannot fit on one worker.

**Serving:** Use a SageMaker real-time endpoint for synchronous low-latency scoring, with multiple instances/AZs and Application Auto Scaling. Load test concurrent requests and scale on invocations per instance, CPU, latency, and error rate.

**Kubernetes:** Use EKS for the surrounding API/orchestration layer when it matches the company's platform, or use it for model serving as an explicit alternative—not a duplicate primary serving path.

**Data/monitoring:** Partition S3 data by event date and run batch drift/outcome jobs independently of the online endpoint.

AWS describes real-time endpoints as managed low-latency endpoints with autoscaling: [AWS documentation](https://docs.aws.amazon.com/sagemaker/latest/dg/realtime-endpoints.html). SageMaker also documents data-parallel versus model-parallel training strategies: [AWS documentation](https://docs.aws.amazon.com/sagemaker/latest/dg/distributed-training-strategies.html).

### Slide 9 — Monitoring separates service failure, drift, and delayed model quality

**Seconds to minutes:** request count, latency, validation failures, 5xx errors, model-load failures.

**Before labels mature:** feature drift, missingness, category changes, score/risk-band shift, PSI.

**After outcomes mature:** join prediction audit to outcomes by `loanId`; calculate ROC-AUC, PR-AUC, log loss, recall, and calibration by model version.

**Response:** CloudWatch alarm or quality event -> SNS -> Slack -> investigation, remediation, or a controlled retraining run. No automatic promotion.

### Slide 10 — The POC proves the safety boundaries; AWS supplies the runtime

**Proven locally:** deterministic pipeline, shared feature contract, immutable bundles/checksums, evidence gates, audited promotion, smoke-test rollback, versioned API responses, drift and delayed-quality reports, automated tests.

**Production extension:** co-delivery with the MLOps team on Terraform-managed AWS resources, managed registry and endpoint, SLOs/load tests, IAM/KMS/VPC controls, alert routing, and disaster recovery; collaboration with Data Science and risk owners on approved thresholds, calibration, and fairness policy.

### Slide 11 — Every decision is traceable; every model change is controlled

**Visual:** scoring workspace and restricted model-operations screenshots with three numbered callouts.

**Demo sequence:**

1. Confirm readiness, active champion, and feature-contract version.
2. Submit a valid prediction; explain probability, risk band, request ID, and model version.
3. Submit invalid input; show contract-boundary rejection.
4. Promote a prepared candidate; show audit details and in-process reload.
5. Roll back; confirm the prior champion and audit record.

**Closing line:** Automation does not mean automatic trust: every model change remains evidence-based, versioned, observable, and recoverable.

## Recommended architecture decisions

### Primary recommendation

Propose SageMaker for model training, registry, and real-time inference because that is the clearest match to the mentor's company-stack guidance. Use Docker images in ECR for reproducibility. Use EKS only for the product/API layer or other platform services if Kubernetes is an organizational requirement. Present this as a workload design to validate with the MLOps lead/team against the company's existing paved road—not as a unilateral platform replacement.

This avoids an unclear design in which both EKS and SageMaker appear to host the same champion.

### Feature store decision

Do not add a feature store only for visual completeness. Add it if multiple models reuse governed features or online/offline parity requires low-latency retrieval.

- Simple first version: versioned offline features in S3; request-time application fields supplied to the endpoint.
- Mature version: SageMaker Feature Store offline store for training and online store for low-latency reusable features, with event-time correctness.

For historical borrower features, prevent leakage by computing only events that occurred before each application's timestamp.

### Distributed training decision

The current dataset does not justify distributed training. Saying so demonstrates engineering judgment.

Use a scaling ladder:

1. Measure data loading, feature build, and training separately.
2. Optimize data format/partitioning and LightGBM parameters.
3. Move to a larger single SageMaker CPU instance if memory/runtime requires it.
4. Use distributed LightGBM with a supported distributed framework only after a training SLO or memory limit is breached.
5. Use data parallelism for very large datasets/models that replicate on each worker; use model parallelism only when the model itself does not fit on one worker.

Do not imply that SageMaker's deep-learning distributed libraries are necessary for this small tabular LightGBM model.

### Serving and concurrency decision

For a synchronous loan decision, start with a SageMaker real-time endpoint:

- minimum two instances for production availability if the SLO requires it;
- autoscaling based on measured invocations per instance, CPU, latency, and queue pressure;
- health checks and endpoint deployment guardrails;
- load tests that report p50/p95/p99 latency, throughput, saturation point, and error rate;
- champion model loaded once per container, never per request;
- bounded batch endpoint separate from synchronous single-loan scoring.

If the company's standard is Kubernetes-hosted models, the alternative is FastAPI pods on EKS with Horizontal Pod Autoscaler, readiness probes, PodDisruptionBudget, multiple availability zones, and cluster/node autoscaling. Present this as an alternative deployment target behind the same versioned serving contract.

### Idempotency and versioning decision

Suggested production identifiers:

```text
data_snapshot_id = immutable S3 manifest/version
code_version     = Git SHA + container digest
config_version   = hash of target, feature, training, and evaluation config
run_key          = hash(data_snapshot_id, code_version, config_version)
model_version    = SageMaker Model Package version
```

A DynamoDB conditional write can claim the `run_key` before orchestration begins. Repeated events then return the existing run rather than launching a conflicting one. Candidate artifacts remain immutable; “champion” is a pointer/approval state, not a mutable model file.

AWS Model Registry supports model-version approval states such as pending, approved, and rejected: [AWS documentation](https://docs.aws.amazon.com/sagemaker/latest/dg/model-registry-approve.html).

## Repository structure recommendation

The current repository is already a credible Python ML system: it has `configs/`, `src/`, `tests/`, `notebooks/`, Docker, pipeline modules, monitoring, and a registry interface. The first structural refactor is now implemented: offline model training and online serving live in separate packages. Continue only where a new boundary makes ownership clearer; avoid a large cosmetic rewrite immediately before the interview.

Recommended target structure:

```text
data/
  README.md                 # raw/processed data contract; data itself untracked
configs/
  baseline.yaml
  promotion.yaml
  monitoring.yaml
infra/
  terraform/
    modules/
      data/
      training/
      registry/
      serving/
      monitoring/
    environments/
      dev/
      prod/
notebooks/
  01_eda.ipynb             # research and diagnostics only
src/
  training/
    data.py
    labels.py
    features.py
    train.py
    evaluate.py
    benchmark.py
    pipeline.py
  serving/
    predictor.py
    api.py
  mlops.py
  monitoring.py
tests/
  unit/
  integration/
scripts/
Dockerfile
docker-compose.yml
Makefile
```

Notes:

- Terraform provisions AWS resources, policies, alarms, and integrations; it is not a folder “for infrastructure functions.”
- Keep shared feature transformation inside `src/training/features.py` and import it from both training and serving to prevent training-serving skew.
- Separate ingestion/transformation/validation when those modules have distinct contracts; do not create empty folders simply to resemble a template.
- If time is limited, add `infra/terraform/README.md` with the planned modules before attempting a full refactor.

## Action plan to kick-start the revision

### Phase 1 — Fix the story and evidence first

1. Freeze the current slide export as the before-version.
2. Add a label-distribution slide using the actual 53.6% / 72.0% / 71.6% chronological rates.
3. Add the model-evidence slide with the three-model table and calibration caveat.
4. Correct the false-negative/false-positive wording and add recall at the operating threshold.
5. Rewrite slide titles as claims using the proposed sequence above.

Definition of done: an interviewer can explain the target, time shift, model choice, metric choice, and threshold risk without seeing the architecture.

### Phase 2 — Redesign the architecture content

1. Propose the primary serving target—recommended SageMaker real-time endpoint—and state that the final choice is agreed with the MLOps lead/team based on the existing platform and SLOs.
2. Convert the existing architecture into four visual rails: CI/CD, offline ML, online serving, monitoring/feedback.
3. Replace generic boxes with official AWS service icons.
4. Add the missing paths:
   - EventBridge/MWAA orchestration;
   - S3 snapshot and offline features;
   - SageMaker Processing/Training/Registry/Endpoint;
   - CloudWatch -> SNS -> Amazon Q Developer in chat applications -> Slack;
   - Terraform and IAM/KMS as cross-cutting controls.
5. Remove duplicate or ambiguous serving components.
6. Add a small ownership legend for ML workload, shared MLOps platform, and Data Science collaboration.

Definition of done: every arrow represents a concrete data, artifact, control, or alert flow that can be explained in one sentence.

### Phase 3 — Add the scalability and reliability narrative

1. Create the “Scale each bottleneck independently” slide.
2. State explicitly that distributed training is unnecessary for 28k rows today.
3. Add measurable triggers for scaling: training SLO, memory limit, inference p95/p99, concurrency, error rate, and utilization.
4. Add idempotency keys, immutable versions, champion approval, and rollback semantics.
5. Prepare one answer for SageMaker serving and one for an EKS alternative.

### Phase 4 — Align the repository without over-refactoring

1. Add an `infra/terraform/` design skeleton that describes the resources and interfaces expected from the shared MLOps platform. Implement a dev environment only if the assessment scope and time justify it.
2. Evolve the new `src/training/` and `src/serving/` package boundaries only when a module has a clear owner and the tests remain green.
3. Keep notebooks for EDA and diagnostics; keep production logic importable and tested.
4. Rerun tests and update the test count shown in the deck.
5. Update README and architecture documentation to match the final names and flows.

### Phase 5 — Rehearse the interview path

Prepare concise answers to these likely questions:

- Why is an adverse outcome the positive class?
- Why does validation/test prevalence rise from 53.6% to about 72%?
- Why chronological rather than random split?
- Why LightGBM if logistic regression has lower log loss?
- How would calibration be fitted without leaking the test set?
- Which error is costlier, and how does that change the threshold?
- Why SageMaker endpoint rather than EKS model serving?
- When would distributed LightGBM be justified?
- How does a retry avoid producing or promoting the same model twice?
- What happens when Slack reports drift at 02:00?
- How does rollback restore both the model and its feature contract?

## Immediate next three actions

If starting now, do these in order:

1. Build the content-only version of slides 4 and 5 from the proposed Markdown: label/time shift, then model evidence and metric rationale.
2. Redraft the architecture on paper using the recommended AWS flow and explicitly choose SageMaker as the champion-serving target.
3. Replace the generic closing slide with the “Automation does not mean automatic trust” conclusion.

Those three changes address the highest-risk interview gaps before any detailed icon work or code reorganization.
