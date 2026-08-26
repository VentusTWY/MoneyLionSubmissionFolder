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
    # Step 1: resolve the configured path and fail clearly when the file is absent.
    path = Path(path)
    if not path.is_file():
        raise FileNotFoundError(f"{name} parquet not found: {path}")

    # Step 2: load the Parquet snapshot into a dataframe.
    frame = pd.read_parquet(path)

    # Step 3: enforce the minimum schema before downstream processing begins.
    missing = sorted(set(required) - set(frame.columns))
    if missing:
        raise ValueError(f"{name} is missing required columns: {missing}")
    return frame


def load_training_inputs(config: dict) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Load only data available to the application-time training pipeline."""
    # Step 1: resolve and validate the configured loan and Clarity snapshots.
    paths = config["data"]
    loans = _read(paths["loans"], "loans", LOAN_REQUIRED)
    clarity = _read(paths["clarity"], "clarity", CLARITY_REQUIRED)

    # Step 2: allow incomplete null IDs but reject duplicated usable loan IDs.
    # Null IDs occur on incomplete, non-funded applications and are excluded by
    # the resolved-loan population. Non-null IDs must still be unique.
    non_null_ids = loans["loanId"].dropna()
    if non_null_ids.duplicated().any():
        raise ValueError("Non-null loan.loanId values must be unique")

    # Step 3: return only application-time inputs; payments remain outcome-time data.
    return loans, clarity


def load_payments(config: dict) -> pd.DataFrame:
    """Load outcome-time payments for a separate label-audit workflow."""
    return _read(config["data"]["payments"], "payments", PAYMENT_REQUIRED)


def join_clarity(loans: pd.DataFrame, clarity: pd.DataFrame) -> pd.DataFrame:
    """Left join the application-time underwriting report, enforcing many-to-one."""
    # Step 1: remove the exported dataframe index when it is present.
    clarity = clarity.drop(columns=["__index_level_0__"], errors="ignore")

    # Step 2: prove the Clarity join key is unique before merging.
    duplicated = clarity["underwritingid"].dropna().duplicated(keep=False)
    if duplicated.any():
        raise ValueError(
            f"clarity.underwritingid is not unique ({duplicated.sum()} duplicate rows)"
        )

    # Step 3: preserve every loan while enforcing a many-to-one report relationship.
    joined = loans.merge(
        clarity,
        how="left",
        left_on="clarityFraudId",
        right_on="underwritingid",
        validate="many_to_one",
        indicator="_clarity_join",
    )

    # Step 4: expose report availability as a safe application-time feature.
    joined["has_clarity_report"] = joined["_clarity_join"].eq("both")
    return joined
