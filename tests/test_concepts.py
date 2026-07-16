"""Tests for concept tagging, progress tracking, and adaptive selection."""

import math

import numpy as np
import pandas as pd

from pitchsense.concepts import (
    concept_scores,
    concept_weights,
    pick_adaptive,
    shot_concepts,
    shot_weight,
    update_progress,
)


def _shot(distance=15.0, angle_deg=40.0, defenders=1, header=0, one_on_one=0,
          pressure=0, cross=0, through=0):
    return pd.Series(
        {
            "distance": distance,
            "angle": math.radians(angle_deg),
            "defenders_in_cone": defenders,
            "is_header": header,
            "is_one_on_one": one_on_one,
            "under_pressure": pressure,
            "assist_cross": cross,
            "assist_through_ball": through,
        }
    )


def test_close_and_long_range_tags():
    assert "Close range" in shot_concepts(_shot(distance=5.0))
    assert "Long range" in shot_concepts(_shot(distance=30.0))


def test_tight_angle_and_crowded_and_header():
    tags = shot_concepts(_shot(angle_deg=10.0, defenders=4, header=1))
    assert "Tight angle" in tags
    assert "Crowded box" in tags
    assert "Header" in tags


def test_assist_and_situation_tags():
    tags = shot_concepts(_shot(one_on_one=1, pressure=1, cross=1, through=1))
    assert {"One-on-one", "Under pressure", "From cross", "Through ball"} <= set(tags)


def test_standard_chance_when_nothing_special():
    assert shot_concepts(_shot(distance=15.0, angle_deg=45.0, defenders=1)) == ["Standard chance"]


def test_update_and_score_progress():
    progress = {}
    update_progress(progress, ["Header", "Crowded box"], 80)
    update_progress(progress, ["Header"], 40)
    assert progress["Header"] == {"attempts": 2, "points": 120}
    scores = concept_scores(progress)
    assert scores["Header"] == 60.0
    assert scores["Crowded box"] == 80.0


def test_weights_favor_weak_and_unseen():
    progress = {}
    update_progress(progress, ["Header"], 100)  # strong
    update_progress(progress, ["Long range"], 0)  # weak
    weights = concept_weights(progress)
    assert weights["Tight angle"] == 1.5  # unseen -> exploration weight
    assert weights["Long range"] > weights["Header"]  # weak served more than strong


def test_shot_weight_takes_neediest_concept():
    weights = {"Header": 0.2, "Long range": 1.3}
    assert shot_weight(["Header", "Long range"], weights) == 1.3


def test_pick_adaptive_biases_to_heavy_shot():
    # Shot 1 is far weightier; it should be picked almost every time.
    concepts_per_shot = [["Header"], ["Long range"]]
    weights = {"Header": 0.001, "Long range": 10.0}
    rng = np.random.default_rng(0)
    picks = [pick_adaptive(concepts_per_shot, weights, rng) for _ in range(200)]
    assert picks.count(1) > 180


def test_pick_adaptive_returns_valid_index():
    rng = np.random.default_rng(1)
    idx = pick_adaptive([["Header"], ["Long range"], ["Close range"]], {}, rng)
    assert idx in (0, 1, 2)
