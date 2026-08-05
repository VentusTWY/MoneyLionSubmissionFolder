"""Offline pre-label drift and delayed-outcome performance reports."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import average_precision_score, log_loss, roc_auc_score


def population_stability_index(reference, current, bins: int = 10) -> float:
    reference = pd.to_numeric(pd.Series(reference), errors="coerce").dropna()
    current = pd.to_numeric(pd.Series(current), errors="coerce").dropna()
    if reference.empty or current.empty:
        return float("nan")
    edges = np.unique(np.quantile(reference, np.linspace(0, 1, bins + 1)))
    if len(edges) < 2:
        return 0.0
    edges[0], edges[-1] = -np.inf, np.inf
    expected = np.histogram(reference, bins=edges)[0] / len(reference)
    actual = np.histogram(current, bins=edges)[0] / len(current)
    expected, actual = np.clip(expected, 1e-6, None), np.clip(actual, 1e-6, None)
    return float(np.sum((actual - expected) * np.log(actual / expected)))


def drift_report(reference: pd.DataFrame, current: pd.DataFrame) -> dict:
    common = reference.select_dtypes(include="number").columns.intersection(current.columns)
    values = {name: population_stability_index(reference[name], current[name]) for name in common}
    return {
        "reference_rows": len(reference),
        "current_rows": len(current),
        "numeric_feature_psi": values,
        "maximum_psi": max((value for value in values.values() if np.isfinite(value)), default=None),
    }


def delayed_performance_report(outcomes: pd.DataFrame) -> dict:
    required = {"model_version", "adverse_probability", "adverse_outcome"}
    missing = sorted(required - set(outcomes.columns))
    if missing:
        raise ValueError(f"Delayed outcomes are missing columns: {missing}")
    reports = {}
    for version, rows in outcomes.groupby("model_version"):
        y = rows["adverse_outcome"].astype(int)
        if y.nunique() != 2:
            reports[str(version)] = {"rows": len(rows), "status": "insufficient_classes"}
            continue
        probability = rows["adverse_probability"].astype(float)
        reports[str(version)] = {
            "rows": len(rows),
            "roc_auc": float(roc_auc_score(y, probability)),
            "pr_auc": float(average_precision_score(y, probability)),
            "log_loss": float(log_loss(y, probability)),
        }
    return {"models": reports}


def write_report(report: dict, output: str | Path) -> None:
    Path(output).write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
