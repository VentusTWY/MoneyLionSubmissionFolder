import json
from pathlib import Path

import joblib
import pandas as pd
from sklearn.linear_model import LogisticRegression

from src.mlops import (
    LocalRegistry,
    RegistryBackendNotInstalled,
    create_registry,
    evaluate_gates,
    sha256,
    write_json,
)
from src.serving import LoanRiskPredictor, create_app


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


def test_api_health_prediction_and_batch_limit(tmp_path):
    from fastapi.testclient import TestClient

    registry = LocalRegistry(tmp_path / "registry")
    registry.register(make_bundle(tmp_path, "v1"), "v1")
    registry.promote("v1")
    client = TestClient(create_app(registry.root, batch_limit=1))

    assert client.get("/health/ready").json()["model_version"] == "v1"
    response = client.post(
        "/v1/predict", json={"applicationDate": "2020-01-01", "loanAmount": 5.0}
    )
    assert response.status_code == 200
    assert response.json()["model_version"] == "v1"
    item = {"applicationDate": "2020-01-01", "loanAmount": 5.0}
    assert client.post("/v1/predict/batch", json=[item, item]).status_code == 413
    assert "ml_prediction_requests_total" in client.get("/metrics").text
