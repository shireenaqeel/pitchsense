"""Unit tests for player behavioural feature aggregation (no network)."""

import numpy as np
import pandas as pd

from pitchsense.players import (
    PLAYER_FEATURES,
    combine_aggregates,
    finalize_features,
    player_raw_aggregates,
    position_group,
)


def _ev(pid, type_, x, y, angle=None, length=None, cross=None,
        player="P", position="Center Back"):
    return {
        "player_id": pid,
        "player": player,
        "position": position,
        "type": type_,
        "location": [x, y],
        "pass_angle": angle,
        "pass_length": length,
        "pass_cross": cross,
    }


def test_position_group_mapping():
    assert position_group("Goalkeeper") == "Goalkeeper"
    assert position_group("Right Back") == "Full-back"
    assert position_group("Left Wing Back") == "Full-back"
    assert position_group("Center Back") == "Centre-back"
    assert position_group("Left Center Back") == "Centre-back"
    assert position_group("Center Defensive Midfield") == "Defensive mid"
    assert position_group("Center Attacking Midfield") == "Attacking mid"
    assert position_group("Center Midfield") == "Central mid"
    assert position_group("Right Wing") == "Winger"
    assert position_group("Center Forward") == "Forward"
    assert position_group(None) == "Unknown"


def _one_player_match():
    rows = [
        _ev(1, "Pass", 30, 20, angle=0.0, length=10.0),        # forward pass
        _ev(1, "Pass", 40, 60, angle=np.pi, length=25.0, cross=True),  # backward cross
        _ev(1, "Carry", 50, 40),
        _ev(1, "Shot", 100, 40),
        _ev(1, "Pressure", 20, 40),
    ]
    return pd.DataFrame(rows)


def test_raw_aggregates_counts():
    raw = player_raw_aggregates(_one_player_match())
    assert len(raw) == 1
    r = raw.iloc[0]
    assert r["n_events"] == 5
    assert r["n_passes"] == 2
    assert r["n_fwd"] == 1          # only the angle-0 pass is forward
    assert r["n_cross"] == 1
    assert r["n_carry"] == 1
    assert r["n_shot"] == 1
    assert r["n_def"] == 1          # the Pressure event
    assert r["sum_pass_len"] == 35.0


def test_finalized_shares_and_position():
    raw = player_raw_aggregates(_one_player_match())
    pooled = combine_aggregates(raw)
    feats = finalize_features(pooled, min_events=1)
    assert len(feats) == 1
    f = feats.iloc[0]
    for key in PLAYER_FEATURES:
        assert key in feats.columns
    assert f["pass_share"] == 2 / 5
    assert f["shot_share"] == 1 / 5
    assert f["defensive_share"] == 1 / 5
    assert f["forward_pass_ratio"] == 0.5
    assert f["avg_pass_length"] == 17.5
    assert f["cross_share"] == 0.5
    assert f["avg_x"] == (30 + 40 + 50 + 100 + 20) / 5
    assert f["position_group"] == "Centre-back"


def test_min_events_filter():
    raw = player_raw_aggregates(_one_player_match())
    pooled = combine_aggregates(raw)
    assert finalize_features(pooled, min_events=100).empty


def test_combine_pools_across_matches_and_picks_main_position():
    # Same player in two matches: counts add; label position is the busier match.
    m1 = player_raw_aggregates(pd.DataFrame([
        _ev(1, "Pass", 30, 40, angle=0.0, length=10.0, position="Center Back"),
        _ev(1, "Carry", 35, 40, position="Center Back"),
    ]))
    m2 = player_raw_aggregates(pd.DataFrame([
        _ev(1, "Pass", 80, 40, angle=0.0, length=10.0, position="Right Wing"),
        _ev(1, "Shot", 100, 40, position="Right Wing"),
        _ev(1, "Dribble", 90, 40, position="Right Wing"),
        _ev(1, "Pass", 85, 30, angle=0.0, length=8.0, position="Right Wing"),
    ]))
    pooled = combine_aggregates(pd.concat([m1, m2], ignore_index=True))
    assert len(pooled) == 1
    r = pooled.iloc[0]
    assert r["n_events"] == 6
    assert r["position"] == "Right Wing"   # match 2 had more events
    assert r["n_passes"] == 3


def test_missing_location_is_ignored_in_position_average():
    events = pd.DataFrame([
        _ev(1, "Pass", 30, 40, angle=0.0, length=10.0),
        {**_ev(1, "Pass", 0, 0, angle=0.0, length=10.0), "location": None},
    ])
    raw = player_raw_aggregates(events)
    r = raw.iloc[0]
    assert r["n_events"] == 2
    assert r["n_loc"] == 1        # only one event had a location
    assert r["sum_x"] == 30.0
