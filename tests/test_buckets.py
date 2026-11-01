"""Tests for Beginner-mode chance bands and their scoring."""

import pytest

from pitchsense.quiz import (
    BUCKET_LABELS,
    CHANCE_BUCKETS,
    bucket_balance,
    bucket_index,
    bucket_label,
    bucket_points,
    gap_points,
    out_of_100,
    outcome_text,
)


@pytest.mark.parametrize("xg, label", [
    (0.0, "Speculative"), (0.049, "Speculative"), (0.05, "Half chance"),
    (0.2, "Good chance"), (0.3, "Big chance"), (0.5, "Sitter"), (0.99, "Sitter"),
])
def test_bucket_label_boundaries(xg, label):
    assert bucket_label(xg) == label


def test_each_band_scores_with_a_probability_inside_the_band():
    # A Beginner answer is scored with its band's representative probability.
    for label, _, _, prob, _ in CHANCE_BUCKETS:
        assert bucket_label(prob) == label


def test_bucket_points_reward_matching_the_model():
    assert bucket_points("Big chance", 0.3) == 100
    assert bucket_points("Good chance", 0.3) == 50
    assert bucket_points("Speculative", 0.3) == 0


def test_gap_points_shrink_with_distance_from_model():
    assert gap_points(0.30, 0.32) == 100
    assert gap_points(0.30, 0.38) == 75
    assert gap_points(0.30, 0.48) == 50
    assert gap_points(0.0, 0.5) == 0


def test_out_of_100_never_shows_zero():
    assert out_of_100(0.001) == 1
    assert out_of_100(0.34) == 34


def test_bucket_balance_favours_rare_bands():
    xgs = [0.01] * 9 + [0.6]
    w = bucket_balance(xgs)
    assert w[-1] == pytest.approx(1.0)
    assert w[0] == pytest.approx(1 / 3)
    assert bucket_index(0.6) == len(BUCKET_LABELS) - 1


def test_outcome_text_is_friendly_with_fallback():
    assert outcome_text("Off T") == "Off target"
    assert outcome_text("Something new") == "Something new"
