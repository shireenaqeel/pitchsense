"""Unit tests for the persistent quiz leaderboard (uses a temp file)."""

from datetime import datetime, timezone

import pytest

from pitchsense.leaderboard import (
    add_score,
    load_scores,
    make_entry,
    ranked,
    save_scores,
    top,
)


def test_make_entry_computes_averages_and_margin():
    entry = make_entry("Sam", total_points=360, model_points=300, rounds=6,
                       when=datetime(2026, 7, 17, tzinfo=timezone.utc))
    assert entry["name"] == "Sam"
    assert entry["rounds"] == 6
    assert entry["avg_points"] == 60.0
    assert entry["model_avg"] == 50.0
    assert entry["vs_model"] == 10.0        # beat the model by 10 pts/round
    assert entry["date"] == "2026-07-17"


def test_make_entry_defaults_blank_name_and_validates_rounds():
    assert make_entry("   ", 10, 10, 1)["name"] == "Anonymous"
    with pytest.raises(ValueError):
        make_entry("Sam", 0, 0, 0)


def test_load_missing_file_is_empty(tmp_path):
    assert load_scores(tmp_path / "nope.json") == []


def test_add_and_load_roundtrip(tmp_path):
    path = tmp_path / "lb.json"
    add_score(make_entry("A", 300, 200, 5), path)
    add_score(make_entry("B", 450, 200, 5), path)
    scores = load_scores(path)
    assert len(scores) == 2
    assert {s["name"] for s in scores} == {"A", "B"}


def test_corrupt_file_yields_empty_board(tmp_path):
    path = tmp_path / "lb.json"
    path.write_text("{ not json", encoding="utf-8")
    assert load_scores(path) == []


def test_ranked_orders_by_average_then_margin_then_rounds():
    scores = [
        make_entry("Low", 250, 250, 5),      # avg 50
        make_entry("High", 400, 300, 5),     # avg 80, +20
        make_entry("Mid", 300, 200, 5),      # avg 60, +20
    ]
    order = [s["name"] for s in ranked(scores)]
    assert order == ["High", "Mid", "Low"]


def test_margin_breaks_ties_on_average():
    scores = [
        make_entry("Beats", 300, 200, 5),    # avg 60, +20
        make_entry("Ties", 300, 300, 5),     # avg 60, 0
    ]
    order = [s["name"] for s in ranked(scores)]
    assert order == ["Beats", "Ties"]


def test_min_rounds_filter_excludes_thin_scores():
    scores = [
        make_entry("Cameo", 100, 50, 1),     # perfect-ish but only 1 round
        make_entry("Steady", 240, 200, 6),   # avg 40 over 6 rounds
    ]
    assert [s["name"] for s in ranked(scores, min_rounds=5)] == ["Steady"]


def test_top_limits_count(tmp_path):
    scores = [make_entry(f"P{i}", 300 + i, 200, 5) for i in range(12)]
    assert len(top(scores, n=10)) == 10


def test_save_scores_creates_parent_dir(tmp_path):
    path = tmp_path / "nested" / "lb.json"
    save_scores([make_entry("A", 300, 200, 5)], path)
    assert path.exists()
    assert load_scores(path)[0]["name"] == "A"
