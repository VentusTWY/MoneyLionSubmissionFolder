import json
import logging
import sys
from importlib import metadata
from pathlib import Path

import joblib
import pandas as pd
from sklearn.linear_model import LogisticRegression

from src.mlops import (
    LocalRegistry,
    RegistryBackendNotInstalled,
    create_registry,
    evaluate_gates,
    runtime_provenance,
    sha256,
    write_json,
)
from src.serving.predictor import LoanRiskPredictor, create_app


def make_bundle(root: Path, version: str) -> Path:
    bundle = root / f"bundle-{version}"
    bundle.mkdir()
    model = LogisticRegression().fit(pd.DataFrame({"loanAmount": [1.0, 10.0]}), [0, 1])
    joblib.dump(model, bundle / "model.joblib")
    schema = {
        "features": [{"name": "loanAmount", "kind": "number", "nullable": False}]
    }
    write_json(bundle / "feature_schema.json", schema)
    write_json(bundle / "metrics.json", {"roc_auc": 0.8, "log_loss": 0.5})
    manifest = {
        "version": version,
        "decision_threshold": 0.5,
        "feature_contract": {"name": "pre_pricing_v1", "exclude": []},
        "checksums": {
            name: sha256(bundle / name)
            for name in ["model.joblib", "feature_schema.json", "metrics.json"]
        },
    }
    write_json(bundle / "manifest.json", manifest)
    return bundle


def test_rejected_gate_does_not_pass():
    result = evaluate_gates(
        {"test_rows": 100, "roc_auc": 0.55, "log_loss": 0.9},
        None,
        {"minimum_test_rows": 1000, "minimum_roc_auc": 0.65, "maximum_log_loss": 0.75},
        {"target_classes": 2},
    )
    assert result["passed"] is False


def test_champion_relative_gate_requires_matching_evaluation_fingerprint():
    config = {
        "minimum_test_rows": 100,
        "minimum_roc_auc": 0.65,
        "maximum_log_loss": 0.75,
        "roc_auc_regression_tolerance": 0.01,
    }
    challenger = {
        "test_rows": 1000,
        "roc_auc": 0.79,
        "log_loss": 0.5,
        "evaluation_fingerprint": "same-rows",
    }
    quality = {"target_classes": 2}

    comparable = evaluate_gates(
        challenger,
        {"roc_auc": 0.80, "evaluation_fingerprint": "same-rows"},
        config,
        quality,
    )
    different = evaluate_gates(
        challenger,
        {"roc_auc": 0.99, "evaluation_fingerprint": "different-rows"},
        config,
        quality,
    )

    comparable_by_name = {gate["name"]: gate for gate in comparable["gates"]}
    different_by_name = {gate["name"]: gate for gate in different["gates"]}
    assert comparable_by_name["champion_evaluation_comparability"]["applied"] is True
    assert comparable_by_name["champion_roc_auc_tolerance"]["passed"] is True
    assert different_by_name["champion_evaluation_comparability"]["applied"] is False
    assert different_by_name["champion_evaluation_comparability"]["passed"] is None
    assert "champion_roc_auc_tolerance" not in different_by_name
    assert different["passed"] is True


def test_runtime_provenance_records_actual_runtime_and_requirements(tmp_path):
    requirements = tmp_path / "requirements.txt"
    requirements.write_text("joblib==1.5.1\n", encoding="utf-8")

    result = runtime_provenance(requirements, dependencies=("joblib",))

    assert result == {
        "python_version": sys.version.split()[0],
        "dependencies": {"joblib": metadata.version("joblib")},
        "requirements_file": "requirements.txt",
        "requirements_sha256": sha256(requirements),
    }


def test_registry_factory_supports_paths_and_file_uris(tmp_path):
    from_path = create_registry(tmp_path / "path-registry")
    from_uri = create_registry(f"file://{tmp_path}/uri-registry")

    assert isinstance(from_path, LocalRegistry)
    assert from_path.root == tmp_path / "path-registry"
    assert isinstance(from_uri, LocalRegistry)
    assert from_uri.root == tmp_path / "uri-registry"


def test_s3_registry_is_an_explicit_production_extension():
    try:
        create_registry("s3://loan-risk-models/registry")
    except RegistryBackendNotInstalled as exc:
        message = str(exc)
        assert "S3" in message
        assert "DynamoDB" in message
    else:
        raise AssertionError("Expected the uninstalled production adapter to fail clearly")


def test_registry_promotion_predict_and_rollback(tmp_path):
    registry = LocalRegistry(tmp_path / "registry")
    registry.register(make_bundle(tmp_path, "v1"), "v1")
    registry.promote("v1")
    registry.register(make_bundle(tmp_path, "v2"), "v2")
    registry.promote("v2")

    predictor = LoanRiskPredictor.from_registry(registry.root)
    result = predictor.predict({"applicationDate": "2020-01-01", "loanAmount": 5.0})
    assert result["model_version"] == "v2"

    registry.rollback()
    assert registry.champion()["version"] == "v1"


def test_failed_smoke_restores_champion(tmp_path):
    registry = LocalRegistry(tmp_path / "registry")
    registry.register(make_bundle(tmp_path, "v1"), "v1")
    registry.promote("v1")
    registry.register(make_bundle(tmp_path, "v2"), "v2")
    try:
        registry.promote("v2", smoke_test=lambda: (_ for _ in ()).throw(RuntimeError("bad")))
    except RuntimeError:
        pass
    assert registry.champion()["version"] == "v1"


def test_rejected_candidate_never_changes_champion(tmp_path):
    registry = LocalRegistry(tmp_path / "registry")
    registry.register(make_bundle(tmp_path, "v1"), "v1")
    registry.promote("v1")
    registry.register(make_bundle(tmp_path, "v2"), "v2")
    gates = evaluate_gates(
        {"test_rows": 10, "roc_auc": 0.5, "log_loss": 0.9},
        None,
        {"minimum_test_rows": 100, "minimum_roc_auc": 0.65, "maximum_log_loss": 0.75},
        {"target_classes": 2},
    )

    if gates["passed"]:
        registry.promote("v2")

    assert registry.champion()["version"] == "v1"


def test_checksum_mismatch_fails_readiness(tmp_path):
    registry = LocalRegistry(tmp_path / "registry")
    destination = registry.register(make_bundle(tmp_path, "v1"), "v1")
    registry.promote("v1")
    (destination / "metrics.json").write_text("{}")
    try:
        LoanRiskPredictor.from_registry(registry.root)
    except ValueError as exc:
        assert "checksum" in str(exc)
    else:
        raise AssertionError("Expected corrupt bundle to fail")


def test_api_health_prediction_batch_errors_and_safe_logs(tmp_path, caplog):
    from fastapi.testclient import TestClient

    registry = LocalRegistry(tmp_path / "registry")
    registry.register(make_bundle(tmp_path, "v1"), "v1")
    registry.promote("v1")
    client = TestClient(create_app(registry.root, batch_limit=2))

    assert client.get("/health/ready").json()["model_version"] == "v1"
    payload = {
        "applicationDate": "2020-01-01",
        "loanAmount": 5.0,
        "anon_ssn": "must-not-appear-in-logs",
    }
    with caplog.at_level(logging.INFO, logger="loan_risk.serving"):
        response = client.post("/v1/predict", json=payload)
    assert response.status_code == 200
    assert response.json()["model_version"] == "v1"
    assert response.json()["request_id"] == response.headers["X-Request-ID"]
    event = json.loads(caplog.records[-1].getMessage())
    assert event["request_id"] == response.json()["request_id"]
    assert event["decision"] == response.json()["decision"]
    assert event["timestamp_utc"].endswith("+00:00")
    assert "must-not-appear-in-logs" not in caplog.text
    assert "anon_ssn" not in caplog.text

    item = {"applicationDate": "2020-01-01", "loanAmount": 5.0}
    batch = client.post("/v1/predict/batch", json=[item, item])
    assert batch.status_code == 200
    assert {result["request_id"] for result in batch.json()} == {
        batch.headers["X-Request-ID"]
    }
    too_large = client.post("/v1/predict/batch", json=[item, item, item])
    assert too_large.status_code == 413
    assert too_large.json()["request_id"] == too_large.headers["X-Request-ID"]

    missing_feature = client.post(
        "/v1/predict", json={"applicationDate": "2020-01-01"}
    )
    assert missing_feature.status_code == 422
    assert missing_feature.json()["request_id"] == missing_feature.headers["X-Request-ID"]

    invalid_date = client.post(
        "/v1/predict", json={"applicationDate": "not-a-date", "loanAmount": 5.0}
    )
    assert invalid_date.status_code == 422
    assert invalid_date.json()["request_id"] == invalid_date.headers["X-Request-ID"]

    openapi = client.get("/openapi.json").json()
    schemas = openapi["components"]["schemas"]
    assert "PredictionResponse" in schemas
    assert "ModelInfoResponse" in schemas
    assert "ml_prediction_requests_total" in client.get("/metrics").text


def test_admin_model_operations_require_a_key_and_reload_the_predictor(tmp_path):
    from fastapi.testclient import TestClient

    registry = LocalRegistry(tmp_path / "registry")
    registry.register(make_bundle(tmp_path, "v1"), "v1")
    registry.promote("v1")
    registry.register(make_bundle(tmp_path, "v2"), "v2")
    client = TestClient(create_app(registry.root, admin_api_key="test-admin-key"))
    change = {"actor": "Model Risk", "reason": "Drift investigation approved this change"}

    assert client.get("/v1/admin/models").status_code == 403
    assert client.get("/v1/admin/models", headers={"X-Admin-API-Key": "wrong"}).status_code == 403

    listed = client.get("/v1/admin/models", headers={"X-Admin-API-Key": "test-admin-key"})
    assert listed.status_code == 200
    assert {model["version"] for model in listed.json()["models"]} == {"v1", "v2"}

    promoted = client.post(
        "/v1/admin/models/v2/promote",
        headers={"X-Admin-API-Key": "test-admin-key"},
        json=change,
    )
    assert promoted.status_code == 200
    assert client.get("/health/ready").json()["model_version"] == "v2"
    assert registry.champion()["actor"] == "Model Risk"
    assert registry.champion()["reason"] == change["reason"]

    rolled_back = client.post(
        "/v1/admin/models/rollback",
        headers={"X-Admin-API-Key": "test-admin-key"},
        json=change,
    )
    assert rolled_back.status_code == 200
    assert client.get("/health/ready").json()["model_version"] == "v1"
