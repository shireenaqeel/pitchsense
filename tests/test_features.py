"""Unit tests for the pitch-geometry feature engineering."""

import math

import numpy as np
import pandas as pd

from pitchsense.features import (
    build_feature_frame,
    defenders_in_cone,
    distance_to_goal,
    shot_angle,
)


def test_distance_from_goal_center_is_zero():
    assert distance_to_goal(120.0, 40.0) == 0.0


def test_distance_from_penalty_spot():
    # Penalty spot is 12 yards out, on the central line.
    assert distance_to_goal(108.0, 40.0) == 12.0


def test_angle_wider_when_closer_and_central():
    close = shot_angle(114.0, 40.0)
    far = shot_angle(90.0, 40.0)
    assert close > far


def test_angle_smaller_from_tight_side_position():
    central = shot_angle(110.0, 40.0)
    wide = shot_angle(110.0, 5.0)
    assert central > wide


def test_angle_is_positive_and_bounded():
    a = shot_angle(100.0, 30.0)
    assert 0.0 < a < math.pi


def test_defender_directly_in_front_is_counted():
    ff = [{"teammate": False, "location": [115.0, 40.0]}]
    assert defenders_in_cone(100.0, 40.0, ff) == 1


def test_teammate_in_cone_is_ignored():
    ff = [{"teammate": True, "location": [115.0, 40.0]}]
    assert defenders_in_cone(100.0, 40.0, ff) == 0


def test_defender_outside_cone_is_not_counted():
    ff = [{"teammate": False, "location": [110.0, 10.0]}]
    assert defenders_in_cone(100.0, 40.0, ff) == 0


def test_missing_freeze_frame_returns_zero():
    assert defenders_in_cone(100.0, 40.0, None) == 0


def test_freeze_frame_with_numpy_array_locations():
    # After a parquet round-trip, locations come back as numpy arrays rather
    # than plain lists; the cone test must handle both.
    ff = np.array(
        [
            {"teammate": False, "location": np.array([115.0, 40.0])},
            {"teammate": False, "location": np.array([110.0, 10.0])},
        ],
        dtype=object,
    )
    assert defenders_in_cone(100.0, 40.0, ff) == 1


def test_build_feature_frame_drops_penalties_and_labels_goals():
    shots = pd.DataFrame(
        {
            "location": [[100.0, 40.0], [108.0, 40.0], [95.0, 30.0]],
            "shot_type": ["Open Play", "Penalty", "Open Play"],
            "shot_outcome": ["Goal", "Goal", "Saved"],
            "shot_body_part": ["Right Foot", "Right Foot", "Head"],
            "shot_first_time": [True, False, False],
            "shot_one_on_one": [False, False, False],
            "under_pressure": [None, None, True],
            "play_pattern": ["Regular Play", "From Penalty", "From Corner"],
            "shot_freeze_frame": [None, None, None],
        }
    )
    out = build_feature_frame(shots)
    assert len(out) == 2  # penalty dropped
    assert out["is_goal"].tolist() == [1, 0]
    assert out["is_header"].tolist() == [0, 1]


def test_assist_features_default_to_zero_when_absent():
    shots = pd.DataFrame(
        {
            "location": [[100.0, 40.0]],
            "shot_type": ["Open Play"],
            "shot_outcome": ["Goal"],
            "shot_body_part": ["Right Foot"],
            "shot_first_time": [False],
            "shot_one_on_one": [False],
            "under_pressure": [None],
            "play_pattern": ["Regular Play"],
            "shot_freeze_frame": [None],
        }
    )
    out = build_feature_frame(shots)
    assert out["assist_cross"].tolist() == [0]
    assert out["assist_cutback"].tolist() == [0]
    assert out["assist_through_ball"].tolist() == [0]


def test_assist_features_preserved_when_present():
    shots = pd.DataFrame(
        {
            "location": [[100.0, 40.0]],
            "shot_type": ["Open Play"],
            "shot_outcome": ["Saved"],
            "shot_body_part": ["Left Foot"],
            "shot_first_time": [True],
            "shot_one_on_one": [False],
            "under_pressure": [None],
            "play_pattern": ["From Counter"],
            "shot_freeze_frame": [None],
            "assist_cross": [1],
            "assist_cutback": [0],
            "assist_through_ball": [1],
        }
    )
    out = build_feature_frame(shots)
    assert out["assist_cross"].tolist() == [1]
    assert out["assist_through_ball"].tolist() == [1]
