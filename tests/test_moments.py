"""Unit tests for the "What happens next?" moments (no network)."""

from pitchsense.export_game import moment_record
from pitchsense.moments import (
    ACTOR,
    CHOICES,
    KEEPER,
    OPPONENT,
    TEAMMATE,
    compact_360,
    decision,
    match_moments,
    orient,
    outcome,
    pick,
    zone,
    zone_rates,
)


def _event(id_, kind, loc, possession=1, team=1, **fields):
    """A raw StatsBomb event with the fields the moment code reads."""
    e = {"id": id_, "type": {"name": kind}, "location": loc, "possession": possession,
         "team": {"id": team, "name": "Blues"}, "player": {"name": "Ann Example"}, "minute": 12}
    e.update(fields)
    return e


def _frame(event_id, actor_at, others):
    ff = [{"location": actor_at, "actor": True, "teammate": True, "keeper": False}]
    ff += [{"location": loc, "actor": False, "teammate": mate, "keeper": gk} for loc, mate, gk in others]
    return {"event_uuid": event_id, "freeze_frame": ff}


CROWD = [([110, 40], False, False), ([112, 44], False, False), ([118, 40], False, True), ([104, 30], True, False)]


def test_decision_labels_the_four_calls_and_skips_set_pieces():
    assert decision(_event("a", "Shot", [110, 40], shot={"type": {"name": "Open Play"}})) == "shoot"
    assert decision(_event("b", "Shot", [108, 40], shot={"type": {"name": "Penalty"}})) is None
    assert decision(_event("c", "Pass", [100, 70], **{"pass": {"cross": True}})) == "cross"
    assert decision(_event("d", "Pass", [100, 40], **{"pass": {}})) == "pass"
    assert decision(_event("e", "Pass", [119, 79], **{"pass": {"type": {"name": "Corner"}}})) is None
    assert decision(_event("f", "Dribble", [100, 40])) == "dribble"
    assert decision(_event("g", "Carry", [90, 40], carry={"end_location": [97, 40]})) == "dribble"
    assert decision(_event("h", "Carry", [90, 40], carry={"end_location": [91, 41]})) is None


def test_compact_360_marks_actor_teammates_opponents_and_keeper():
    frame = _frame("x", [100.04, 40.0], CROWD)
    kinds = [p[2] for p in compact_360(frame)]
    assert kinds == [ACTOR, OPPONENT, OPPONENT, KEEPER, TEAMMATE]
    assert compact_360(frame)[0][:2] == [100.0, 40.0]


def test_zone_covers_the_final_third_without_gaps():
    seen = {zone(x, y) for x in range(80, 121, 2) for y in range(0, 81, 2)}
    assert seen == set(range(25))
    assert zone(120, 80) == 24


def test_outcome_reads_the_first_shot_after_the_decision():
    goal = _event("s", "Shot", [110, 40], shot={"outcome": {"name": "Goal"}})
    saved = _event("t", "Shot", [110, 40], shot={"outcome": {"name": "Saved"}})
    assert outcome([_event("p", "Pass", [100, 40]), goal]) == "goal"
    assert outcome([saved, goal]) == "shot"
    assert outcome([_event("p", "Pass", [100, 40])]) == "no shot"


def test_match_moments_builds_a_record_with_lead_up_and_aftermath():
    events = [
        _event("p1", "Pass", [70, 30], **{"pass": {"end_location": [85, 35]}}),
        _event("c1", "Carry", [85, 35], carry={"end_location": [86, 36]}),
        _event("p2", "Pass", [86, 36], **{"pass": {"end_location": [104, 40]}}),
        _event("s1", "Shot", [104, 40], shot={"type": {"name": "Open Play"}, "outcome": {"name": "Goal"},
                                             "end_location": [120, 39]}),
        _event("z1", "Pass", [95, 40], possession=2, **{"pass": {}}),  # no frame: skipped
    ]
    frames = [_frame("p2", [86, 36], CROWD), _frame("s1", [104, 40], CROWD)]
    moments = match_moments(events, frames, match_id=7)
    assert [m["id"] for m in moments] == ["p2", "s1"]
    shot = moments[1]
    assert shot["call"] == "shoot" and shot["outcome"] == "goal" and shot["match_id"] == 7
    assert shot["before"][0] == [70.0, 30.0] and shot["before"][-1] == [104.0, 40.0]
    assert shot["after"] == [[104.0, 40.0], [120.0, 39.0]]
    assert moments[0]["outcome"] == "goal"  # the pass led to the goal


def test_match_moments_needs_a_crowd_in_view_and_the_final_third():
    events = [_event("p", "Pass", [104, 40], **{"pass": {}}), _event("q", "Pass", [70, 40], **{"pass": {}})]
    frames = [_frame("p", [104, 40], CROWD[:2]), _frame("q", [70, 40], CROWD)]
    assert match_moments(events, frames, 1) == []


def test_zone_rates_sum_to_one_in_choice_order():
    moments = [{"x": 110, "y": 40, "call": c} for c in ["shoot", "shoot", "pass", "dribble"]]
    rates = zone_rates(moments)[zone(110, 40)]
    assert rates == [0.5, 0.25, 0.0, 0.25]
    assert len(rates) == len(CHOICES)


def test_pick_respects_quotas_and_spreads_matches():
    moments = [{"call": "pass", "match_id": m, "i": i} for m in range(3) for i in range(5)]
    chosen = pick(moments, quota={"pass": 6, "shoot": 2})
    assert len(chosen) == 6
    assert sorted(m["match_id"] for m in chosen) == [0, 0, 1, 1, 2, 2]
    assert pick(moments, quota={"pass": 6}) == chosen  # reproducible


def test_moment_record_uses_choice_indices_and_display_names():
    m = {"id": "e", "match_id": 3, "minute": 9, "player": "Full Name", "team": "Blues", "call": "cross",
         "x": 100.0, "y": 70.0, "frame": [[100, 70, ACTOR]], "before": [], "after": [[100, 70], [110, 40]],
         "outcome": "shot", "rates": [0.1, 0.5, 0.3, 0.1]}
    r = moment_record(m, "Short Name")
    assert r["call"] == CHOICES.index("cross") and r["player"] == "Short Name" and r["match"] == 3


def test_orient_turns_a_backwards_frame_to_match_its_event():
    frame = [[30.0, 20.0, ACTOR], [25.0, 40.0, OPPONENT]]
    assert orient(frame, [90.0, 60.0]) == [[90.0, 60.0, ACTOR], [95.0, 40.0, OPPONENT]]
    assert orient(frame, [30.5, 20.0]) == frame  # already the right way round
