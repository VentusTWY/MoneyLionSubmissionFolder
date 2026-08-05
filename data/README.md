# Data layout

Place the three immutable source datasets supplied for the assessment under
`raw/` before running the pipeline:

- `loan.parquet` - loan applications and terminal loan status.
- `clarity_underwriting_variables.parquet` - application-time Clarity underwriting attributes.
- `payment.parquet` - outcome-time payment records used only for label audit and monitoring, never as prediction features.

Code should resolve these paths through `configs/baseline.yaml` rather than embedding file locations. Generated training bundles and models belong under `artifacts/`, not under `data/raw/`.

The source datasets are intentionally not included in this submission package.
