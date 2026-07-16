"""Tests for building and interpolating a ball track from events."""

import numpy as np
import pandas as pd

from pitchsense.sequences import (
    build_waypoints,
    event_end_location,
    interpolate_track,
    possession_events,
)


def _events():
    return pd.DataFrame(
        {
            "type": ["Pass", "Carry", "Shot"],
            "team": ["A", "A", "A"],
            "player": ["p1", "p2", "p2"],
            "location": [[60.0, 40.0], [80.0, 40.0], [100.0, 40.0]],
            "pass_end_location": [[80.0, 40.0], None, None],
            "carry_end_location": [None, [100.0, 40.0], None],
            "shot_end_location": [None, None, [120.0, 40.0]],
        }
    )


def test_event_end_location_picks_field_by_type():
    rows = _events()
    assert event_end_location(rows.iloc[0]) == (80.0, 40.0)
    assert event_end_location(rows.iloc[1]) == (100.0, 40.0)
    assert event_end_location(rows.iloc[2]) == (120.0, 40.0)


def test_event_end_location_none_for_non_ball_action():
    row = pd.Series({"type": "Pressure", "location": [50.0, 50.0]})
    assert event_end_location(row) is None


def test_build_waypoints_merges_touching_points():
    wps = build_waypoints(_events())
    # Pass 60->80, Carry 80->100 (80 merged), Shot 100->120 (100 merged): 4 points.
    xs = [w["x"] for w in wps]
    assert xs == [60.0, 80.0, 100.0, 120.0]
    assert wps[-1]["action"] == "Shot"


def test_build_waypoints_skips_missing_location():
    events = pd.DataFrame(
        {
            "type": ["Pass", "Pass"],
            "player": ["p1", "p2"],
            "location": [None, [50.0, 50.0]],
            "pass_end_location": [[10.0, 10.0], [60.0, 50.0]],
        }
    )
    wps = build_waypoints(events)
    assert all(w["x"] != 10.0 for w in wps)


def test_interpolate_track_frame_count_and_endpoints():
    wps = [
        {"x": 0.0, "y": 0.0, "action": "Pass", "player": "p1"},
        {"x": 10.0, "y": 0.0, "action": "Pass", "player": "p1"},
    ]
    frames = interpolate_track(wps, frames_per_segment=10)
    assert len(frames) == 11  # 10 steps + final point
    assert frames[0]["x"] == 0.0
    assert frames[-1]["x"] == 10.0
    assert frames[5]["x"] == 5.0


def test_interpolate_empty_is_empty():
    assert interpolate_track([]) == []


def test_possession_events_filters_to_team_ball_actions():
    events = pd.DataFrame(
        {
            "index": [1, 2, 3, 4],
            "possession": [7, 7, 7, 7],
            "possession_team": ["A", "A", "A", "A"],
            "team": ["A", "A", "B", "A"],
            "type": ["Pass", "Pressure", "Pass", "Shot"],
            "location": [[1, 1], [2, 2], [3, 3], [4, 4]],
        }
    )
    chain = possession_events(events, 7)
    assert chain["type"].tolist() == ["Pass", "Shot"]  # Pressure + opponent pass dropped
