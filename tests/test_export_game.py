"""Tests for the browser-game export: frames, career roads and puzzle grids."""

import math

import numpy as np
import pandas as pd

from pitchsense.export_game import (
    CAREER_ORDER,
    CHAMPIONS,
    KEEPER,
    OPPONENT,
    PUZZLES,
    TEAMMATE,
    build_career,
    champion_road,
    compact_frame,
    end_point,
    goal_events,
    pick_match_shots,
    reachable_spots,
)
from pitchsense.features import distance_to_goal


def _player(x, y, teammate=False, position="Center Back"):
    return {"location": np.array([x, y]), "teammate": teammate, "position": {"name": position}}


def test_compact_frame_marks_kinds():
    frame = [_player(100, 40), _player(95, 30, teammate=True),
             _player(119, 40, position="Goalkeeper"), _player(5, 40, True, "Goalkeeper")]
    assert compact_frame(frame) == [[100.0, 40.0, OPPONENT], [95.0, 30.0, TEAMMATE],
                                    [119.0, 40.0, KEEPER], [5.0, 40.0, TEAMMATE]]


def test_compact_frame_handles_missing():
    assert compact_frame(None) == []


def test_end_point_defaults_height():
    assert end_point(np.array([120.0, 38.0])) == [120.0, 38.0, 0.0]
    assert end_point(np.array([120.0, 38.0, 1.234])) == [120.0, 38.0, 1.23]
    assert end_point(None) is None


def test_pick_match_shots_keeps_every_goal_in_order():
    minutes = list(range(30))
    goals = [0] * 30
    goals[3] = goals[27] = 1
    picks = pick_match_shots(minutes, goals, limit=6)
    assert len(picks) == 6
    assert 3 in picks and 27 in picks
    assert picks == sorted(picks, key=lambda i: minutes[i])


def test_pick_match_shots_returns_all_when_short():
    assert pick_match_shots([50, 10, 30], [0, 1, 0], limit=10) == [1, 2, 0]


def _match(mid, home, away, stage, date):
    return {"match_id": mid, "home_team": home, "away_team": away, "competition_stage": stage,
            "match_date": date, "home_score": 1, "away_score": 0,
            "competition": "International - FIFA World Cup", "season": "2018"}


def test_champion_road_is_dated_and_skips_third_place():
    matches = [
        _match(3, "France", "Croatia", "Final", "2018-07-15"),
        _match(1, "France", "Peru", "Group Stage", "2018-06-21"),
        _match(2, "Belgium", "England", "3rd Place Final", "2018-07-14"),
        _match(4, "Uruguay", "France", "Quarter-finals", "2018-07-06"),
    ]
    road = champion_road(matches, "France")
    assert [m["match_id"] for _, m in road] == [1, 4, 3]
    assert road[-1][0] == "Final"


def test_build_career_marks_the_final_as_boss():
    matches = {1: _match(1, "France", "Peru", "Group Stage", "2018-06-21"),
               2: _match(2, "France", "Croatia", "Final", "2018-07-15")}
    shots = pd.DataFrame({"id": ["a", "b", "c"], "match_id": [1, 2, 2],
                          "minute": [10, 5, 80], "is_goal": [0, 1, 0]})
    world = build_career(matches, shots)[0]
    assert world["name"] == "World Cup 2018" and world["champion"] == "France"
    assert [lvl["boss"] for lvl in world["levels"]] == [False, True]
    assert world["levels"][1]["shots"] == ["b", "c"]


def test_every_career_tournament_has_a_champion():
    assert set(CAREER_ORDER) == set(CHAMPIONS)


def test_reachable_spots_stay_in_reach_and_never_retreat():
    for puzzle in PUZZLES:
        sx, sy = puzzle["start"]
        spots = reachable_spots(puzzle)
        assert spots
        for x, y in spots:
            assert math.hypot(x - sx, y - sy) <= puzzle["reach"] + 1e-9
            assert distance_to_goal(x, y) <= distance_to_goal(sx, sy) + 1e-9


def test_goal_events_include_penalties_in_minute_order():
    raw = pd.DataFrame({"match_id": [1, 1, 1, 2], "minute": [80, 10, 50, 3],
                        "team": ["France", "Peru", "France", "Spain"],
                        "shot_outcome": ["Goal", "Goal", "Saved", "Goal"]})
    assert goal_events(raw) == {1: [[11, "Peru"], [81, "France"]], 2: [[4, "Spain"]]}
