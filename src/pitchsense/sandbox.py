"""'Be the striker': build a made-up shot and let the real model rate it.

The quiz shows real shots; the sandbox lets a learner *change one thing at a
time* — step closer, drift wide, add a defender, bring the keeper off the line —
and watch the model's xG respond. That is the fastest way to build intuition for
what makes a chance.

A scenario is turned into a synthetic StatsBomb-shaped shot row (location,
freeze-frame, body part, ...) and pushed through the same
``build_feature_frame`` the model was trained on, so the sandbox can never drift
from the real feature definitions. Pure and UI-free so it can be unit tested.
"""

import math
from dataclasses import asdict, dataclass

import numpy as np
import pandas as pd

from pitchsense.features import GOAL_CENTER, build_feature_frame

# Nearest-marker choices: label -> distance in yards from the shooter.
MARKER_GAPS = {"Right on you": 1.0, "Close": 3.0, "Some space": 6.0, "Free": 12.0}

# Keeper choices: label -> how far off the goal line the keeper stands, as a
# function of the shot distance (rushing out closes half the gap, capped).
KEEPER_POSITIONS = ["On the line", "Off the line", "Rushing out"]

ASSIST_TYPES = ["None", "Cross", "Cutback", "Through ball"]


@dataclass(frozen=True)
class Scenario:
    x: float = 105.0               # up the pitch (goal at x=120)
    y: float = 40.0                # across the pitch (goal centre at y=40)
    blockers: int = 1              # defenders between ball and goal
    marker: str = "Close"          # how close the nearest defender is
    keeper: str = "On the line"
    header: bool = False
    first_time: bool = False
    one_on_one: bool = False
    under_pressure: bool = False
    assist: str = "None"


# Ready-made situations used by the lessons and the sandbox's preset buttons.
PRESETS = {
    "Penalty-spot tap-in": Scenario(x=108, y=40, blockers=0, marker="Free"),
    "Edge of the box": Scenario(x=101, y=40, blockers=2, marker="Close"),
    "Long-range screamer": Scenario(x=88, y=38, blockers=2, marker="Some space"),
    "Tight angle by the byline": Scenario(x=116, y=30, blockers=1, marker="Close"),
    "Header from a cross": Scenario(x=110, y=42, blockers=1, marker="Right on you",
                                    header=True, assist="Cross"),
    "Through on goal": Scenario(x=104, y=38, blockers=0, marker="Some space",
                                keeper="Rushing out", one_on_one=True, assist="Through ball"),
    "Cutback to the penalty spot": Scenario(x=108, y=41, blockers=1, marker="Some space",
                                            first_time=True, assist="Cutback"),
}


def _unit_to_goal(x: float, y: float) -> tuple[float, float, float]:
    """Unit vector from the shot toward the goal centre, and the distance."""
    dx, dy = GOAL_CENTER[0] - x, GOAL_CENTER[1] - y
    dist = math.hypot(dx, dy) or 1e-6
    return dx / dist, dy / dist, dist


def keeper_point(scenario: Scenario) -> tuple[float, float]:
    """Where the keeper stands, on the line from the goal centre to the ball."""
    ux, uy, dist = _unit_to_goal(scenario.x, scenario.y)
    off_line = {"On the line": 1.0,
                "Off the line": min(4.0, dist * 0.4),
                "Rushing out": min(10.0, dist * 0.55)}[scenario.keeper]
    return GOAL_CENTER[0] - ux * off_line, GOAL_CENTER[1] - uy * off_line


def blocker_points(scenario: Scenario) -> list:
    """Defenders spread along the shooting lane, between the ball and the keeper."""
    ux, uy, dist = _unit_to_goal(scenario.x, scenario.y)
    points = []
    for i in range(scenario.blockers):
        frac = 0.25 + 0.5 * (i + 1) / (scenario.blockers + 1)   # 25%..75% of the way
        side = 0.7 * (1 if i % 2 else -1)                      # alternate either side
        px = scenario.x + ux * dist * frac - uy * side
        py = scenario.y + uy * dist * frac + ux * side
        points.append((px, py))
    return points


def marker_point(scenario: Scenario) -> tuple[float, float]:
    """The nearest marker, trailing the shooter (so it does not block the lane)."""
    ux, uy, _ = _unit_to_goal(scenario.x, scenario.y)
    gap = MARKER_GAPS[scenario.marker]
    return scenario.x - ux * gap, scenario.y - uy * gap


def _player(point, teammate: bool, position: str) -> dict:
    return {"location": np.array(point, dtype=float), "teammate": teammate,
            "position": {"name": position}}


def scenario_shot(scenario: Scenario) -> pd.Series:
    """A StatsBomb-shaped shot row for the scenario, before feature engineering."""
    frame = [_player(keeper_point(scenario), False, "Goalkeeper"),
             _player(marker_point(scenario), False, "Center Back")]
    frame += [_player(p, False, "Center Back") for p in blocker_points(scenario)]
    return pd.Series({
        "id": "sandbox", "match_id": 0, "team": "You", "player": "You", "minute": 0,
        "location": np.array([scenario.x, scenario.y], dtype=float),
        "shot_end_location": None,
        "play_pattern": "Regular Play",
        "under_pressure": scenario.under_pressure,
        "shot_body_part": "Head" if scenario.header else "Right Foot",
        "shot_technique": "Normal", "shot_type": "Open Play", "shot_outcome": "Unknown",
        "shot_first_time": scenario.first_time,
        "shot_one_on_one": scenario.one_on_one,
        "shot_freeze_frame": np.array(frame, dtype=object),
        "shot_key_pass_id": None, "shot_statsbomb_xg": None,
        "assist_cross": int(scenario.assist == "Cross"),
        "assist_cutback": int(scenario.assist == "Cutback"),
        "assist_through_ball": int(scenario.assist == "Through ball"),
    })


def scenario_features(scenarios) -> pd.DataFrame:
    """Engineered features for one or many scenarios, via the real pipeline."""
    if isinstance(scenarios, Scenario):
        scenarios = [scenarios]
    return build_feature_frame(pd.DataFrame([scenario_shot(s) for s in scenarios]))


def xg_map(model, scenario: Scenario, feature_columns, step: float = 2.0):
    """xG over a grid of shooting spots, holding every other setting fixed.

    Returns ``(xs, ys, grid)`` for a heatmap of the attacking third. Defenders and
    the keeper move with the ball, so the map isolates *where you shoot from*.
    """
    xs = np.arange(84.0, 119.0 + 1e-9, step)
    ys = np.arange(14.0, 66.0 + 1e-9, step)
    base = asdict(scenario)
    grid_scenarios = [Scenario(**{**base, "x": float(x), "y": float(y)}) for y in ys for x in xs]
    feats = scenario_features(grid_scenarios)
    probs = model.predict_proba(feats[feature_columns])[:, 1]
    return xs, ys, probs.reshape(len(ys), len(xs))
