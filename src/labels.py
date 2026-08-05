"""Resolved-loan population and adverse-outcome target."""

from __future__ import annotations

import warnings

import pandas as pd


def find_unfunded_terminal_outcomes(loans: pd.DataFrame, config: dict) -> pd.DataFrame:
    """Return terminal outcomes that contradict the funded-loan population.

    These rows are quarantined from target construction. Returning them also
    makes the anomaly available for data-quality reporting and investigation.
    """
    label = config["label"]
    terminal_statuses = set(label["positive_statuses"]) | set(label["negative_statuses"])
    funded = loans["isFunded"].fillna(0).astype(int).eq(1)
    terminal = loans["loanStatus"].isin(terminal_statuses)
    return loans.loc[terminal & ~funded].copy()


def create_resolved_target(loans: pd.DataFrame, config: dict) -> pd.DataFrame:
    """Return terminal funded loans with 1=adverse and 0=paid-off.

    Payment data is intentionally not used as a feature. It is accepted by the
    pipeline and validated because it is outcome-time information and useful for
    later label audits, but including it in predictors would leak the result.
    """
    label = config["label"]
    positive = set(label["positive_statuses"])
    negative = set(label["negative_statuses"])
    overlap = positive & negative
    if overlap:
        raise ValueError(f"Label status sets overlap: {sorted(overlap)}")

    quarantined = find_unfunded_terminal_outcomes(loans, config)
    if not quarantined.empty:
        warnings.warn(
            f"Quarantining {len(quarantined)} unfunded loans with terminal outcomes",
            UserWarning,
            stacklevel=2,
        )

    funded = loans["isFunded"].fillna(0).astype(int).eq(1)
    resolved = loans["loanStatus"].isin(positive | negative)
    result = loans.loc[funded & resolved].copy()
    result[label["target_name"]] = result["loanStatus"].isin(positive).astype("int8")
    if result.empty or result[label["target_name"]].nunique() != 2:
        raise ValueError("Resolved population must contain both target classes")
    return result


def target_distribution(frame: pd.DataFrame, target: str) -> dict:
    counts = frame[target].value_counts().sort_index()
    total = int(len(frame))
    return {
        "rows": total,
        "negative_count": int(counts.get(0, 0)),
        "positive_count": int(counts.get(1, 0)),
        "positive_rate": float(frame[target].mean()),
    }
