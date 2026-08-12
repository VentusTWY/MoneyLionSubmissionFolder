# Loan Risk Predictor - Interview Presentation Narration

Use this as a speaking guide rather than a script to memorize word-for-word.
The suggested pacing is approximately 9-10 minutes for the slides, followed by
a 3-4 minute demonstration.

## Slide 1 - Loan Risk Predictor ML System Design

Good morning, and thank you for the opportunity to present my solution.

The assignment asked for more than a LightGBM model. It asked for an automated
machine-learning system that can take future model improvements from data
ingestion through evaluation and controlled deployment.

I will first explain how I defined loan risk and avoided leakage. I will then
show the model evidence, the production architecture, and the controls around
promotion, rollback, and monitoring. Finally, I will demonstrate the working
POC through the scoring and model-operations interfaces.

**Transition:** I will start with the most important modeling decision: what
exactly the model is predicting.

## Slide 2 - Loan Risk Target Definition

The brief describes loan risk, but it does not give a formal target definition.
I therefore defined risk as the probability that a funded loan reaches an
adverse repayment outcome.

A paid-off loan is labelled as a good outcome. Internal or external collection,
settled bankruptcy, and charge-off are labelled as adverse outcomes.

I deliberately excluded statuses such as Settlement Paid Off and Charged Off
Paid Off because their financial interpretation is ambiguous without a business
loss policy.

One important limitation is that repayment outcomes are available only for
historically funded loans. Therefore, the model estimates risk conditional on
the previous underwriting policy. It does not directly establish performance
for previously rejected applicants.

**Transition:** Once the target is defined, the next question is what
information the model is allowed to see.

## Slide 3 - Model Design, Leakage Controls and Evaluation

The prediction point is before pricing and before the lending decision. That
timing determines the feature contract.

APR and scheduled payment amount are excluded because they are produced later
and could also be influenced by the model's output. Outcome fields, payment
records, and final loan statuses never enter the feature matrix.

Loan status is used only to construct the label, while payment records are used
as an independent consistency check.

Application date is transformed into month, day of week, and hour. Features
such as the fraud score and number of previously paid-off loans are retained
because they are application-time information.

For evaluation, I use a chronological split rather than a random split. That
better represents how the model would perform on future applications and
reduces temporal leakage.

**Transition:** The next slide shows what that chronological evaluation
actually produced.

## Slide 4 - LightGBM Improves Ranking, but Calibration Remains a Caveat

The final modeling cohort contains 28,360 funded loans with mature,
unambiguous outcomes. These were split chronologically into training,
validation, and an untouched test population of 5,672 records.

The test adverse-outcome rate is 71.6 percent, which is important when
interpreting PR-AUC. A no-skill predictor already has a PR-AUC of 0.716 because
PR-AUC depends on the prevalence of the positive class.

LightGBM achieves a ROC-AUC of 0.737 and PR-AUC of 0.849. This means it ranks
adverse outcomes better than the simple reference models. Logistic regression,
however, produces a lower log loss: 0.562 compared with 0.615.

The assignment specifically requires LightGBM, so LightGBM remains the model
used by the automated system. The constant predictor and logistic regression
are sanity baselines, not competing deliverables. They help demonstrate that
the evaluation pipeline can place the required model in context.

The main conclusion is that LightGBM provides better ranking, while its raw
probabilities need further calibration before they are used directly for
pricing or expected-loss calculations.

**Transition:** Having established the candidate model and its evidence, I will
now show how it moves through the wider production system.

## Slide 5 - Production Target Architecture

This diagram represents the production target architecture. The local POC
implements the same logical boundaries using Docker Compose and a
filesystem-backed registry.

At the top, the CI/CD control plane tests, scans, and deploys application code
and container images. This is intentionally separate from model promotion.

Within the ML lifecycle, the offline pipeline reads immutable data snapshots,
validates the inputs, builds features, trains a challenger, and evaluates it
against promotion gates. Accepted artifacts are stored as immutable model
versions.

The online pipeline loads only the approved champion and serves synchronous
scores through the FastAPI service.

Finally, prediction events, outcomes, and service metrics feed the monitoring
pipeline. Monitoring may trigger investigation or retraining, but it never
promotes a model automatically.

That separation allows software deployment and model governance to evolve
independently.

**Transition:** The most sensitive boundary in this design is the point where a
candidate becomes the live champion.

## Slide 6 - Promotion Controls

A newly trained model does not become live simply because training completed.

First, the candidate must pass evidence gates covering data quality, minimum
sample size, ROC-AUC, and log loss. These POC thresholds are configurable;
production thresholds would require agreement from risk and business owners.

If the candidate passes, the bundle and checksums are verified. Promotion is
serialized with a lock, and the champion pointer is changed atomically. The
audit log records the actor, reason, previous version, and new version.

The service then reloads the selected model and performs a smoke test. If that
test fails, the previous champion is restored automatically.

This means a failed candidate or interrupted promotion leaves the system on a
known working model rather than in a partially updated state.

**Transition:** Safe promotion handles model change. Monitoring determines
whether the deployed system remains healthy afterwards.

## Slide 7 - Monitoring and Observability

I separate monitoring into three time horizons because operational evidence and
model-quality evidence arrive at different speeds.

The first layer is live service monitoring. Within seconds or minutes, latency,
errors, and request volume reveal whether the API is functioning correctly.

The second layer covers early model signals before labels mature. Current
feature and score distributions are compared with the training reference using
PSI. A warning triggers investigation, not automatic retraining or promotion.

The third layer begins when repayment outcomes become available. Prediction
audit events are joined to outcomes by loan ID while retaining the model
version. ROC-AUC, PR-AUC, and log loss are then calculated separately for each
deployed version.

This avoids mixing operational failures, distribution drift, and actual
predictive degradation into a single alert.

**Transition:** These decisions can be summarized through three design
principles.

## Slide 8 - Design Summary

The design is built around three principles.

First, model integrity: predictions use only information available at the
stated decision point, with explicit leakage controls and chronological
evaluation.

Second, safe delivery: model artifacts are reproducible and versioned, and only
candidates that pass evidence gates can become the champion. Promotion and
rollback are atomic and audited.

Third, continuous oversight: the system monitors immediate service health,
early distribution changes, and delayed model performance.

The POC implements these boundaries with a one-command pipeline, immutable
model bundles, automated tests, controlled promotion, and tested rollback.

**Transition:** I will now show those controls working through the POC.

## Slide 9 - POC Demonstration: Scoring and Model Operations

These two interfaces are windows into the underlying Python system.

The scoring workspace shows the active model and contract version. An
application can be submitted to receive an adverse-outcome probability, risk
band, decision, request ID, and exact model version.

The restricted model-operations page shows registered candidates and provides
controlled promotion and rollback. Every change requires an operator identity
and reason and is written to the audit history.

For the live demonstration, I will first confirm that the service is ready and
show the active champion. I will submit a valid prediction and explain the
versioned response. I will then show controlled validation with an invalid
request.

Finally, I will promote a prepared candidate, confirm that the active model
changes without restarting the API, and roll back to the previous champion.

### Short demo commentary

1. **Readiness:** The service is healthy and has loaded this champion version.
2. **Valid prediction:** The response includes the probability, operational
   decision, request ID, model version, and feature-contract version.
3. **Invalid prediction:** Invalid input is rejected at the contract boundary
   before reaching the model.
4. **Promotion:** This candidate has already passed its gates. Promotion
   verifies it, updates the champion atomically, and reloads it in-process.
5. **Rollback:** Rollback restores the previous verified champion and records
   the change in the audit history.

## Slide 10 - Questions and Discussion

To summarize, I built a reproducible vertical slice covering data validation,
LightGBM training, evidence-based promotion, versioned serving, rollback, and
monitoring.

The central design decision is that automation does not mean automatic trust.
Training can be automated, but every model change remains evidence-based,
versioned, observable, and recoverable.

I spent approximately **[insert actual number] hours** across data analysis,
modeling, system design, implementation, testing, documentation, and
presentation preparation.

Thank you. I am happy to discuss any part of the modeling assumptions,
architecture, or implementation.

---

# Slide 4 Metrics Cheat Sheet

This section is for preparation and should not be read aloud in full.

## Why show baselines if the assignment requires LightGBM?

Yes, keep them, but describe them as **sanity baselines**, not as alternative
models you considered deploying instead of the requested LightGBM model.

They answer three useful engineering questions:

1. Does the evaluation pipeline detect a model that has no predictive skill?
2. Does LightGBM add ranking value beyond a simple linear model?
3. Do the metrics reveal a limitation that should affect promotion or serving?

This is relevant to an ML engineering role because promotion gates need
meaningful, reproducible evidence. A pipeline should not promote a candidate
merely because training finished successfully.

## Constant predictor

The constant predictor assigns every record the same probability, normally the
adverse rate observed in the training population.

It cannot rank one application above another, so its ROC-AUC is 0.500. Its
PR-AUC is close to the adverse-class prevalence. In the chronological test set,
the adverse rate is 71.6 percent, so the no-skill PR-AUC reference is 0.716.

Use it to answer: **Does the trained model do more than reproduce the base
rate?**

## Logistic regression

Logistic regression is a simple linear benchmark. It is useful because it is
easy to train, reproducible, and often produces reasonably behaved
probabilities.

Use it to answer: **Does LightGBM's nonlinear tree structure add useful ranking
performance beyond a simple model?**

Here, LightGBM produces higher ROC-AUC and PR-AUC, but logistic regression
produces lower log loss.

## ROC-AUC

ROC-AUC measures ranking across all possible thresholds.

A practical interpretation of 0.737 is: if one adverse loan and one good loan
are selected at random, the model will assign the adverse loan a higher risk
score approximately 73.7 percent of the time.

ROC-AUC does not tell us whether a predicted probability of 0.80 really means
an 80 percent adverse rate. It measures ordering, not probability calibration.

## PR-AUC

PR-AUC summarizes the trade-off between:

- **Precision:** among loans flagged as adverse, how many are actually adverse?
- **Recall:** among all adverse loans, how many did the model identify?

PR-AUC depends strongly on the positive-class prevalence. That is why the
0.849 result should be compared with the 0.716 no-skill reference rather than
with zero.

## Log loss

Log loss evaluates the predicted probabilities themselves. It penalizes
confident mistakes heavily, and lower values are better.

LightGBM can rank loans correctly while still producing probabilities that are
too extreme or not well calibrated. That explains how LightGBM can win on
ROC-AUC and PR-AUC while logistic regression wins on log loss.

## What calibration means

A model is calibrated when predicted probabilities match observed frequencies.
For example, among applications assigned approximately 20 percent risk, about
20 percent should eventually have an adverse outcome.

If calibrated probabilities are required, calibration can be fitted on the
validation population using a method such as Platt scaling or isotonic
regression, then evaluated once on the untouched chronological test set.

This is future work for the POC. It should not be fitted using the test set.

## Recommended one-sentence answer if challenged

> The assignment required LightGBM, so that is the model implemented in the
> automated pipeline. I included constant and logistic sanity baselines to
> validate the evaluation framework and show that LightGBM adds ranking value,
> while also identifying calibration as a limitation before probability-based
> business use.

## What slide 4 proves from a pipeline perspective

The main purpose of slide 4 is not to demonstrate deep model selection. It
shows that the automated system has:

- A reproducible chronological split.
- An untouched test population.
- Multiple complementary evaluation metrics.
- Contextual baselines.
- Evidence that can feed promotion gates.
- A documented limitation that prevents overclaiming.
