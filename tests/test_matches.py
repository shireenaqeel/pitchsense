"""Tests for the match-context formatting that gives each shot its story."""

import pandas as pd

from pitchsense.matches import (
    build_name_map,
    match_subtitle,
    opponent,
    ordinal,
    shot_headline,
    stage_label,
    tournament_label,
)

MATCH = {"home_team": "Brazil", "away_team": "Belgium", "home_score": 1, "away_score": 2,
         "competition": "International - FIFA World Cup", "season": "2018",
         "competition_stage": "Quarter-finals"}


def test_tournament_label_strips_region_prefix():
    assert tournament_label("International - FIFA World Cup", "2018") == "World Cup 2018"
    assert tournament_label("Europe - UEFA Euro", "2024") == "Euro 2024"


def test_stage_label_is_singular_and_lowercase():
    assert stage_label("Quarter-finals") == "quarter-final"
    assert stage_label("Group Stage") == "group stage"
    assert stage_label(None) == ""


def test_opponent_is_the_other_side():
    assert opponent(MATCH, "Belgium") == "Brazil"
    assert opponent(MATCH, "Brazil") == "Belgium"


def test_ordinal_suffixes():
    assert [ordinal(n) for n in (1, 2, 3, 4, 11, 12, 13, 21, 22, 90)] == [
        "1st", "2nd", "3rd", "4th", "11th", "12th", "13th", "21st", "22nd", "90th"]


def test_headline_uses_display_name_and_one_based_minute():
    shot = {"player": "Neymar da Silva Santos Júnior", "team": "Brazil", "minute": 75}
    assert shot_headline(shot, MATCH, "Neymar") == "Neymar · Brazil vs Belgium · 76th minute"
    assert shot_headline(shot, None) == "Neymar da Silva Santos Júnior · Brazil · 76th minute"


def test_subtitle_hides_score_until_asked():
    assert match_subtitle(MATCH, include_score=False) == "World Cup 2018 quarter-final"
    assert match_subtitle(MATCH).endswith("final score Brazil 1–2 Belgium")
    assert match_subtitle(None) == ""


def test_name_map_prefers_nickname():
    lineups = pd.DataFrame({"player_name": ["Neymar da Silva Santos Júnior", "Kevin De Bruyne"],
                            "player_nickname": ["Neymar", None]})
    assert build_name_map(lineups) == {"Neymar da Silva Santos Júnior": "Neymar",
                                       "Kevin De Bruyne": "Kevin De Bruyne"}
