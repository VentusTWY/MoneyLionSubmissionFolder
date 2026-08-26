# Model Assumptions and Caveats

## Prediction point

The primary POC model scores before pricing and excludes `apr` and
`originallyScheduledPaymentAmount`. Although both fields are complete for the
28,360-row resolved modeling population, completeness does not demonstrate that
they existed before the lending decision. More importantly, a score intended to
influence APR cannot also require APR without a circular dependency.

The original model that includes both fields is labelled post-pricing and kept
only for comparison. A future offer-risk model could use applicant information
plus proposed APR, term, and payment to predict risk for a finalized offer. The
current observational data cannot establish the causal effect of changing APR:
the historical underwriting policy may have assigned higher APR to borrowers it
already considered risky.

## Target and population

The primary target maps Paid Off Loan to `0`, and External Collection, Internal
Collection, Settled Bankruptcy, or Charged Off to `1`. Settlement Paid Off and
Charged Off Paid Off are excluded because the supplied dictionary does not
define their business-loss treatment. Unfunded, unresolved, voided, rejected,
withdrawn, missing, and ambiguous outcomes are excluded. Four unfunded records
with terminal outcomes are quarantined as source inconsistencies.

Labels occur only for historically funded loans. The model therefore estimates:

```text
P(adverse repayment | funded under the historical policy, pre-pricing inputs)
```

It cannot demonstrate accuracy for rejected applicants. Changes to approval or
marketing policy may alter the scored population and require renewed validation.

## Outcome maturity

Recent loans must not be treated as good merely because default has not yet
occurred. A production system requires an agreed performance window and the time
at which each outcome became observable. The supplied extract appears to expose
current status rather than full status history, so filtering by age plus terminal
status is only a POC approximation. It cannot reconstruct a historically exact
rolling backtest without timestamped events or periodic outcome snapshots.

## Evaluation and decisions

Chronological validation reduces temporal leakage, but repeat customers overlap
between periods; raw identity is excluded and any future customer-history
feature must be computed strictly from earlier events. The fixed `0.50`
threshold is experimental. Production selection requires costs for adverse
funding, good-loan rejection, recovery, manual review, and capital, along with
affordability and legal constraints.

The pre-pricing LightGBM currently ranks better than logistic regression but has
worse log loss. Calibration should be assessed by time and risk band before its
probabilities are used for pricing or expected value. Aggregate metrics must be
supplemented by recent-period stability and legally approved subgroup review;
fairness policy and protected-attribute handling require legal ownership.

## Decisions requiring external approval

- Exact production scoring event and upstream field lineage
- Default/performance window and outcome timestamp source
- Ambiguous status treatment and recovery/loss definition
- Decision threshold and financial objective
- Affordability, pricing, and maximum-risk policies
- Monitoring groups, fairness tolerances, and legal constraints
- Retraining cadence, gate limits, owners, and rollback authority
