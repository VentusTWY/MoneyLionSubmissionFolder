"""Part 3 automated train, gate, register, promote, and smoke-test pipeline."""

from __future__ import annotations

import argparse
import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path

import yaml

from src.mlops import (
    code_revision, create_registry, evaluate_gates, runtime_provenance, sha256,
    utc_now, write_json,
)
from src.serving import LoanRiskPredictor
from src.train import load_config, run


def _run_id() -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return f"{stamp}-{uuid.uuid4().hex[:8]}"


def _smoke_request(schema: dict) -> dict:
    # Step 0: build a minimal payload that matches the feature schema for a smoke test.
    request = {"applicationDate": "2020-01-15T12:00:00Z"}
    derived = {"application_month", "application_dayofweek", "application_hour"}
    for item in schema["features"]:
        if item["name"] in derived or item.get("nullable"):
            continue
        if item["kind"] == "category":
            categories = item.get("categories", [])
            request[item["name"]] = categories[0] if categories else "unknown"
        elif item["kind"] == "bool":
            request[item["name"]] = False
        else:
            request[item["name"]] = 0
    return request


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


def execute(
    config_path: str | Path,
    promotion_path: str | Path = "configs/promotion.yaml",
    registry_uri: str | Path = "file://registry",
    runs_root: str | Path = "artifacts/runs",
) -> dict:
    # Step 1: load the training config and promotion rules.
    config_path = Path(config_path)
    config = load_config(config_path)
    promotion = load_config(promotion_path)

    # Step 2: create a unique run directory for this training execution.
    version = _run_id()
    run_dir = Path(runs_root) / version
    run_dir.mkdir(parents=True, exist_ok=False)

    # Step 3: save a copy of the run config and pass it to training.
    run_config = dict(config)
    run_config["output_dir"] = str(run_dir)
    (run_dir / "config.yaml").write_text(yaml.safe_dump(run_config, sort_keys=False))
    temporary_config = run_dir / ".training-config.yaml"
    temporary_config.write_text(yaml.safe_dump(run_config, sort_keys=False))
    try:
        metrics = run(temporary_config)
    finally:
        temporary_config.unlink(missing_ok=True)

    # Step 4: assemble data-quality and smoke-test artifacts from the run outputs.
    cutoff = json.loads((run_dir / "data_cutoff.json").read_text())
    quality = build_data_quality_report(metrics, cutoff)
    write_json(run_dir / "data_quality.json", quality)
    schema = json.loads((run_dir / "feature_schema.json").read_text())
    write_json(run_dir / "smoke_request.json", _smoke_request(schema))

    # Step 5: evaluate whether this run meets the promotion gates.
    registry = create_registry(registry_uri)
    champion = registry.champion()
    champion_metrics = None
    if champion:
        champion_metrics = json.loads((registry.champion_dir() / "metrics.json").read_text())
    gates = evaluate_gates(metrics, champion_metrics, promotion, quality)
    write_json(run_dir / "gate_results.json", gates)

    # Step 6: write the manifest and register this run in the configured registry.
    tracked = [
        "model.joblib", "features.json", "feature_schema.json", "metrics.json",
        "threshold_analysis.json", "data_cutoff.json", "data_quality.json",
        "gate_results.json", "config.yaml", "smoke_request.json",
    ]
    manifest = {
        "version": version,
        "created_at_utc": utc_now(),
        "status": "accepted" if gates["passed"] else "rejected",
        "code_revision": code_revision(),
        "runtime": runtime_provenance(
            Path(__file__).resolve().parents[1] / "requirements.txt"
        ),
        "feature_contract": config["feature_contract"],
        "target_name": config["label"]["target_name"],
        "decision_threshold": metrics["threshold"],
        "review_threshold": float(config["evaluation"]["threshold"]),
        "reject_threshold": float(config["evaluation"].get("reject_threshold", config["evaluation"]["threshold"])),
        "source_checksums": {
            name: sha256(path) for name, path in config["data"].items()
        },
        "checksums": {name: sha256(run_dir / name) for name in tracked},
    }
    write_json(run_dir / "manifest.json", manifest)
    registered = registry.register(run_dir, version)

    # Step 7: promote the model if the gates pass and the smoke test succeeds.
    if gates["passed"]:
        smoke = json.loads((registered / "smoke_request.json").read_text())
        registry.promote(
            version,
            smoke_test=lambda: LoanRiskPredictor.from_registry(registry).predict(smoke),
        )
    result = {
        "version": version,
        "status": manifest["status"],
        "promoted": gates["passed"],
        "run_dir": str(run_dir),
        "registry_dir": str(registered),
        "gates": gates,
    }
    print(json.dumps(result, indent=2))
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default="configs/baseline.yaml")
    parser.add_argument("--promotion-config", default="configs/promotion.yaml")
    parser.add_argument(
        "--registry",
        default=os.environ.get("MODEL_REGISTRY_URI", "file://registry"),
        help="Registry URI (demo: file://registry; production extension: s3://bucket/prefix)",
    )
    parser.add_argument("--runs-root", default="artifacts/runs")
    args = parser.parse_args()
    execute(args.config, args.promotion_config, args.registry, args.runs_root)


if __name__ == "__main__":
    main()
