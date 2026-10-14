"""Unit tests for the effectiveness and discipline scoring (no network, no models)."""

import numpy as np
import pandas as pd

from pitchsense.ratings import (
    finishing_table,
    mask_small_samples,
    peer_percentiles,
    score_players,
)


def test_finishing_is_goals_above_expected_per_shot():
    shots = pd.DataFrame({"player": ["A", "A", "A", "B"], "is_goal": [1, 0, 1, 0]})
    out = finishing_table(shots, np.array([0.5, 0.1, 0.4, 0.2])).set_index("player")
    assert out.loc["A", "n_np_shots"] == 3
    assert out.loc["A", "np_goals"] == 2
    assert np.isclose(out.loc["A", "finishing"], (2 - 1.0) / 3)
    assert np.isclose(out.loc["B", "finishing"], -0.2)


def test_small_samples_are_masked():
    df = pd.DataFrame({"tackle_win": [0.9, 0.5], "n_tackle": [3, 20]})
    out = mask_small_samples(df, {"tackle_win": ("n_tackle", 10)})
    assert np.isnan(out.loc[0, "tackle_win"])
    assert out.loc[1, "tackle_win"] == 0.5


def test_percentiles_are_within_role():
    df = pd.DataFrame({"role": ["CB", "CB", "W", "W"],
                       "pass_completion": [0.90, 0.80, 0.70, 0.60]})
    pct = peer_percentiles(df, ["pass_completion"])["pass_completion"]
    # The best winger tops their peers despite passing worse than both centre-backs.
    assert pct.tolist() == [100.0, 50.0, 100.0, 50.0]


def _frame():
    return pd.DataFrame({
        "role": ["CB"] * 3,
        "pass_completion": [0.9, 0.8, 0.7],
        "dribble_success": [np.nan, np.nan, np.nan],
        "tackle_win": [0.7, 0.6, 0.5],
        "finishing": [np.nan, 0.1, -0.1],
        "fouls_per100": [0.5, 1.0, 2.0],
        "cards_per100": [0.0, 0.1, 0.3],
    })


def test_scores_skip_missing_stats_and_reward_clean_play():
    out = score_players(_frame())
    # Player 0: top on both available effectiveness stats, finishing/dribbling skipped.
    assert out.loc[0, "effectiveness"] == 100.0
    assert out.loc[0, "effectiveness_n_stats"] == 2
    # Fewest fouls and cards -> highest discipline; most -> lowest.
    assert out["discipline"].idxmax() == 0
    assert out["discipline"].idxmin() == 2
    assert out.loc[2, "fouls_per100_pct"] == 100.0
