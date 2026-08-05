"""Data loading, schema validation, and joins."""

from __future__ import annotations

from pathlib import Path
from typing import Iterable

import pandas as pd


LOAN_REQUIRED = {
    "loanId", "anon_ssn", "applicationDate", "loanStatus", "isFunded",
    "clarityFraudId", "payFrequency", "nPaidOff", "loanAmount", "state",
    "leadType", "leadCost",
}
PAYMENT_REQUIRED = {"loanId", "paymentDate", "paymentStatus", "paymentAmount"}
CLARITY_REQUIRED = {"underwritingid"}


def _read(path: str | Path, name: str, required: Iterable[str]) -> pd.DataFrame:
    path = Path(path)
    if not path.is_file():
        raise FileNotFoundError(f"{name} parquet not found: {path}")
    frame = pd.read_parquet(path)
    missing = sorted(set(required) - set(frame.columns))
    if missing:
        raise ValueError(f"{name} is missing required columns: {missing}")
    return frame


def load_training_inputs(config: dict) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Load only data available to the application-time training pipeline."""
    paths = config["data"]
    loans = _read(paths["loans"], "loans", LOAN_REQUIRED)
    clarity = _read(paths["clarity"], "clarity", CLARITY_REQUIRED)
    # Null IDs occur on incomplete, non-funded applications and are excluded by
    # the resolved-loan population. Non-null IDs must still be unique.
    non_null_ids = loans["loanId"].dropna()
    if non_null_ids.duplicated().any():
        raise ValueError("Non-null loan.loanId values must be unique")
    return loans, clarity


def load_payments(config: dict) -> pd.DataFrame:
    """Load outcome-time payments for a separate label-audit workflow."""
    return _read(config["data"]["payments"], "payments", PAYMENT_REQUIRED)


def join_clarity(loans: pd.DataFrame, clarity: pd.DataFrame) -> pd.DataFrame:
    """Left join the application-time underwriting report, enforcing many-to-one."""
    clarity = clarity.drop(columns=["__index_level_0__"], errors="ignore")
    duplicated = clarity["underwritingid"].dropna().duplicated(keep=False)
    if duplicated.any():
        raise ValueError(
            f"clarity.underwritingid is not unique ({duplicated.sum()} duplicate rows)"
        )
    joined = loans.merge(
        clarity,
        how="left",
        left_on="clarityFraudId",
        right_on="underwritingid",
        validate="many_to_one",
        indicator="_clarity_join",
    )
    joined["has_clarity_report"] = joined["_clarity_join"].eq("both")
    return joined
