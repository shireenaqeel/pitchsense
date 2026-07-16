"""Turn raw StatsBomb shot events into a numeric feature table for the xG model.

Pitch geometry follows the StatsBomb convention: the pitch is 120x80 yards and
the attacking goal is at x=120, with posts at y=36 and y=44 (an 8-yard mouth
centred on y=40). The geometry helpers are pure functions so they can be unit
tested independently of the data.
"""

import math

import numpy as np
import pandas as pd

PITCH_LENGTH = 120.0
GOAL_CENTER = (120.0, 40.0)
LEFT_POST = (120.0, 36.0)
RIGHT_POST = (120.0, 44.0)


def distance_to_goal(x: float, y: float) -> float:
    """Straight-line distance from the shot location to the centre of the goal."""
    return math.hypot(GOAL_CENTER[0] - x, GOAL_CENTER[1] - y)


def shot_angle(x: float, y: float) -> float:
    """Angle (radians) subtended by the goal mouth at the shot location.

    A wider angle means more of the goal is visible, so scoring is easier. The
    value is the angle between the vectors from the shot to each post.
    """
    v1 = (LEFT_POST[0] - x, LEFT_POST[1] - y)
    v2 = (RIGHT_POST[0] - x, RIGHT_POST[1] - y)
    dot = v1[0] * v2[0] + v1[1] * v2[1]
    mag = math.hypot(*v1) * math.hypot(*v2)
    if mag == 0:
        return 0.0
    cos_theta = max(-1.0, min(1.0, dot / mag))
    return math.acos(cos_theta)


def _sign(ax, ay, bx, by, cx, cy) -> float:
    return (ax - cx) * (by - cy) - (bx - cx) * (ay - cy)


def _point_in_triangle(px, py, ax, ay, bx, by, cx, cy) -> bool:
    """Whether point p lies inside triangle abc (edges inclusive)."""
    d1 = _sign(px, py, ax, ay, bx, by)
    d2 = _sign(px, py, bx, by, cx, cy)
    d3 = _sign(px, py, cx, cy, ax, ay)
    has_neg = (d1 < 0) or (d2 < 0) or (d3 < 0)
    has_pos = (d1 > 0) or (d2 > 0) or (d3 > 0)
    return not (has_neg and has_pos)


def defenders_in_cone(x: float, y: float, freeze_frame) -> int:
    """Count opponents inside the triangle from the shot to both goal posts.

    ``freeze_frame`` is the StatsBomb list of players at the moment of the shot;
    each entry has a ``location`` and a ``teammate`` flag (False = opponent).
    These are the players actually blocking the path to goal.
    """
    if not isinstance(freeze_frame, (list, np.ndarray)):
        return 0
    count = 0
    for player in freeze_frame:
        if player.get("teammate", True):
            continue
        loc = player.get("location")
        if loc is None or len(loc) < 2:
            continue
        if _point_in_triangle(
            loc[0], loc[1], x, y, LEFT_POST[0], LEFT_POST[1], RIGHT_POST[0], RIGHT_POST[1]
        ):
            count += 1
    return count


def build_feature_frame(shots: pd.DataFrame) -> pd.DataFrame:
    """Build the model-ready table of engineered features plus the target.

    Penalties are dropped: they are a fixed-distance set piece that scores far
    more often than open play and would distort an open-play xG model.
    """
    df = shots[shots["shot_type"] != "Penalty"].copy()

    locs = df["location"].apply(lambda p: p if isinstance(p, (list, np.ndarray)) else [np.nan, np.nan])
    df["x"] = locs.apply(lambda p: p[0])
    df["y"] = locs.apply(lambda p: p[1])
    df = df.dropna(subset=["x", "y"])

    df["distance"] = df.apply(lambda r: distance_to_goal(r["x"], r["y"]), axis=1)
    df["angle"] = df.apply(lambda r: shot_angle(r["x"], r["y"]), axis=1)
    df["defenders_in_cone"] = df.apply(
        lambda r: defenders_in_cone(r["x"], r["y"], r["shot_freeze_frame"]), axis=1
    )
    df["is_header"] = (df["shot_body_part"] == "Head").astype(int)
    df["is_first_time"] = df["shot_first_time"].fillna(False).astype(int)
    df["is_one_on_one"] = df["shot_one_on_one"].fillna(False).astype(int)
    df["under_pressure"] = df["under_pressure"].fillna(False).astype(int)
    df["from_open_play"] = (df["play_pattern"] == "Regular Play").astype(int)

    for col in ("assist_cross", "assist_cutback", "assist_through_ball"):
        df[col] = df[col].fillna(0).astype(int) if col in df.columns else 0

    df["is_goal"] = (df["shot_outcome"] == "Goal").astype(int)

    return df


FEATURE_COLUMNS = [
    "distance",
    "angle",
    "defenders_in_cone",
    "is_header",
    "is_first_time",
    "is_one_on_one",
    "under_pressure",
    "from_open_play",
    "assist_cross",
    "assist_cutback",
    "assist_through_ball",
]
TARGET_COLUMN = "is_goal"
