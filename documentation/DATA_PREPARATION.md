# Loan Risk Data Preparation and Join Process

## Purpose

This document defines how the three source tables are validated, cleaned, joined, and converted into the versioned modeling dataset. The prediction unit is one funded loan application, and the primary POC prediction point is before pricing.

Payment outcomes are not model features. They may be used only in a separate outcome-audit process.

## Source Tables and Cardinality

The initial scan found:

| Table | Key | Relationship | Initial observation |
|---|---|---|---|
| `loan.parquet` | `loanId` | One row per loan application | 573,402 rows; 255 null IDs; all 573,147 non-null IDs are unique |
| `clarity_underwriting_variables.parquet` | `underwritingid` | One underwriting report | 49,596 rows; key is unique and non-null |
| `payment.parquet` | `loanId` | Many payment attempts per loan | 689,364 rows across 39,952 loan IDs |

The main joins are:

```text
loan.clarityFraudId = clarity.underwritingid
loan.loanId         = payment.loanId
```

Clarity is a many-to-one application-time join. Payment is a one-to-many outcome-time relationship and must never be joined at raw row level into the feature table.

## Use of `anon_ssn`

`anon_ssn` is a hashed customer identifier. It should not be used to deduplicate the loan table because one customer can legitimately have multiple loan applications over time.

Use `anon_ssn` for:

- identifying repeat customers;
- preventing customer leakage during validation where appropriate;
- calculating historical features from loans strictly earlier than the current application; and
- reporting model performance separately for new and returning customers.

Do not use the raw `anon_ssn` value as a model feature. It is a high-cardinality identifier and could encourage memorization rather than generalizable risk learning.

Deduplication rules are therefore:

```text
Loan records: deduplicate or reject duplicates by loanId, not anon_ssn.
Customer records: preserve repeated anon_ssn values as separate chronological loans.
Clarity records: require one row per underwritingid.
Payment records: preserve multiple attempts, then aggregate only for outcome audits.
```

## Step-by-Step Process

### Step 1 - Load and validate schemas

Load each source independently and check required columns, readable types, row counts, and key fields. Fail on missing required columns or duplicate non-null `loanId` values. Report null loan IDs rather than assigning synthetic IDs.

Store the source file names, row counts, schemas, and run timestamp in metadata.

### Step 2 - Standardize the loan application table

Use `loan.parquet` as the base table because it represents the prediction unit.

1. Parse `applicationDate` and `originatedDate` as timestamps.
2. Preserve the raw status values for auditability.
3. Validate binary fields such as `originated`, `approved`, and `isFunded`.
4. Validate that non-null `loanId` values are unique.
5. Quarantine records with impossible or contradictory outcome combinations.

The initial scan found three records with `loanStatus = "Internal Collection"` and one record with `loanStatus = "Settled Bankruptcy"` despite `isFunded = 0`. They are reported and excluded from target construction rather than automatically corrected.

### Step 3 - Construct the target population

Keep only funded loans with an explicitly configured, resolved outcome:

```text
isFunded = 1
loanStatus is in the adverse or non-adverse terminal-status set
```

Initial target mapping:

```text
adverse_outcome = 1:
  External Collection
  Internal Collection
  Settled Bankruptcy
  Charged Off

adverse_outcome = 0:
  Paid Off Loan
```

Exclude unresolved, voided, rejected, withdrawn, and ambiguous outcomes. The primary baseline explicitly excludes `Settlement Paid Off` and `Charged Off Paid Off`; sensitivity experiments must use separate configurations so their assumptions do not silently alter the baseline population.

### Step 4 - Clean the Clarity underwriting table

1. Require `underwritingid` to be unique and non-null.
2. Remove export-only index columns such as `__index_level_0__`.
3. Preserve numeric values, booleans, and categorical identity-match results.
4. Do not impute missing Clarity values before the temporal split.
5. Record missingness and category levels for monitoring.

### Step 5 - Left-join Clarity to eligible loans

Left-join from the target-eligible loan population:

```text
eligible_loans.clarityFraudId = clarity.underwritingid
```

Enforce a `many_to_one` join so that each loan produces at most one modeling row. Preserve loans without a matching report and add:

```text
has_clarity_report = 1 when a report matched, otherwise 0
```

Do not inner-join and discard missing reports. Clarity availability depends on the underwriting flow, so dropping unmatched loans would introduce additional selection bias.

### Step 6 - Keep payment processing separate

Do not add raw payment columns to the application-time modeling dataset. Payment dates, amounts, statuses, return codes, and collection-plan indicators occur after the prediction point and would leak repayment performance.

If payment data is used for an outcome audit:

1. Validate payment schema independently.
2. Aggregate payment attempts to one record per `loanId` before joining.
3. Derive only audit fields such as number of attempts, successful amount, rejected attempts, or first-payment outcome.
4. Compare those fields with `loanStatus` to investigate label quality.
5. Do not pass the audit fields into model training.

### Step 7 - Build application-time features

Candidate inputs include application fields and the matched Clarity report. Exclude identifiers, decision outcomes, repayment outcomes, and raw timestamps used only for splitting.

Always exclude:

```text
loanId
anon_ssn
clarityFraudId
underwritingid
originated
originatedDate
approved
isFunded
loanStatus
fpStatus
all payment-table fields
```

The primary `pre_pricing_v1` contract excludes `apr` and `originallyScheduledPaymentAmount` because the risk score may inform APR and repayment terms. The older post-pricing model that includes them is retained only as an ablation reference. Completeness in historical funded rows does not prove that either field was available at the intended scoring event.

Keep the raw Clarity variables for the initial LightGBM baseline. LightGBM may apply Exclusive Feature Bundling internally to sparse, mutually exclusive features, but EFB is a computational optimization rather than a semantic feature-engineering step. Many Clarity inquiry counts and fraud flags can be non-zero or true at the same time, so they must not be manually bundled merely because they belong to the same source. Native categorical handling should be preferred over one-hot encoding where supported.

Later experiments may add documented domain aggregates, such as the total number of fraud flags or inquiry velocity, while retaining the raw variables for comparison. Any reduction should be justified through validation performance, stability, interpretability, or latency rather than an assumption that EFB will safely combine correlated fields.

Historical customer features may be computed with `anon_ssn`, but each value must use only applications and outcomes available before the current `applicationDate`.

### Step 8 - Split before fitting transformations

Use application time to create training, validation, and final test periods. Fit imputers, encoders, feature selection, and model parameters using the training period only.

Because customers can have multiple loans, report customer overlap across splits. Either use a group-aware policy or demonstrate that all repeat-customer features are strictly historical and that raw customer identity is unavailable to the model.

### Step 9 - Save versioned outputs and audit metadata

Recommended generated files:

```text
data/processed/loan_outcomes_v1.parquet
data/processed/application_features_v1.parquet
data/processed/loan_risk_modeling_v1.parquet
artifacts/prepricing_lightgbm/data_quality_report.json
artifacts/prepricing_lightgbm/data_cutoff.json
```

The final modeling dataset should contain one row per eligible `loanId`, application-time features, `has_clarity_report`, and `adverse_outcome`.

Record the target-definition version, source counts, exclusions, quarantined rows, join match rate, date ranges, feature list, and split boundaries with every run.

Generated processed data should normally be reproducible and Git-ignored. Do not include the original assessment data in the final submission package.

## Required Assertions

The pipeline should enforce or report:

```text
Non-null loanId is unique in the loan table.
underwritingid is unique in the Clarity table.
The Clarity join does not increase eligible-loan row count.
The final modeling table has one row per loanId.
Every labeled loan is funded.
Every target value is either 0 or 1.
Both target classes exist in every model-development split.
No payment or post-decision column appears in the feature list.
Temporal train dates precede validation and test dates.
```
