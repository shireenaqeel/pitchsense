"""Build an animatable ball track from a StatsBomb possession.

StatsBomb records discrete events, not continuous tracking, so a "replay" is
reconstructed by walking the ball through the on-ball actions of a possession
(passes, carries, the shot) and interpolating between their start and end
locations. The waypoint and interpolation helpers are pure so they can be
tested without any network access.
"""

import numpy as np

# Event types that move the ball, mapped to the field holding their end point.
BALL_ACTIONS = {
    "Pass": "pass_end_location",
    "Carry": "carry_end_location",
    "Shot": "shot_end_location",
}


def _point(loc):
    if not isinstance(loc, (list, np.ndarray)) or len(loc) < 2:
        return None
    return (float(loc[0]), float(loc[1]))


def event_end_location(row):
    """Return the (x, y) end point for a ball action, or None."""
    end_field = BALL_ACTIONS.get(row.get("type"))
    if end_field is None:
        return None
    return _point(row.get(end_field))


def build_waypoints(events, min_step: float = 0.1):
    """Turn ordered ball events into a list of waypoints the ball passes through.

    Each waypoint is ``{"x", "y", "action", "player"}``. Consecutive points
    closer than ``min_step`` are merged so a pass received and then carried does
    not create a zero-length hop.
    """
    waypoints = []

    def push(x, y, action, player):
        if waypoints:
            last = waypoints[-1]
            if np.hypot(last["x"] - x, last["y"] - y) < min_step:
                return
        waypoints.append({"x": x, "y": y, "action": action, "player": player})

    for _, row in events.iterrows():
        start = _point(row.get("location"))
        if start is None:
            continue
        action = row.get("type")
        player = row.get("player")
        push(start[0], start[1], action, player)
        end = event_end_location(row)
        if end is not None:
            push(end[0], end[1], action, player)
    return waypoints


def interpolate_track(waypoints, frames_per_segment: int = 12):
    """Interpolate straight-line frames between consecutive waypoints.

    The action/player carried by each frame is the one for the segment being
    travelled, so a caption can name what is happening at that moment.
    """
    if not waypoints:
        return []
    frames = []
    for a, b in zip(waypoints, waypoints[1:]):
        for step in range(frames_per_segment):
            t = step / frames_per_segment
            frames.append(
                {
                    "x": a["x"] + (b["x"] - a["x"]) * t,
                    "y": a["y"] + (b["y"] - a["y"]) * t,
                    "action": b["action"],
                    "player": b["player"],
                }
            )
    last = waypoints[-1]
    frames.append({"x": last["x"], "y": last["y"], "action": last["action"], "player": last["player"]})
    return frames


def possession_events(events, possession: int):
    """Ordered on-ball events for one possession, by the possession team.

    Filters to the ball actions (pass/carry/shot) performed by the team in
    possession, dropping opponent touches and off-ball events.
    """
    chain = events[events["possession"] == possession].copy()
    chain = chain.sort_values("index") if "index" in chain.columns else chain
    team = chain["possession_team"].iloc[0]
    chain = chain[
        (chain["type"].isin(BALL_ACTIONS)) & (chain["team"] == team)
    ]
    return chain


def find_goal_possession(events):
    """Return the possession id of a goal with the richest build-up, or None."""
    goals = events[(events["type"] == "Shot") & (events["shot_outcome"] == "Goal")]
    best, best_len = None, 0
    for possession in goals["possession"].unique():
        n = len(possession_events(events, possession))
        if n > best_len:
            best, best_len = possession, n
    return best
