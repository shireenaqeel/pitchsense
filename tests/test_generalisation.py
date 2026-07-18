"""Unit tests for the leave-one-tournament-out helpers (no network, no fit)."""

import pandas as pd

from pitchsense.generalisation import (
    TOURNAMENT_NAMES,
    holdout_split,
    label_tournaments,
    summarise,
    tournaments_in_order,
)


def test_tournaments_in_order_matches_config():
    names = tournaments_in_order()
    assert "World Cup 2018" in names
    assert len(names) == len(TOURNAMENT_NAMES)


def test_label_tournaments_maps_and_drops_unmapped():
    data = pd.DataFrame({"match_id": [1, 2, 3], "value": [10, 20, 30]})
    labels = {1: "World Cup 2018", 2: "Euro 2020"}  # match 3 unmapped
    out = label_tournaments(data, labels)
    assert len(out) == 2
    assert set(out["tournament"]) == {"World Cup 2018", "Euro 2020"}
    assert 3 not in out["match_id"].tolist()


def test_holdout_split_separates_the_held_tournament():
    data = pd.DataFrame({
        "tournament": ["A", "A", "B", "C"],
        "v": [1, 2, 3, 4],
    })
    train, test = holdout_split(data, "A")
    assert set(test["tournament"]) == {"A"}
    assert "A" not in set(train["tournament"])
    assert len(train) == 2 and len(test) == 2


def test_summarise_averages_across_tournaments():
    per_model = {
        "logistic_regression": {
            "A": {"roc_auc": 0.80, "log_loss": 0.25},
            "B": {"roc_auc": 0.70, "log_loss": 0.35},
        }
    }
    summary = summarise(per_model, ["A", "B"])
    assert summary["logistic_regression"]["mean_roc_auc"] == 0.75
    assert summary["logistic_regression"]["mean_log_loss"] == 0.30
    # the per-tournament detail is preserved
    assert summary["logistic_regression"]["per_tournament"]["A"]["roc_auc"] == 0.80
