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


# Distance used for "nearest defender" when there is no opponent in the frame:
# a large value standing for "open space, nobody close".
OPEN_SPACE = 30.0


def _iter_opponents(freeze_frame):
    """Yield ``(x, y, is_keeper)`` for each opponent in a freeze-frame.

    Opponents are the entries with ``teammate`` False; the opposing goalkeeper is
    the opponent whose ``position`` name is Goalkeeper. Entries without a usable
    location are skipped.
    """
    if not isinstance(freeze_frame, (list, np.ndarray)):
        return
    for player in freeze_frame:
        if player.get("teammate", True):
            continue
        loc = player.get("location")
        if loc is None or len(loc) < 2:
            continue
        pos = player.get("position")
        name = pos.get("name") if isinstance(pos, dict) else pos
        yield float(loc[0]), float(loc[1]), name == "Goalkeeper"


def nearest_defender_distance(x: float, y: float, freeze_frame,
                              default: float = OPEN_SPACE) -> float:
    """Distance from the shot to the closest opponent outfielder (not the keeper).

    A large value means the shooter had space; the keeper is handled separately by
    its own features. Returns ``default`` when no outfield opponent is in the frame.
    """
    dists = [math.hypot(px - x, py - y)
             for px, py, is_keeper in _iter_opponents(freeze_frame) if not is_keeper]
    return min(dists) if dists else default


def defenders_behind_ball(x: float, y: float, freeze_frame) -> int:
    """Opponent outfielders that are goal-side of the shot (nearer the goal line).

    StatsBomb orients the shooting team to attack toward x=120, so an opponent with
    a larger x than the shot is between the ball and the goal.
    """
    return sum(1 for px, py, is_keeper in _iter_opponents(freeze_frame)
               if not is_keeper and px > x)


def goalkeeper_location(freeze_frame):
    """``(x, y)`` of the opposing goalkeeper, or ``None`` if not in the frame."""
    for px, py, is_keeper in _iter_opponents(freeze_frame):
        if is_keeper:
            return (px, py)
    return None


def keeper_distance_to_goal(freeze_frame) -> float:
    """How far the keeper is off the goal line (distance to the goal centre).

    Defaults to 0 (as if the keeper were on the line) when the keeper is absent.
    """
    gk = goalkeeper_location(freeze_frame)
    if gk is None:
        return 0.0
    return math.hypot(GOAL_CENTER[0] - gk[0], GOAL_CENTER[1] - gk[1])


def keeper_distance_to_ball(x: float, y: float, freeze_frame) -> float:
    """Distance from the keeper to the shot; small values are near one-on-ones.

    Defaults to the distance to goal (keeper assumed on the line) when absent.
    """
    gk = goalkeeper_location(freeze_frame)
    if gk is None:
        return distance_to_goal(x, y)
    return math.hypot(gk[0] - x, gk[1] - y)


# Half-width (yards) of the direct shooting lane — roughly a player's reach to
# either side of the straight line from the ball to the centre of the goal.
LANE_HALF_WIDTH = 1.5


def keeper_in_cone(x: float, y: float, freeze_frame) -> int:
    """Whether the opposing keeper sits inside the shot cone (guards the lane)."""
    gk = goalkeeper_location(freeze_frame)
    if gk is None:
        return 0
    return int(_point_in_triangle(
        gk[0], gk[1], x, y, LEFT_POST[0], LEFT_POST[1], RIGHT_POST[0], RIGHT_POST[1]
    ))


def _point_to_segment(px, py, ax, ay, bx, by) -> float:
    """Shortest distance from point p to the line segment ab."""
    abx, aby = bx - ax, by - ay
    ab2 = abx * abx + aby * aby
    if ab2 == 0:
        return math.hypot(px - ax, py - ay)
    t = max(0.0, min(1.0, ((px - ax) * abx + (py - ay) * aby) / ab2))
    cx, cy = ax + t * abx, ay + t * aby
    return math.hypot(px - cx, py - cy)


def defenders_in_lane(x: float, y: float, freeze_frame,
                      half_width: float = LANE_HALF_WIDTH) -> int:
    """Opponents sitting in the direct shooting lane from the ball to goal centre.

    Narrower than ``defenders_in_cone`` (the whole goal-mouth triangle): this
    counts only opponents close to the straight line to the middle of the goal,
    and only those goal-side of the shot, so it captures a directly blocked shot.
    """
    count = 0
    for px, py, is_keeper in _iter_opponents(freeze_frame):
        if is_keeper or px <= x:
            continue
        if _point_to_segment(px, py, x, y, GOAL_CENTER[0], GOAL_CENTER[1]) <= half_width:
            count += 1
    return count


def shot_end_point(end_location):
    """``(x, y, z)`` of a shot's end location; height defaults to 0 when absent."""
    if not isinstance(end_location, (list, np.ndarray)) or len(end_location) < 2:
        return None
    z = float(end_location[2]) if len(end_location) >= 3 else 0.0
    return (float(end_location[0]), float(end_location[1]), z)


def placement_from_center(end_location) -> float:
    """How far the shot finished from the goal's central line (toward a post)."""
    point = shot_end_point(end_location)
    return abs(point[1] - GOAL_CENTER[1]) if point else 0.0


def placement_height(end_location) -> float:
    """Height the shot finished at (0 = along the ground)."""
    point = shot_end_point(end_location)
    return point[2] if point else 0.0


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
    df["nearest_defender_dist"] = df.apply(
        lambda r: nearest_defender_distance(r["x"], r["y"], r["shot_freeze_frame"]), axis=1
    )
    df["defenders_behind_ball"] = df.apply(
        lambda r: defenders_behind_ball(r["x"], r["y"], r["shot_freeze_frame"]), axis=1
    )
    df["keeper_dist_to_goal"] = df["shot_freeze_frame"].apply(keeper_distance_to_goal)
    df["keeper_dist_to_ball"] = df.apply(
        lambda r: keeper_distance_to_ball(r["x"], r["y"], r["shot_freeze_frame"]), axis=1
    )
    df["keeper_in_cone"] = df.apply(
        lambda r: keeper_in_cone(r["x"], r["y"], r["shot_freeze_frame"]), axis=1
    )
    df["defenders_in_lane"] = df.apply(
        lambda r: defenders_in_lane(r["x"], r["y"], r["shot_freeze_frame"]), axis=1
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
    "nearest_defender_dist",
    "defenders_behind_ball",
    "keeper_dist_to_goal",
    "keeper_dist_to_ball",
    "keeper_in_cone",
    "defenders_in_lane",
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
