# Data inputs (quick)

Place the original dataset files in `data/raw/` before running the pipeline or demo UI. These files are NOT included in the repository.

Required files:
- `data/raw/loan.parquet`
- `data/raw/payment.parquet`
- `data/raw/clarity_underwriting_variables.parquet`

Example rows (pseudo-view of the source structure):

```text
loan.parquet:
loanId, applicationDate, loanAmount, payFrequency, state, clarityFraudId, isFunded, loanStatus
12345, 2025-11-15, 500, B, CA, 0987, 1, Paid Off Loan
12346, 2025-12-03, 700, M, NY, 1234, 1, Charged Off

clarity_underwriting_variables.parquet:
underwritingid, has_clarity_report, risk_score, income_verified
0987, 1, 0.43, 1
1234, 1, 0.72, 0

payment.parquet:
loanId, paymentDate, paymentAmount, paymentStatus
12345, 2026-01-15, 250, Paid
12345, 2026-02-15, 250, Paid
12346, 2026-02-01, 0, Default
```

The `data/README.md` here is intentionally minimal — full data preparation steps are in `documentation/DATA_PREPARATION.md`.
# Data layout

Place the three immutable source datasets supplied for the assessment under
`raw/` before running the pipeline:

- `loan.parquet` - loan applications and terminal loan status.
- `clarity_underwriting_variables.parquet` - application-time Clarity underwriting attributes.
- `payment.parquet` - outcome-time payment records used only for label audit and monitoring, never as prediction features.

Code should resolve these paths through `configs/baseline.yaml` rather than embedding file locations. Generated training bundles and models belong under `artifacts/`, not under `data/raw/`.

The source datasets are intentionally not included in this submission package.
