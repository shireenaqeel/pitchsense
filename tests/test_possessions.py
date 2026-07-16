"""Unit tests for possession feature engineering (no network)."""

import numpy as np
import pandas as pd

from pitchsense.possessions import (
    MIN_ACTIONS,
    POSSESSION_FEATURES,
    build_possession_frame,
    possession_features,
)


def _event(idx, type_, loc, end=None, minute=0, second=0, possession=1,
           team="A", pass_end=None):
    """One event row with the fields the feature code reads."""
    return {
        "index": idx,
        "type": type_,
        "location": loc,
        "pass_end_location": pass_end if pass_end is not None else (end if type_ == "Pass" else None),
        "carry_end_location": end if type_ == "Carry" else None,
        "shot_end_location": end if type_ == "Shot" else None,
        "minute": minute,
        "second": second,
        "possession": possession,
        "possession_team": "A",
        "team": team,
        "player": "P",
        "match_id": 99,
    }


def _buildup():
    """A patient possession: several passes worked slowly up the middle."""
    return pd.DataFrame([
        _event(1, "Pass", [20.0, 40.0], end=[35.0, 30.0], second=0),
        _event(2, "Pass", [35.0, 30.0], end=[50.0, 50.0], second=5),
        _event(3, "Pass", [50.0, 50.0], end=[65.0, 40.0], second=11),
        _event(4, "Carry", [65.0, 40.0], end=[70.0, 40.0], second=15),
    ])


def test_features_present_and_typed():
    feats = possession_features(_buildup(), possession=1)
    assert feats is not None
    for key in POSSESSION_FEATURES:
        assert key in feats
    assert feats["n_actions"] == 4
    assert feats["n_passes"] == 3
    assert feats["ends_in_shot"] == 0


def test_forward_progress_and_duration():
    feats = possession_features(_buildup(), possession=1)
    assert feats["start_x"] == 20.0
    assert feats["net_forward"] == 50.0          # 70 - 20
    assert feats["duration"] == 15.0             # seconds 0 -> 15
    # Worked side to side, so the ball travelled further than the net gain.
    assert feats["path_length"] > feats["net_forward"]
    assert 0.0 < feats["directness"] < 1.0


def test_short_possession_is_skipped():
    short = pd.DataFrame([
        _event(1, "Pass", [20.0, 40.0], end=[30.0, 40.0]),
        _event(2, "Pass", [30.0, 40.0], end=[40.0, 40.0]),
    ])
    assert len(short) < MIN_ACTIONS
    assert possession_features(short, possession=1) is None


def test_opponent_events_excluded():
    events = _buildup()
    # Splice in an opponent touch that should not count toward the chain.
    intruder = pd.DataFrame([_event(5, "Pass", [60.0, 10.0], end=[10.0, 10.0], team="B")])
    events = pd.concat([events, intruder], ignore_index=True)
    feats = possession_features(events, possession=1)
    assert feats["n_actions"] == 4  # opponent pass ignored


def test_counter_is_more_direct_and_faster_than_buildup():
    counter = pd.DataFrame([
        _event(1, "Carry", [30.0, 40.0], end=[55.0, 40.0], second=0),
        _event(2, "Pass", [55.0, 40.0], end=[80.0, 40.0], second=2),
        _event(3, "Shot", [80.0, 40.0], end=[120.0, 40.0], second=4),
    ])
    c = possession_features(counter, possession=1)
    b = possession_features(_buildup(), possession=1)
    assert c["ends_in_shot"] == 1
    assert c["directness"] > b["directness"]
    assert c["forward_speed"] > b["forward_speed"]


def test_ends_in_shot_flag():
    feats = possession_features(_buildup().assign(), possession=1)
    assert feats["ends_in_shot"] == 0


def test_speed_guard_on_same_second_burst():
    # All actions in the same second: speed must fall back to net_forward, not blow up.
    burst = pd.DataFrame([
        _event(1, "Carry", [20.0, 40.0], end=[40.0, 40.0], second=3),
        _event(2, "Carry", [40.0, 40.0], end=[60.0, 40.0], second=3),
        _event(3, "Pass", [60.0, 40.0], end=[80.0, 40.0], second=3),
    ])
    feats = possession_features(burst, possession=1)
    assert feats["duration"] == 0.0
    assert np.isfinite(feats["forward_speed"])
    assert feats["forward_speed"] == feats["net_forward"]


def test_build_possession_frame_tags_and_filters():
    events = pd.concat([
        _buildup(),
        # A second, too-short possession that must be dropped.
        pd.DataFrame([
            _event(10, "Pass", [10.0, 40.0], end=[20.0, 40.0], possession=2),
            _event(11, "Pass", [20.0, 40.0], end=[30.0, 40.0], possession=2),
        ]),
    ], ignore_index=True)
    frame = build_possession_frame(events)
    assert len(frame) == 1
    assert frame.iloc[0]["possession"] == 1
    assert frame.iloc[0]["match_id"] == 99
    for key in POSSESSION_FEATURES:
        assert key in frame.columns
