"""Training-data quarantine rules and measured quality reports."""

from __future__ import annotations

import pandas as pd


def find_unfunded_terminal_outcomes(
    loans: pd.DataFrame,
    config: dict,
) -> pd.DataFrame:
    """Return terminal outcomes that contradict the funded-loan population.

    These rows are quarantined from target construction. Returning them also
    makes the anomaly available for data-quality reporting and investigation.
    """
    # Step 1: combine every configured terminal positive and negative status.
    label = config["label"]
    terminal_statuses = set(label["positive_statuses"]) | set(
        label["negative_statuses"]
    )

    # Step 2: identify funded records and records carrying a terminal outcome.
    funded = loans["isFunded"].fillna(0).astype(int).eq(1)
    terminal = loans["loanStatus"].isin(terminal_statuses)

    # Step 3: return contradictory unfunded outcomes for quarantine and reporting.
    return loans.loc[terminal & ~funded].copy()


def build_data_quality_report(metrics: dict, cutoff: dict) -> dict:
    """Build the successful-run quality report from measured validation evidence."""
    distribution = metrics["target_distribution"]
    target_classes = sum(
        int(distribution.get(name, 0) > 0)
        for name in ("negative_count", "positive_count")
    )
    checks = [
        {
            "name": "resolved_population_has_both_classes",
            "passed": target_classes == 2,
            "observed": target_classes,
        },
        {
            "name": "non_null_loan_ids_are_unique",
            "passed": cutoff["duplicate_non_null_loan_ids"] == 0,
            "observed_duplicates": cutoff["duplicate_non_null_loan_ids"],
        },
        {
            "name": "non_null_clarity_ids_are_unique",
            "passed": cutoff["duplicate_non_null_clarity_ids"] == 0,
            "observed_duplicates": cutoff["duplicate_non_null_clarity_ids"],
        },
    ]
    return {
        "passed": all(check["passed"] for check in checks),
        "checks": checks,
        "target_classes": target_classes,
        "resolved_rows": distribution["rows"],
        "null_loan_ids": cutoff["loan_rows_with_null_id"],
        "duplicate_non_null_loan_ids": cutoff["duplicate_non_null_loan_ids"],
        "duplicate_non_null_clarity_ids": cutoff[
            "duplicate_non_null_clarity_ids"
        ],
        "clarity_match_rate": cutoff["clarity_match_rate"],
        "outcome_maturity": {
            "method": "terminal-status proxy",
            "limitation": "status-event timestamps are unavailable",
        },
    }
