"""Tests for the quiz scoring and explanation logic."""

import math

import pandas as pd
import pytest

from pitchsense.quiz import brier_points, explain_shot, model_gap, verdict


def test_perfect_guess_scores_full():
    assert brier_points(1.0, 1) == 100
    assert brier_points(0.0, 0) == 100


def test_worst_guess_scores_zero():
    assert brier_points(1.0, 0) == 0
    assert brier_points(0.0, 1) == 0


def test_coin_flip_scores_75():
    assert brier_points(0.5, 1) == 75
    assert brier_points(0.5, 0) == 75


def test_guess_is_clamped():
    assert brier_points(1.5, 1) == 100
    assert brier_points(-0.5, 0) == 100


def test_model_gap_is_absolute_difference():
    assert model_gap(0.3, 0.5) == pytest.approx(0.2)
    assert model_gap(0.7, 0.5) == pytest.approx(0.2)


def test_verdict_reads_direction():
    assert verdict(0.5, 0.5) == "close to the model"
    assert verdict(0.9, 0.5) == "higher than the model"
    assert verdict(0.1, 0.5) == "lower than the model"


def _shot(is_goal, defenders=2, header=0, pressure=0):
    # distance 20 yds, angle in radians for a central-ish shot.
    return pd.Series(
        {
            "distance": 20.0,
            "angle": math.radians(30),
            "defenders_in_cone": defenders,
            "is_header": header,
            "under_pressure": pressure,
            "is_goal": is_goal,
        }
    )


def test_explanation_mentions_key_facts_and_goal():
    text = explain_shot(_shot(1, defenders=2), model_xg=0.15, guess=0.4)
    assert "20 yards" in text
    assert "2 defenders" in text
    assert "15%" in text and "40%" in text
    assert "goal" in text.lower()


def test_explanation_reports_no_goal_and_header():
    text = explain_shot(_shot(0, defenders=0, header=1, pressure=1), model_xg=0.2, guess=0.2)
    assert "no defenders" in text.lower()
    assert "header" in text.lower()
    assert "under pressure" in text.lower()
    assert "did not go in" in text.lower()
