import pandas as pd

from src.features import build_features, feature_schema, transform_features


def test_features_exclude_outcomes_identifiers_and_payments():
    frame = pd.DataFrame({
        "loanId": ["loan-1", "loan-2"],
        "anon_ssn": ["customer-1", "customer-2"],
        "applicationDate": ["2020-01-01", "2020-01-02"],
        "approved": [True, False],
        "isFunded": [1, 1],
        "loanStatus": ["Paid Off Loan", "Internal Collection"],
        "fpStatus": ["Checked", "Rejected"],
        "paymentStatus": ["Checked", "Rejected"],
        "paymentAmount": [100.0, 0.0],
        "has_clarity_report": [True, False],
        "loanAmount": [300.0, 400.0],
        "adverse_outcome": [0, 1],
    })

    X, y = build_features(frame, "adverse_outcome")

    forbidden = {
        "loanId", "anon_ssn", "approved", "isFunded", "loanStatus",
        "fpStatus", "paymentStatus", "paymentAmount", "adverse_outcome",
    }
    assert forbidden.isdisjoint(X.columns)
    assert "has_clarity_report" in X.columns
    assert y.tolist() == [0, 1]


def test_pre_pricing_contract_excludes_pricing_fields():
    frame = pd.DataFrame({
        "loanId": ["loan-1", "loan-2"],
        "applicationDate": ["2020-01-01", "2020-01-02"],
        "apr": [10.0, 20.0],
        "originallyScheduledPaymentAmount": [100.0, 110.0],
        "loanAmount": [300.0, 400.0],
        "adverse_outcome": [0, 1],
    })
    contract = {
        "name": "pre_pricing_v1",
        "exclude": ["apr", "originallyScheduledPaymentAmount"],
    }

    X, _ = build_features(frame, "adverse_outcome", contract)

    assert "loanAmount" in X.columns
    assert "apr" not in X.columns
    assert "originallyScheduledPaymentAmount" not in X.columns


def test_feature_contract_cannot_enable_leakage_field():
    frame = pd.DataFrame({
        "loanId": ["loan-1"],
        "applicationDate": ["2020-01-01"],
        "loanStatus": ["Paid Off Loan"],
        "adverse_outcome": [0],
    })

    try:
        build_features(
            frame,
            "adverse_outcome",
            {"include": ["loanStatus"]},
        )
    except ValueError as exc:
        assert "forbidden" in str(exc)
    else:
        raise AssertionError("Expected leakage feature contract to fail")


def test_training_and_inference_transform_have_identical_order():
    frame = pd.DataFrame({
        "applicationDate": ["2020-01-01", "2020-01-02"],
        "loanAmount": [300.0, 400.0],
        "state": ["CA", "TX"],
        "adverse_outcome": [0, 1],
    })
    training, _ = build_features(frame, "adverse_outcome")
    schema = feature_schema(training)
    inference = transform_features(
        frame.drop(columns="adverse_outcome"), feature_schema=schema
    )
    assert list(training.columns) == list(inference.columns)
    assert inference["state"].dtype == training["state"].dtype
