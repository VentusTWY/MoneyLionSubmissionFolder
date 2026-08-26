from pathlib import Path

from src.training.data_quality import build_data_quality_report
from src.training.pipeline import training_requirements_path


def test_pipeline_resolves_training_requirements_from_repository_root():
    requirements = training_requirements_path()

    assert requirements == Path(__file__).resolve().parents[1] / "requirements.txt"
    assert requirements.is_file()


def test_data_quality_report_is_derived_from_observed_values():
    metrics = {
        "target_distribution": {
            "rows": 20,
            "negative_count": 12,
            "positive_count": 8,
        }
    }
    cutoff = {
        "loan_rows_with_null_id": 3,
        "duplicate_non_null_loan_ids": 0,
        "duplicate_non_null_clarity_ids": 0,
        "clarity_match_rate": 0.75,
    }

    report = build_data_quality_report(metrics, cutoff)

    assert report["passed"] is True
    assert report["target_classes"] == 2
    assert report["resolved_rows"] == 20
    assert report["null_loan_ids"] == 3
    assert all(check["passed"] for check in report["checks"])


def test_data_quality_report_fails_from_observed_class_or_duplicate_evidence():
    metrics = {
        "target_distribution": {
            "rows": 12,
            "negative_count": 12,
            "positive_count": 0,
        }
    }
    cutoff = {
        "loan_rows_with_null_id": 0,
        "duplicate_non_null_loan_ids": 1,
        "duplicate_non_null_clarity_ids": 0,
        "clarity_match_rate": 1.0,
    }

    report = build_data_quality_report(metrics, cutoff)

    assert report["passed"] is False
    assert report["target_classes"] == 1
    assert report["duplicate_non_null_loan_ids"] == 1
