"""End-to-end temporal LightGBM baseline."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

import joblib
import lightgbm as lgb
import pandas as pd
import yaml

from src.data import join_clarity, load_training_inputs
from src.evaluate import evaluate_predictions
from src.features import build_features, feature_schema
from src.labels import (
    create_resolved_target,
    find_unfunded_terminal_outcomes,
    target_distribution,
)


def load_config(path: str | Path) -> dict:
    with Path(path).open(encoding="utf-8") as handle:
        config = yaml.safe_load(handle)
    if not isinstance(config, dict):
        raise ValueError("Configuration must be a YAML mapping")
    return config


def temporal_split(
    frame: pd.DataFrame,
    validation_fraction: float,
    test_fraction: float,
):
    """Return chronological train, validation, and untouched test periods."""
    if validation_fraction <= 0 or test_fraction <= 0:
        raise ValueError("validation_fraction and test_fraction must be positive")
    if validation_fraction + test_fraction >= 1:
        raise ValueError("validation_fraction + test_fraction must be less than 1")
    ordered = frame.assign(
        _application_ts=pd.to_datetime(
            frame["applicationDate"], format="mixed", errors="raise", utc=True
        )
    ).sort_values(["_application_ts", "loanId"])
    train_end = int(len(ordered) * (1 - validation_fraction - test_fraction))
    validation_end = int(len(ordered) * (1 - test_fraction))
    if train_end <= 0 or validation_end <= train_end or validation_end >= len(ordered):
        raise ValueError("split fractions create an empty train, validation, or test set")
    return (
        ordered.iloc[:train_end].drop(columns="_application_ts"),
        ordered.iloc[train_end:validation_end].drop(columns="_application_ts"),
        ordered.iloc[validation_end:].drop(columns="_application_ts"),
    )


def customer_overlap(left: pd.DataFrame, right: pd.DataFrame) -> int:
    """Count customers represented in both temporal periods."""
    left_customers = set(left["anon_ssn"].dropna())
    right_customers = set(right["anon_ssn"].dropna())
    return len(left_customers & right_customers)


def run(config_path: str | Path) -> dict:
    # Step 1: load the experiment configuration and prepare its output directory.
    config = load_config(config_path)
    output = Path(config["output_dir"])
    output.mkdir(parents=True, exist_ok=True)

    # Step 2: load and validate the application-time loan and Clarity inputs.
    loans, clarity = load_training_inputs(config)

    # Step 3: quarantine contradictory outcomes and construct the resolved target.
    quarantined_outcomes = find_unfunded_terminal_outcomes(loans, config)
    resolved = create_resolved_target(loans, config)
    labelled_distribution = target_distribution(resolved, config["label"]["target_name"])

    # Step 4: enrich resolved loans with the optional application-time Clarity report.
    joined = join_clarity(resolved, clarity)

    # Step 5: create chronological train, validation, and untouched test periods.
    train_frame, valid_frame, test_frame = temporal_split(
        joined,
        config["split"]["validation_fraction"],
        config["split"]["test_fraction"],
    )

    # Step 6: build identical feature matrices under the shared feature contract.
    target = config["label"]["target_name"]
    feature_contract = config.get("feature_contract", {})
    X_train, y_train = build_features(train_frame, target, feature_contract)
    X_valid, y_valid = build_features(valid_frame, target, feature_contract)
    X_test, y_test = build_features(test_frame, target, feature_contract)
    X_valid = X_valid[X_train.columns]
    X_test = X_test[X_train.columns]

    # Step 7: fit the LightGBM challenger with validation-based early stopping.
    model = lgb.LGBMClassifier(**config["model"])
    model.fit(
        X_train, y_train,
        eval_set=[(X_valid, y_valid)],
        callbacks=[lgb.early_stopping(config["training"]["early_stopping_rounds"], verbose=False)],
    )

    # Step 8: evaluate once on the untouched test set and attach split metadata.
    probabilities = model.predict_proba(X_test)[:, 1]
    metrics = evaluate_predictions(
        y_test, probabilities, config["evaluation"]["threshold"], output
    )
    metrics["evaluation_split"] = "test"
    metrics["target_distribution"] = labelled_distribution
    metrics["train_rows"] = int(len(train_frame))
    metrics["validation_rows"] = int(len(valid_frame))
    metrics["test_rows"] = int(len(test_frame))

    # Step 9: persist the model, ordered features, schema, and evaluation metrics.
    joblib.dump(model, output / "model.joblib")
    (output / "features.json").write_text(json.dumps(list(X_train.columns), indent=2) + "\n")
    (output / "feature_schema.json").write_text(
        json.dumps(feature_schema(X_train), indent=2) + "\n", encoding="utf-8"
    )
    (output / "metrics.json").write_text(json.dumps(metrics, indent=2) + "\n")

    # Step 10: record data cutoffs and lineage, then return the completed metrics.
    metadata = {
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "train_application_min": str(train_frame["applicationDate"].min()),
        "train_application_max": str(train_frame["applicationDate"].max()),
        "validation_application_min": str(valid_frame["applicationDate"].min()),
        "validation_application_max": str(valid_frame["applicationDate"].max()),
        "test_application_min": str(test_frame["applicationDate"].min()),
        "test_application_max": str(test_frame["applicationDate"].max()),
        "loan_rows_with_null_id": int(loans["loanId"].isna().sum()),
        "unfunded_terminal_outcomes_quarantined": int(len(quarantined_outcomes)),
        "clarity_match_rate": float(joined["_clarity_join"].eq("both").mean()),
        "train_validation_customer_overlap": customer_overlap(train_frame, valid_frame),
        "train_test_customer_overlap": customer_overlap(train_frame, test_frame),
        "validation_test_customer_overlap": customer_overlap(valid_frame, test_frame),
        "feature_count": int(len(X_train.columns)),
        "feature_contract": feature_contract,
        "best_iteration": int(model.best_iteration_),
        "config": str(config_path),
    }
    (output / "data_cutoff.json").write_text(json.dumps(metadata, indent=2) + "\n")
    print(json.dumps(metrics, indent=2))
    return metrics


def main() -> None:
    # Step 1: parse the requested training configuration.
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default="configs/baseline.yaml")
    args = parser.parse_args()

    # Step 2: execute the complete training workflow.
    run(args.config)


if __name__ == "__main__":
    main()
