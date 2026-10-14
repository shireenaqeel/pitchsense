"""Tests for the 'be the striker' scenario builder."""

import math

import pytest

from pitchsense.features import FEATURE_COLUMNS
from pitchsense.sandbox import (
    PRESETS,
    Scenario,
    blocker_points,
    keeper_point,
    marker_point,
    scenario_features,
)


def test_scenario_runs_through_the_real_feature_pipeline():
    feats = scenario_features(Scenario(x=108, y=40, blockers=0, marker="Free"))
    assert len(feats) == 1
    assert set(FEATURE_COLUMNS) <= set(feats.columns)
    assert feats.iloc[0]["distance"] == pytest.approx(12.0)


def test_blockers_land_in_the_shooting_cone():
    feats = scenario_features(Scenario(x=100, y=40, blockers=3, marker="Free"))
    # Three blockers plus the keeper on the line, all inside the cone.
    assert feats.iloc[0]["defenders_in_cone"] == 4


def test_marker_sets_the_nearest_defender_distance():
    feats = scenario_features(Scenario(x=100, y=40, blockers=0, marker="Some space"))
    assert feats.iloc[0]["nearest_defender_dist"] == pytest.approx(6.0)


def test_keeper_moves_toward_the_ball_when_rushing():
    on_line = keeper_point(Scenario(x=100, y=40, keeper="On the line"))
    rushing = keeper_point(Scenario(x=100, y=40, keeper="Rushing out"))
    assert rushing[0] < on_line[0] <= 120


def test_header_and_assist_flags_carry_through():
    feats = scenario_features(Scenario(header=True, assist="Cutback")).iloc[0]
    assert feats["is_header"] == 1 and feats["assist_cutback"] == 1
    assert feats["assist_cross"] == 0


def test_marker_trails_the_shooter():
    mx, _ = marker_point(Scenario(x=100, y=40, marker="Close"))
    assert mx < 100
    assert all(px > 100 for px, _ in blocker_points(Scenario(x=100, y=40, blockers=2)))


def test_presets_build():
    feats = scenario_features(list(PRESETS.values()))
    assert len(feats) == len(PRESETS)
    assert not feats[FEATURE_COLUMNS].isna().any().any()
