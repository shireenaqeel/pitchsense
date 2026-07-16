"""Tests for wiring the tactical pattern into the animated replay."""

import inspect

import pandas as pd

from pitchsense import animate, tactics


def _events():
    return pd.DataFrame([
        {"index": 1, "type": "Pass", "location": [20.0, 40.0],
         "pass_end_location": [40.0, 40.0], "minute": 0, "second": 0,
         "possession": 1, "possession_team": "A", "team": "A", "player": "P"},
        {"index": 2, "type": "Carry", "location": [40.0, 40.0],
         "carry_end_location": [60.0, 40.0], "minute": 0, "second": 3,
         "possession": 1, "possession_team": "A", "team": "A", "player": "P"},
        {"index": 3, "type": "Shot", "location": [60.0, 40.0],
         "shot_end_location": [120.0, 40.0], "minute": 0, "second": 5,
         "possession": 1, "possession_team": "A", "team": "A", "player": "P"},
    ])


def test_pattern_is_none_when_model_untrained(tmp_path, monkeypatch):
    monkeypatch.setattr(tactics, "MODEL_PATH", tmp_path / "absent.joblib")
    assert animate.possession_pattern(_events(), possession=1) is None


def test_animate_sequence_accepts_pattern():
    # The pattern is an optional caption; the signature must expose it.
    assert "pattern" in inspect.signature(animate.animate_sequence).parameters
