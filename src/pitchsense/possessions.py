"""Turn a StatsBomb possession into a numeric feature vector for tactics.

A "possession" is StatsBomb's grouping of consecutive events while one team has
the ball. The tactical pattern classifier works on these sequences rather than
single shots: it clusters possessions by *how* the ball was moved — patiently
worked through many passes, driven directly upfield, or won and used quickly —
to surface archetypes like build-up, counter-attack, and quick regain.

There are no ground-truth tactical labels in the data, so this is unsupervised:
the features here describe the shape and tempo of a possession, and the
clustering in ``tactics.py`` groups similar ones. These helpers are pure so they
can be unit tested without any network access.
"""

import numpy as np

from pitchsense.sequences import BALL_ACTIONS, build_waypoints, possession_events

# A possession needs at least this many on-ball actions to be a meaningful
# sequence; shorter chains (a clearance, a single hopeful pass) carry no pattern.
MIN_ACTIONS = 3

POSSESSION_FEATURES = [
    "duration",       # seconds from the first to the last on-ball action
    "n_actions",      # number of on-ball actions (passes, carries, the shot)
    "n_passes",       # number of passes in the chain
    "start_x",        # how far upfield the possession began (0-120)
    "net_forward",    # net upfield yards gained, start to end
    "path_length",    # total distance the ball travelled through the chain
    "directness",     # net_forward / path_length: straight at goal vs. worked
    "forward_speed",  # net_forward per second: how fast it went upfield
    "width",          # lateral spread (max - min y) the possession covered
    "ends_in_shot",   # whether the possession finished with a shot
]


def _event_time(row) -> float:
    """Seconds into the match for an event, from its minute/second fields."""
    minute = row.get("minute")
    second = row.get("second")
    if minute is None or second is None:
        return 0.0
    return float(minute) * 60.0 + float(second)


def _path_length(waypoints) -> float:
    total = 0.0
    for a, b in zip(waypoints, waypoints[1:]):
        total += float(np.hypot(b["x"] - a["x"], b["y"] - a["y"]))
    return total


def possession_features(events, possession) -> dict:
    """Feature vector for one possession, or None if it is too short.

    ``events`` is the full event frame for a match; ``possession`` is the id to
    describe. Returns ``None`` when the possession has fewer than ``MIN_ACTIONS``
    on-ball actions, so callers can skip trivial chains.
    """
    chain = possession_events(events, possession)
    if len(chain) < MIN_ACTIONS:
        return None

    waypoints = build_waypoints(chain)
    if len(waypoints) < 2:
        return None

    xs = [w["x"] for w in waypoints]
    ys = [w["y"] for w in waypoints]
    start_x, end_x = xs[0], xs[-1]

    times = [_event_time(row) for _, row in chain.iterrows()]
    duration = max(times) - min(times)

    net_forward = end_x - start_x
    path_length = _path_length(waypoints)
    directness = net_forward / path_length if path_length > 0 else 0.0
    # Guard the per-second rate: many actions land in the same recorded second,
    # which would otherwise blow the speed up to infinity.
    forward_speed = net_forward / duration if duration >= 1.0 else net_forward

    return {
        "duration": float(duration),
        "n_actions": int(len(chain)),
        "n_passes": int((chain["type"] == "Pass").sum()),
        "start_x": float(start_x),
        "net_forward": float(net_forward),
        "path_length": float(path_length),
        "directness": float(directness),
        "forward_speed": float(forward_speed),
        "width": float(max(ys) - min(ys)),
        "ends_in_shot": int((chain["type"] == "Shot").any()),
    }


def build_possession_frame(events):
    """Feature table for every non-trivial possession in a match's events.

    Returns a list of feature dicts, each tagged with its ``possession`` id and
    ``match_id`` so a possession can be traced back to its events for replay.
    """
    import pandas as pd  # local import keeps the pure helpers dependency-light

    match_id = events["match_id"].iloc[0] if "match_id" in events.columns else None
    rows = []
    for possession in events["possession"].dropna().unique():
        feats = possession_features(events, possession)
        if feats is None:
            continue
        feats["possession"] = int(possession)
        feats["match_id"] = int(match_id) if match_id is not None else None
        rows.append(feats)
    return pd.DataFrame(rows)
