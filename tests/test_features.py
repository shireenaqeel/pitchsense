"""Unit tests for the pitch-geometry feature engineering."""

import math

import numpy as np
import pandas as pd

from pitchsense.features import (
    OPEN_SPACE,
    build_feature_frame,
    defenders_behind_ball,
    defenders_in_cone,
    distance_to_goal,
    keeper_distance_to_ball,
    keeper_distance_to_goal,
    nearest_defender_distance,
    shot_angle,
)


def _keeper(x, y):
    return {"teammate": False, "location": [x, y], "position": {"name": "Goalkeeper"}}


def _opponent(x, y):
    return {"teammate": False, "location": [x, y], "position": {"name": "Center Back"}}


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


def test_nearest_defender_picks_closest_opponent():
    ff = [_opponent(105.0, 40.0), _opponent(112.0, 44.0)]
    # Shot at (100,40): the first opponent is 5 yards away, the second ~12.6.
    assert nearest_defender_distance(100.0, 40.0, ff) == 5.0


def test_nearest_defender_excludes_keeper():
    ff = [_keeper(119.0, 40.0)]
    # Only the keeper is present, so there is no outfield defender close by.
    assert nearest_defender_distance(100.0, 40.0, ff) == OPEN_SPACE


def test_nearest_defender_default_when_no_freeze_frame():
    assert nearest_defender_distance(100.0, 40.0, None) == OPEN_SPACE


def test_defenders_behind_ball_counts_goal_side_only():
    ff = [
        _opponent(110.0, 40.0),   # goal-side of the shot
        _opponent(112.0, 30.0),   # goal-side
        _opponent(95.0, 40.0),    # behind the shooter, not counted
        _keeper(119.0, 40.0),     # keeper excluded
    ]
    assert defenders_behind_ball(100.0, 40.0, ff) == 2


def test_keeper_distance_to_goal_and_ball():
    ff = [_keeper(114.0, 40.0), _opponent(105.0, 40.0)]
    # Keeper 6 yards off the line (goal centre at 120,40).
    assert keeper_distance_to_goal(ff) == 6.0
    # Keeper is 14 yards from a shot taken at (100,40).
    assert keeper_distance_to_ball(100.0, 40.0, ff) == 14.0


def test_keeper_defaults_when_absent():
    ff = [_opponent(105.0, 40.0)]  # no keeper in the frame
    assert keeper_distance_to_goal(ff) == 0.0            # assume on the line
    assert keeper_distance_to_ball(100.0, 40.0, ff) == distance_to_goal(100.0, 40.0)


def test_new_freeze_frame_features_in_built_frame():
    ff = [_keeper(116.0, 40.0), _opponent(110.0, 40.0)]
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
            "shot_freeze_frame": [ff],
        }
    )
    out = build_feature_frame(shots).iloc[0]
    assert out["nearest_defender_dist"] == 10.0
    assert out["defenders_behind_ball"] == 1
    assert out["keeper_dist_to_goal"] == 4.0
    assert out["keeper_dist_to_ball"] == 16.0


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
