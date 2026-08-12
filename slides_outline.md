# Loan Risk Predictor — Presentation Outline

## Slide 1 — Loan Risk Predictor

- Production-shaped ML system for safe loan-risk scoring
- Presenter name, course, and date

## Slide 2 — The model predicts repayment risk — for business to decide if its review or perfectly nice

- Target: probability of an adverse repayment outcome for funded loans
- Good outcome: paid off loan
- Bad outcome: collection, bankruptcy, or charge-off

## Slide 3 — Careful target design prevents leakage

- Score before pricing and before the lending decision
- Exclude repayment, outcome, approval, APR, and payment fields
- Train only on mature, unambiguous outcomes

## Slide 4 — The solution covers the full model lifecycle

- Validate data → engineer features → train LightGBM
- Evaluate → apply promotion gates → register champion
- Serve predictions → monitor → retrain safely
- **Add the system visual diagram here**

## Slide 5 — Promotion controls protect the live model

- Absolute performance and data-quality gates
- Champion-relative comparison only on comparable evaluation sets
- Atomic promotion, audit history, smoke testing, and rollback

## Slide 6 — The API provides traceable real-time decisions

- Risk probability, risk band, and pass/review/reject decision
- Model version, contract version, and request ID
- Single and batch prediction endpoints
- **Add the scoring UI screenshot here**

## Slide 7 — Monitoring makes operation observable

- Latency, failures, request counts, and risk-band metrics
- PSI drift before outcomes mature
- ROC-AUC, PR-AUC, and log loss after outcomes arrive
- Audited promotion and rollback through the admin interface

## Slide 8 — One prediction feeds two monitoring paths

- Immediate service path: latency, errors, and request volume feed operational monitoring
- Delayed quality path: prediction audits wait for mature repayment outcomes
- Join versioned S3 outcomes to predictions by `loanId` while retaining `model_version`
- Calculate ROC-AUC, PR-AUC, and log loss by deployed model version
- Alerts trigger investigation or controlled retraining, never automatic promotion

## Slide 9 — The POC proves the safety boundaries

- 28 automated tests passing
- Reproducible versioned artifacts and training metadata
- Next steps: managed registry, cloud deployment, formal SLOs, and approved thresholds

## Closing / Demo

End with the live demonstration:

1. Show readiness and active model metadata.
2. Submit a valid prediction and explain the response.
3. Submit an invalid request and show controlled validation.
4. Promote a candidate, then roll back to the previous champion.
5. Show the audit entry and model-labelled metrics.
