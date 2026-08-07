"""Train a pre-pricing logistic-regression benchmark on the baseline split."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

import joblib
import numpy as np
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, log_loss, roc_auc_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from src.data import join_clarity, load_training_inputs
from src.evaluate import evaluate_predictions
from src.features import build_features
from src.labels import create_resolved_target
from src.train import customer_overlap, load_config, temporal_split


def run(config_path: str | Path, output_dir: str | Path) -> dict:
    # Step 1: load the shared configuration and prepare benchmark outputs.
    config = load_config(config_path)
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)

    # Step 2: load inputs and construct the same resolved target as LightGBM.
    loans, clarity = load_training_inputs(config)
    resolved = create_resolved_target(loans, config)

    # Step 3: join application-time data and reuse the chronological split policy.
    joined = join_clarity(resolved, clarity)
    train_frame, valid_frame, test_frame = temporal_split(
        joined,
        config["split"]["validation_fraction"],
        config["split"]["test_fraction"],
    )

    # Step 4: build and align feature matrices under the production contract.
    target = config["label"]["target_name"]
    contract = config.get("feature_contract", {})
    X_train, y_train = build_features(train_frame, target, contract)
    X_valid, _ = build_features(valid_frame, target, contract)
    X_test, y_test = build_features(test_frame, target, contract)
    X_valid = X_valid[X_train.columns]
    X_test = X_test[X_train.columns]

    # Step 5: separate categorical and numeric columns for sklearn preprocessing.
    categorical = list(
        X_train.select_dtypes(include=["object", "string", "category"]).columns
    )
    # sklearn's imputers may attempt a common numeric dtype for pandas
    # Categoricals. Convert only the benchmark copies before one-hot encoding;
    # LightGBM continues to receive native categorical columns in src.train.
    for frame in (X_train, X_valid, X_test):
        frame[categorical] = frame[categorical].astype("object")
    numeric = [column for column in X_train.columns if column not in categorical]

    # Step 6: build imputation, scaling, and one-hot encoding transformations.
    preprocessing = ColumnTransformer(
        transformers=[
            (
                "numeric",
                Pipeline([
                    ("impute", SimpleImputer(strategy="median")),
                    ("scale", StandardScaler()),
                ]),
                numeric,
            ),
            (
                "categorical",
                Pipeline([
                    ("impute", SimpleImputer(strategy="most_frequent")),
                    ("encode", OneHotEncoder(handle_unknown="ignore")),
                ]),
                categorical,
            ),
        ]
    )

    # Step 7: fit the logistic-regression benchmark on the training period.
    model = Pipeline([
        ("preprocess", preprocessing),
        ("classifier", LogisticRegression(max_iter=2_000, solver="liblinear")),
    ])
    model.fit(X_train, y_train)

    # Step 8: evaluate logistic and constant baselines on the untouched test set.
    probabilities = model.predict_proba(X_test)[:, 1]
    metrics = evaluate_predictions(
        y_test, probabilities, config["evaluation"]["threshold"], output
    )
    metrics.update({
        "evaluation_split": "test",
        "model_type": "logistic_regression",
        "train_rows": int(len(train_frame)),
        "validation_rows": int(len(valid_frame)),
        "test_rows": int(len(test_frame)),
    })

    constant_probability = float(y_train.mean())
    constant = np.full(len(y_test), constant_probability)
    metrics["constant_predictor"] = {
        "training_positive_rate": constant_probability,
        "roc_auc": float(roc_auc_score(y_test, constant)),
        "pr_auc": float(average_precision_score(y_test, constant)),
        "log_loss": float(log_loss(y_test, constant)),
    }

    # Step 9: persist the benchmark model, feature list, and metrics.
    joblib.dump(model, output / "model.joblib")
    (output / "features.json").write_text(
        json.dumps(list(X_train.columns), indent=2) + "\n", encoding="utf-8"
    )
    (output / "metrics.json").write_text(
        json.dumps(metrics, indent=2) + "\n", encoding="utf-8"
    )

    # Step 10: record temporal lineage and customer overlap, then return metrics.
    metadata = {
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "model_type": "logistic_regression",
        "feature_contract": contract,
        "feature_count": int(len(X_train.columns)),
        "train_application_min": str(train_frame["applicationDate"].min()),
        "train_application_max": str(train_frame["applicationDate"].max()),
        "validation_application_min": str(valid_frame["applicationDate"].min()),
        "validation_application_max": str(valid_frame["applicationDate"].max()),
        "test_application_min": str(test_frame["applicationDate"].min()),
        "test_application_max": str(test_frame["applicationDate"].max()),
        "train_validation_customer_overlap": customer_overlap(train_frame, valid_frame),
        "train_test_customer_overlap": customer_overlap(train_frame, test_frame),
        "validation_test_customer_overlap": customer_overlap(valid_frame, test_frame),
        "config": str(config_path),
    }
    (output / "data_cutoff.json").write_text(
        json.dumps(metadata, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(metrics, indent=2))
    return metrics


def main() -> None:
    # Step 1: parse the shared config and benchmark output directory.
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default="configs/baseline.yaml")
    parser.add_argument("--output-dir", default="artifacts/prepricing_logistic")
    args = parser.parse_args()

    # Step 2: execute the complete benchmark workflow.
    run(args.config, args.output_dir)


if __name__ == "__main__":
    main()
