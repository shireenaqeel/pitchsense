"""Unit tests for the post-shot xG (PSxG) frame building (no network)."""

import pandas as pd

from pitchsense.features import FEATURE_COLUMNS
from pitchsense.postshot import (
    ON_TARGET_OUTCOMES,
    PLACEMENT_FEATURES,
    POSTSHOT_FEATURES,
    build_postshot_frame,
)


def _shots():
    """Four shots: a goal, a save, an off-target miss, and a block."""
    return pd.DataFrame(
        {
            "location": [[100.0, 40.0], [105.0, 44.0], [90.0, 30.0], [98.0, 42.0]],
            "shot_type": ["Open Play"] * 4,
            "shot_outcome": ["Goal", "Saved", "Off T", "Blocked"],
            "shot_end_location": [
                [120.0, 37.0, 2.5],   # goal, high to the side
                [120.0, 40.0, 0.5],   # saved, central low
                [125.0, 55.0, 3.0],   # missed, wide and over
                [110.0, 41.0, 0.3],   # blocked short of goal
            ],
            "shot_body_part": ["Right Foot"] * 4,
            "shot_first_time": [False] * 4,
            "shot_one_on_one": [False] * 4,
            "under_pressure": [None] * 4,
            "play_pattern": ["Regular Play"] * 4,
            "shot_freeze_frame": [None] * 4,
        }
    )


def test_only_on_target_shots_are_kept():
    frame = build_postshot_frame(_shots())
    assert len(frame) == 2  # goal + save; miss and block dropped
    assert set(frame["shot_outcome"]) <= ON_TARGET_OUTCOMES
    assert frame["is_goal"].tolist() == [1, 0]


def test_placement_features_are_added():
    frame = build_postshot_frame(_shots())
    for col in PLACEMENT_FEATURES:
        assert col in frame.columns
    goal_row = frame[frame["is_goal"] == 1].iloc[0]
    assert goal_row["placement_from_center"] == 3.0   # |37 - 40|
    assert goal_row["placement_height"] == 2.5


def test_postshot_feature_set_extends_preshot_with_placement():
    assert POSTSHOT_FEATURES == FEATURE_COLUMNS + PLACEMENT_FEATURES
    # placement is exactly the extra signal a post-shot model is allowed to use
    assert set(PLACEMENT_FEATURES) == {"placement_from_center", "placement_height"}
