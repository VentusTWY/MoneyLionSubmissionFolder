# Interview Presentation and POC Demo Runbook

This is the single presentation guide for `documentation/TanWeiYang_GenDigital2026SeniorMLAssesment.pdf`.

Use it as a speaking guide, not a script to read. The central argument is:

> The solution is not just a LightGBM model. It is a governed lifecycle in which every prediction is traceable, every promotion is evidence-gated, and every release is reversible.

## Recommended timing

Default plan:

- Slides 1-10, including the repository overview: roughly 13 minutes.
- Live POC: 5 minutes.
- Slide 11: close and move to questions.

Before starting, say:

> "I have prepared a roughly 13-minute system walkthrough followed by a five-minute POC demonstration. I am happy to adjust if you would prefer more time for questions."

If the interviewer gives only 10 minutes, use the compressed route at the end of this document.

## Three messages to repeat

1. The prediction point defines the feature contract and prevents leakage.
2. Training creates a candidate; evidence and approval create the champion.
3. Service health, distribution change and predictive quality arrive on different timelines and require different responses.

## Slide-by-slide narrative

### Slide 1 - Loan Risk Predictor ML System Design (40 seconds)

Say:

> "I will walk through the path from application-time data to a governed production model. LightGBM provides the risk ranking, but the main engineering problem is keeping the target and features leakage-safe, evaluating honestly over time, promoting only validated versions, serving the approved model reliably, and retaining evidence after deployment. I will finish by showing those controls in the working POC."

Transition:

> "I will start by defining exactly what the model predicts."

### Slide 2 - LightGBM Machine Learning Model Definition (55 seconds)

Say:

> "The model estimates the probability of an adverse repayment outcome before pricing. A fully paid-off funded loan is the good outcome; collection, settled bankruptcy and charge-off are adverse outcomes, which I treat as the positive class. I exclude ambiguous statuses instead of forcing them into a class without an agreed loss definition. There is also a selection limitation: repayment outcomes are observed only for historically funded loans, so this evaluation does not directly measure performance on previously rejected applicants."

Do not over-explain every status. The interview value is the explicit target definition and the funded-loan selection caveat.

Transition:

> "Once the target is fixed, the prediction point determines what the model is allowed to see."

### Slide 3 - Feature Contract & Leakage Control (1 minute 30 seconds)

Say:

> "The prediction point is before pricing and before the lending decision. The model may use application-time information such as loan amount, lead characteristics, application time, Clarity signals and prior-loan history. It must not use APR, scheduled payments, approval outputs, final status or repayment records because those are created after, or influenced by, the decision. Raw identifiers are also excluded from the feature matrix."
>
> "The feature contract gives training-serving parity: the same definitions, types, transformations, ordering and missing-value rules run in both paths. I then split chronologically rather than randomly. The adverse rate rises from 53.6% in training to about 72% in validation and test, so the later untouched cohort exposes a real temporal shift instead of mixing future and past applications."

Point to the prediction boundary first, then the chronological adverse-rate chart. Do not read both feature lists.

Transition:

> "That untouched chronological test cohort is the basis for the model comparison."

### Slide 4 - Model Metrics Evaluation (2 minutes 10 seconds)

Say:

> "I chose ROC-AUC and PR-AUC because they answer two complementary ranking questions."
>
> "ROC-AUC measures overall ranking quality. In practical terms, if I randomly select one adverse loan and one paid-off loan, how often does the model assign the adverse loan a higher risk score? A score of 0.5 represents random ranking, while 1.0 represents perfect separation."
>
> "PR-AUC focuses specifically on the adverse class. Precision asks: of the applications flagged as risky, how many are actually adverse? Recall asks: of all adverse applications, how many did we successfully identify?"
>
> "Recall is particularly important because a false negative means an adverse applicant is predicted as low risk and may be approved. We may therefore want higher recall to reduce potential credit losses. However, increasing recall normally creates more false positives, meaning more good applicants may be declined or referred for review. PR-AUC evaluates this precision-recall trade-off across different thresholds."
>
> "Comparing the benchmarks, LightGBM has the strongest AUC metrics, reaching 0.737 ROC-AUC and 0.849 PR-AUC. Logistic regression has the better log loss, so LightGBM ranks applicants better but its raw probabilities are less reliable. I would therefore assess and calibrate the LightGBM probabilities before using them directly for pricing or expected-loss calculations."
>
> "The operating threshold is a separate business decision. A lower threshold catches more adverse applications and reduces false negatives, but it also increases false positives. A higher threshold approves more customers, but exposes the business to greater credit risk."
>
> "That decision should consider expected losses, the desired approval rate, manual-review capacity, customer impact, and fairness or compliance requirements. The threshold can be changed without retraining the model."

If interrupted, lead with the conclusion: LightGBM ranks best; logistic regression calibrates better; business costs set the threshold.

Transition:

> "The next slide talks about the architecture and production lifecycle."

### Slide 5 - Production Target Architecture (1 minute 50 seconds)

Explain the architecture by lanes, not box-by-box.

Say:

> "The design separates software delivery, offline training, online serving and monitoring. Across the top, code and tests become an immutable image, while Terraform manages infrastructure. This keeps application deployment separate from model promotion."
>
> "In the offline path, a scheduled workflow starts from a versioned data snapshot, then runs processing, training and evaluation gates. The output is an immutable candidate in the model registry; training completion does not make it production."
>
> "In the online path, the lending workflow enters through the platform's API entry layer. API Gateway can provide API management and an ALB can route to the EKS API service. EKS validates and authenticates the application request, then invokes the stable SageMaker real-time endpoint hosting the approved model. SageMaker distributes inference across its own model instances."
>
> "Monitoring also has two paths: immediate service telemetry and delayed outcome-based model quality. Either can trigger investigation or controlled retraining, but neither can bypass the promotion gates. The local Docker Compose POC uses simpler components while preserving these boundaries."

Important wording:

- The ALB routes traffic to the EKS API targets, not to individual SageMaker replicas.
- EKS hosts the surrounding API services in the selected design.
- SageMaker is the selected managed model-serving path; model serving on EKS is an alternative when custom control justifies the operational cost.

Transition:

> "The most important boundary is the point where a candidate becomes the active champion."

### Slide 6 - Model Training & Promotion Controls (1 minute 35 seconds)

Say:

> "Training produces a candidate, not a production model. First, the candidate must pass data-quality, minimum-sample and predictive-quality gates. The POC thresholds are illustrative; business and risk owners must approve the production criteria."
>
> "In the POC, a run that passes every gate is registered as an immutable version and promoted automatically. That promotion atomically replaces the local `champion.json` pointer and records the actor, reason, previous version, new version and time. This automatic promotion is a POC simplification."
>
> "In production, I would separate automated evidence gates from the approval decision. An approved model package in SageMaker Model Registry would be deployed through a versioned endpoint configuration, while the previous approved configuration remains available. The serving path then reloads and smoke-tests the selected version. The local POC automatically restores the prior pointer if that smoke test fails; SageMaker requires configured deployment guardrails and alarms for automatic rollback."

Be precise about recovery:

- A health check can remove or replace an unhealthy instance.
- A smoke-test failure can restore the prior champion in the local POC.
- A SageMaker deployment rolls back automatically only when the deployment guardrails and alarms are configured.

Transition:

> "Once a version is approved, the serving layer must handle changing traffic without changing the model decision itself."

### Slide 7 - Model Serving & Autoscaling Strategy (1 minute 30 seconds)

Say:

> "Traffic enters through the API entry layer shown on the previous slide, reaches the EKS API service for validation and authentication, and then invokes one stable SageMaker endpoint. SageMaker hides distribution across the model instance pool behind that logical interface."
>
> "The two layers scale independently. EKS API pods scale with application traffic and API resource metrics. SageMaker instances scale primarily on invocations per instance, while latency, CPU and 5xx errors act as guardrails. CPU here means utilization of the model-serving instances; errors mean failed endpoint invocations, not CPU errors."
>
> "I would not guess the instance counts. I would load-test expected and peak concurrency, measure sustainable throughput per instance against the p95 or p99 latency and error SLO, then derive the minimum, maximum and target capacity. Scale-out cooldown should reflect measured model-load time; scale-in should be longer and conservative to avoid flapping."
>
> "Training is different: about 28,000 rows fit one CPU job, so I would distribute training only after a measured runtime or memory constraint."

If asked how to distinguish scaling from rollback:

- Load-dependent latency, saturation and errors that improve as capacity increases indicate a capacity problem.
- Failures that begin with a deployment, reproduce at low traffic or fail controlled requests indicate a faulty version and support rollback.
- High CPU alone supports scaling; it is not evidence that rollback is required.

Transition:

> "Serving health is immediate, while evidence about model quality arrives later."

### Slide 8 - Service Health & Model Quality Monitoring (1 minute 30 seconds)

Say:

> "The monitoring design separates three evidence horizons. In seconds to minutes, service-health metrics tell me whether the system is responsive: volume, latency percentiles, validation failures, 5xx errors and model-load failures."
>
> "Before repayment labels mature, I cannot measure predictive performance. Feature drift, missingness, changing categories and score shifts are early investigation signals. PSI shows that a distribution changed; it does not prove the model became worse."
>
> "After outcomes mature, I join prediction events to outcomes by loan ID and compute ranking, log loss, recall and calibration by model version. Every event carries the model and feature-contract version, so an alert is traceable to the exact deployment. Alerts open investigation, remediation or controlled retraining; they do not promote a model automatically."

Transition:

> "Together, those controls produce three system-level guarantees."

### Slide 9 - Design Summary (50 seconds)

Say:

> "The design reduces to three guarantees. Model integrity means every prediction uses only information available at decision time and is evaluated on genuinely later data. Safe delivery means candidates are reproducible, evidence-gated, auditable and reversible. Continuous oversight means immediate service health, early distribution changes and delayed outcome quality are monitored separately by version."
>
> "The POC demonstrates those boundaries through reproducible training, controlled promotion, traceable serving and tested recovery. Every prediction is traceable, every promotion is evidence-gated, and every release is reversible."

Transition:

> "I will now show those controls through one scoring request and one controlled champion change."

### Slide 10 - POC Demo: Scoring & Model Operations (about 1 minute before switching)

Before opening the browser, briefly show this compact repository tree. Do not tour individual files.

```text
notebooks/       # reproducible analysis
src/
  training/      # offline pipeline
  serving/       # online inference
  mlops.py       # promotion and rollback
  monitoring.py  # drift and performance
configs/         # externalised policies
tests/           # automated verification
registry/        # generated local model state
documentation/   # design and implementation
infra/terraform/ # cloud integration contract
```

Say:

> "Before running the demo, I will briefly show how the repository maps to the assessment requirements. The `notebooks` folder contains the reproducible exploratory analysis and its HTML export. Production code is moved out of the notebooks into `src`: `training` contains ingestion, validation, feature engineering, temporal training and evaluation, while `serving` contains the independent online prediction API."
>
> "The shared transformation code preserves training-serving parity. Governance operations such as evidence gates, registration, promotion and rollback are separated into `mlops.py`, while `monitoring.py` handles drift and delayed performance. Configuration is externalised under `configs`, automated checks are under `tests`, and `registry` represents the generated local model versions, audit history and champion pointer."
>
> "The `documentation` and `infra` folders contain the production design and cloud integration contract. The original assessment data and generated artifacts are Git-ignored rather than included in the submission. This structure separates experimentation, offline training, online serving and governance so each area can be tested and changed independently."

Then point to the two interfaces on slide 10 and say:

> "The left-hand interface exposes the scoring contract and traceable result. The restricted operations interface exposes the active champion, candidate evidence and controlled promotion or rollback. I will use the live application rather than read the screenshots."

Switch to the prepared browser tabs and follow the demo plan below.

### Slide 11 - Questions & Discussions (20 seconds)

After the demo, return to slide 11 and say:

> "That completes the path from a leakage-safe prediction contract to an evidence-gated champion, a traceable decision and a recoverable model change. Thank you; I welcome questions on the model evidence, production boundaries or operational controls."

## Five-minute live POC demo

### Demo objective

Demonstrate one end-to-end claim, not every feature:

> A request is scored by the approved champion, the response identifies the exact model and contract, and privileged champion changes require an authenticated actor and recorded reason.

### Browser preparation

Open these tabs before screen sharing:

1. The PDF in presentation mode.
2. `http://localhost:3000` - scoring workspace.
3. `http://localhost:3000/admin` - already authenticated if the session permits.
4. A terminal in the repository root, with no secrets visible.

Keep slide 10 available as the visual fallback if the live application fails.

### Demo sequence

#### 0:00-0:30 - Establish the active contract

On the scoring page, point to:

- Scoring service online.
- Active model version.
- Feature contract `pre_pricing_v1`.
- Review and reject thresholds.

Say:

> "The client sees one stable scoring interface, while the response remains tied to a specific approved model and feature contract."

#### 0:30-1:45 - Submit one normal request

Use the default single-request form. The prepared champion currently returns a medium-risk review result for the default application; do not promise the exact probability because it can change when the champion changes.

After submitting, point to:

- Adverse-outcome probability.
- Risk band and operational action.
- Model version.
- Request ID.
- Runtime request count and latency.

Say:

> "The API returns both a model score and an operational interpretation, but the response is also traceable to the exact model, contract and request."

Do not spend time trying several applications or attempting to produce every risk band.

#### 1:45-3:30 - Show controlled model operations

Move to the restricted admin page and point to:

- Active champion.
- Previous rollback target.
- Candidate evaluation metrics.
- Required reason field.

Say:

> "The UI is not a second model registry. It exposes the same immutable versions and champion pointer used by the API. A model change requires an authenticated operator and a reason."

Enter a clear reason such as:

> `Interview demo - controlled rollback to previous approved champion`

Use **Roll back to previous champion**. Point out the changed active version. Do not expose `.env` or the admin API key.

Say:

> "The API atomically changes the pointer, reloads and smoke-tests the selected bundle, and records the actor, reason and previous version. If loading or the smoke test fails, the local registry restores the prior pointer."

#### 3:30-4:30 - Prove the serving path follows the champion

Return to the scoring workspace and refresh. Point to the changed active model version, then submit the same request once more if time allows.

Say:

> "The client still calls the same endpoint. The version changes behind the stable interface, and the response identifies which champion produced it."

#### 4:30-5:00 - Close the loop

If the terminal is already prepared, show only the last two audit records:

```bash
tail -n 2 registry/audit.jsonl
```

Point to the actor, reason, previous version, new version and timestamp. Do not open the entire registry tree.

Close with:

> "This demonstrates the same boundaries as the production design: immutable versions, a controlled champion pointer, traceable serving and a tested recovery path."

## Optional four-minute code walkthrough

Do not mix this into the default five-minute UI demo. Offer it after the demo or open it when an interviewer asks how a control is implemented.

Keep these files open in the editor before the interview:

1. `src/training/pipeline.py`
2. `src/training/features.py`
3. `src/mlops.py`
4. `src/serving/predictor.py`
5. `tests/test_mlops.py`

### 0:00-0:45 - End-to-end orchestration

Open `src/training/pipeline.py` at `execute()`.

Show only the numbered orchestration steps:

- Load the training and promotion configuration.
- Build the run artifacts and data-quality evidence.
- Evaluate promotion gates.
- Write the manifest and register the immutable version.
- Promote and smoke-test only when the evidence passes.

Say:

> "The pipeline is deliberately thin. It composes independently tested stages and makes the promotion decision explicit; training completion alone cannot update the champion."

Do not step through LightGBM fitting line by line.

### 0:45-1:30 - Training-serving parity

Open `src/training/features.py` at `transform_features()`.

Point out:

- The feature contract rejects forbidden fields.
- Training records an ordered feature schema.
- Inference recreates nullable fields and enforces that saved ordering.

Say:

> "This shared transformer is the executable version of slide 3. It prevents post-decision fields from entering training and prevents the API from silently creating a different feature matrix."

If asked about the target, briefly open `src/training/labels.py:create_resolved_target()`; do not add it to the default tour.

### 1:30-2:45 - Gates, atomic promotion and recovery

Open `src/mlops.py` first at `evaluate_gates()`, then at `LocalRegistry.promote()`.

Point out:

- Each gate produces an auditable pass/fail result.
- `verify_bundle()` checks the immutable bundle before use.
- Promotion remembers the current champion and atomically changes the pointer.
- The supplied smoke test reloads through the serving path.
- An exception restores the previous pointer and writes an audit event.

Say:

> "This is the core safety boundary. The model bundle is verified before promotion, the pointer change is serialized and atomic, and a failed serving smoke test restores the prior champion."

### 2:45-3:40 - Traceable serving and privileged operations

Open `src/serving/predictor.py` at `LoanRiskPredictor.predict()`, then the admin routes.

Point out:

- The predictor loads only the registry champion and its saved schema.
- Every result includes the model version and feature-contract version.
- Middleware creates a request ID and metadata-only audit event.
- Admin endpoints require a server-side key plus an actor and reason.
- Promotion and rollback both reload and smoke-test before changing the in-process predictor.

Say:

> "The stable endpoint does not hide governance evidence. Every prediction identifies the model and contract, and privileged model changes reuse the same registry and smoke-test path rather than updating UI-only state."

### 3:40-4:00 - Prove the failure path is tested

Open `tests/test_mlops.py` at `test_failed_smoke_restores_champion()` and then mention `test_admin_model_operations_require_a_key_and_reload_the_predictor()`.

Say:

> "I test the failure behavior, not just the happy path: a failed smoke test restores the champion, and the admin endpoints require authentication and reload the predictor after a controlled change."

Stop there. The objective is to demonstrate the system's important boundaries, not conduct a full repository tour.

## Day-before checklist

Run from the repository root:

```bash
.venv/bin/python -m pytest -q
docker compose config --quiet
docker compose up -d --build
curl -s http://localhost:8000/health/ready | python -m json.tool
curl -s http://localhost:8000/v1/model | python -m json.tool
curl -I http://localhost:3000
```

Confirm:

- All tests pass. The current baseline is 28 passing tests.
- The readiness response names the expected champion.
- `registry/champion.json` contains both `version` and `previous_version`.
- The scoring page loads and produces a result.
- Admin login works without displaying credentials on screen.
- Promotion or rollback was rehearsed once, then the starting champion was restored.
- Docker images and dependencies are cached locally.
- The PDF, scoring page, admin page and terminal are already arranged in separate tabs or windows.
- Notifications, password-manager popups and unrelated browser tabs are closed.
- Screen resolution and browser zoom make the result and model version readable.

Do not run a full retraining job during the timed demo. Explain that path from slides 5 and 6; demonstrate scoring and champion control live.

## Ten-minute pre-interview checklist

```bash
docker compose up -d
curl -s http://localhost:8000/health/ready | python -m json.tool
curl -s http://localhost:8000/v1/model | python -m json.tool
```

Then:

- Submit one scoring request.
- Verify that the admin page identifies a previous champion.
- Clear any temporary reason text from the admin form.
- Return the scoring form to its default state.
- Leave the application running; do not rebuild immediately before presenting unless necessary.

## Fallback plan

### If the UI fails but the API works

Use the terminal:

```bash
curl -s -X POST http://localhost:8000/v1/predict \
  -H 'Content-Type: application/json' \
  -d '{"applicationDate":"2026-08-05T12:00:00Z","loanAmount":500,"leadCost":25,"leadType":"bvMandatory","payFrequency":"B","state":"CA","has_clarity_report":false}' \
  | python -m json.tool
```

Point out `adverse_probability`, `decision`, `model_version`, `feature_contract_version` and `request_id`.

Then show:

```bash
python -m json.tool registry/champion.json
tail -n 2 registry/audit.jsonl
```

### If Docker fails

Do not troubleshoot live for more than 30 seconds. Return to slide 10 and walk through the two captured interfaces. Say that the automated test suite and local preflight passed before the interview, then continue to questions.

### If the admin session expires

Use the login page. If authentication still fails, continue with scoring and explain the operations screenshot on slide 10. Never reveal or paste credentials while screen sharing.

## Likely follow-up answers

### Why LightGBM when logistic regression has better log loss?

> "LightGBM has the strongest ROC-AUC and PR-AUC, so it ranks adverse outcomes best on the chronological test cohort. Logistic regression's better log loss is evidence that LightGBM's raw probabilities need calibration before pricing or expected-loss use."

### Why not train on rejected applicants?

> "Rejected applicants do not have observed repayment outcomes. Treating them as adverse would reproduce the historical approval policy rather than measure repayment risk. I would analyse selection bias and consider reject inference only with additional evidence and governance."

### Why both API Gateway or ALB, EKS and SageMaker?

> "They have different responsibilities. API Gateway can provide external API management; an ALB can route to healthy EKS API targets; EKS hosts validation, authentication and product logic; SageMaker hosts the managed model endpoint and distributes inference across its own instances. The exact entry-layer combination depends on the shared platform."

### Why not host the model on EKS?

> "EKS model serving is a valid alternative when a custom serving stack or tighter infrastructure control is required. I selected SageMaker for the primary path because it provides a managed endpoint, model-instance health and autoscaling with less operational ownership."

### How are autoscaling bounds selected?

> "Traffic volume alone is insufficient. I load-test a representative instance, identify sustainable throughput under the latency and error SLO, choose a target below that saturation point, and derive normal and peak instance counts with availability headroom."

### Capacity incident or faulty deployment?

> "A capacity problem correlates with load, saturation and recovery as traffic falls or capacity increases. A faulty deployment correlates with the release time, can reproduce at low traffic or on specific inputs, and should fail controlled comparisons or deployment alarms. I scale the constrained layer; I roll back only when the version is implicated."

## Compressed 10-minute route

If the total slot for presentation and demo is 10 minutes:

- Slide 1: 20 seconds - state the governed-lifecycle thesis.
- Slides 2-3: 1 minute 20 seconds - target, funded-loan limitation, prediction point and chronological split.
- Slide 4: 1 minute - LightGBM ranks best; calibration and threshold remain separate.
- Slide 5: 1 minute 20 seconds - explain the four lanes only.
- Slides 6-7: 1 minute 40 seconds - candidate-to-champion controls and independent API/inference scaling.
- Slide 8: 1 minute - three evidence horizons.
- Slide 9: 30 seconds - three guarantees.
- Demo: 3 minutes - one score, show admin controls, no live rollback unless invited.
- Slide 11: 10 seconds - close.

In the compressed version, never read service names from slide 5 or code snippets from slide 6.
