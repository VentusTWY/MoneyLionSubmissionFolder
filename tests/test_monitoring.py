import pandas as pd

from src.monitoring import delayed_performance_report, drift_report


def test_drift_report_detects_shift():
    report = drift_report(
        pd.DataFrame({"score": list(range(100))}),
        pd.DataFrame({"score": list(range(100, 200))}),
    )
    assert report["numeric_feature_psi"]["score"] > 0.2


def test_delayed_performance_is_version_specific():
    rows = pd.DataFrame({
        "model_version": ["v1", "v1", "v2", "v2"],
        "adverse_probability": [0.1, 0.9, 0.2, 0.8],
        "adverse_outcome": [0, 1, 0, 1],
    })
    report = delayed_performance_report(rows)
    assert set(report["models"]) == {"v1", "v2"}
    assert report["models"]["v1"]["roc_auc"] == 1.0
