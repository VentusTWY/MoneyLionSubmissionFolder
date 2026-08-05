import pandas as pd
import pytest

from src.labels import (
    create_resolved_target,
    find_unfunded_terminal_outcomes,
    target_distribution,
)


CONFIG = {
    "label": {
        "target_name": "bad",
        "positive_statuses": ["Collection"],
        "negative_statuses": ["Paid"],
    }
}


def test_resolved_target_keeps_only_terminal_funded_loans():
    loans = pd.DataFrame({
        "loanStatus": ["Paid", "Collection", "Active", "Collection"],
        "isFunded": [1, 1, 1, 0],
    })
    with pytest.warns(UserWarning, match="Quarantining 1 unfunded"):
        result = create_resolved_target(loans, CONFIG)
    assert result["bad"].tolist() == [0, 1]
    assert target_distribution(result, "bad")["positive_rate"] == 0.5


def test_unfunded_terminal_outcomes_are_reported_for_quarantine():
    loans = pd.DataFrame({
        "loanId": ["funded", "inconsistent", "active"],
        "loanStatus": ["Collection", "Collection", "Active"],
        "isFunded": [1, 0, 0],
    })

    quarantined = find_unfunded_terminal_outcomes(loans, CONFIG)

    assert quarantined["loanId"].tolist() == ["inconsistent"]


def test_label_sets_must_not_overlap():
    config = {"label": {"target_name": "bad", "positive_statuses": ["X"], "negative_statuses": ["X"]}}
    with pytest.raises(ValueError, match="overlap"):
        create_resolved_target(pd.DataFrame({"loanStatus": ["X"], "isFunded": [1]}), config)
