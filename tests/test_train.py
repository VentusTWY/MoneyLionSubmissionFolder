import pandas as pd

from src.train import customer_overlap, temporal_split


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
