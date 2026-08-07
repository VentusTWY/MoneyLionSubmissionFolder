import pandas as pd

from src.train import customer_overlap, evaluation_fingerprint, temporal_split


def test_temporal_split_has_no_time_leakage():
    frame = pd.DataFrame({
        "loanId": ["f", "c", "a", "e", "b", "d"],
        "applicationDate": [
            "2020-06-01", "2020-03-01", "2020-01-01",
            "2020-05-01", "2020-02-01", "2020-04-01",
        ],
    })
    train, valid, test = temporal_split(frame, 0.20, 0.20)
    assert train["applicationDate"].max() < valid["applicationDate"].min()
    assert valid["applicationDate"].max() < test["applicationDate"].min()


def test_customer_overlap_counts_shared_customers():
    train = pd.DataFrame({"anon_ssn": ["a", "b", None]})
    test = pd.DataFrame({"anon_ssn": ["b", "c", None]})

    assert customer_overlap(train, test) == 1


def test_evaluation_fingerprint_is_stable_and_changes_with_rows_or_policy():
    frame = pd.DataFrame({
        "loanId": ["loan-1", "loan-2"],
        "applicationDate": ["2020-01-01", "2020-02-01"],
        "adverse_outcome": [0, 1],
    })
    label = {"target_name": "adverse_outcome", "positive_statuses": ["bad"]}
    evaluation = {"threshold": 0.5}

    first = evaluation_fingerprint(frame, "adverse_outcome", label, evaluation)
    repeated = evaluation_fingerprint(frame.copy(), "adverse_outcome", label, evaluation)
    changed_rows = evaluation_fingerprint(
        frame.iloc[::-1], "adverse_outcome", label, evaluation
    )
    changed_policy = evaluation_fingerprint(
        frame, "adverse_outcome", label, {"threshold": 0.6}
    )

    assert first == repeated
    assert first != changed_rows
    assert first != changed_policy
