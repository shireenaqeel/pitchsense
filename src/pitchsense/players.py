"""Aggregate a player's events into a behavioural feature vector.

Player-role clustering groups players by *how they play* rather than the position
they are listed at: average position on the pitch, how much they roam, the share
of their actions that are passes / carries / dribbles / shots / defending, how
forward and how long their passing is. All features are scale-free (shares,
averages), so a player who featured in many matches is comparable to one who
featured in few without needing exact minutes played.

The nominal ``position`` StatsBomb records is deliberately *not* a clustering
feature — it is kept only to label and validate the discovered clusters. StatsBomb
orients every team's coordinates so it attacks toward x=120, so a larger average x
means a more attacking player and a ``pass_angle`` near 0 is a forward pass. These
helpers are pure so they can be unit tested without any network access.
"""

import numpy as np
import pandas as pd

# A player needs at least this many recorded events across the dataset for their
# behavioural shares to be stable rather than noise from a cameo.
MIN_EVENTS = 300

# Event types counted as a defensive action.
DEFENSIVE_TYPES = {
    "Pressure", "Duel", "Interception", "Block", "Clearance", "Ball Recovery", "50/50",
}

PLAYER_FEATURES = [
    "avg_x",             # mean pitch x of the player's actions (advancement, 0-120)
    "lateral",           # mean |y - 40|: how wide of centre they operate
    "x_spread",          # std of x: how much they roam up/down the pitch
    "y_spread",          # std of y: how much they roam side to side
    "pass_share",        # passes as a share of all actions
    "forward_pass_ratio",# share of passes played forward
    "avg_pass_length",   # mean pass length
    "cross_share",       # crosses as a share of passes
    "carry_share",       # carries as a share of all actions
    "dribble_share",     # dribbles as a share of all actions
    "shot_share",        # shots as a share of all actions
    "defensive_share",   # defensive actions as a share of all actions
]

# StatsBomb position name -> coarse role group, used only for labelling clusters.
_POSITION_RULES = [
    ("Goalkeeper", "Goalkeeper"),
    ("Wing Back", "Full-back"),
    ("Back", "Centre-back"),       # remaining "*Back" after wing-backs: full/centre
    ("Defensive Midfield", "Defensive mid"),
    ("Attacking Midfield", "Attacking mid"),
    ("Wing", "Winger"),
    ("Forward", "Forward"),
    ("Striker", "Forward"),
    ("Midfield", "Central mid"),
]

# "Right Back" / "Left Back" are full-backs; "Center Back" is a centre-back.
_FULLBACK_HINTS = ("Right Back", "Left Back")


def position_group(position) -> str:
    """Map a StatsBomb position name to a coarse role group."""
    if not isinstance(position, str) or not position:
        return "Unknown"
    if position in _FULLBACK_HINTS:
        return "Full-back"
    for needle, group in _POSITION_RULES:
        if needle in position:
            return group
    return "Unknown"


def _locations(events: pd.DataFrame):
    """x and y series for events that carry a valid location, else NaN."""
    def coord(p, i):
        if isinstance(p, (list, np.ndarray)) and len(p) >= 2:
            return float(p[i])
        return np.nan
    x = events["location"].apply(lambda p: coord(p, 0))
    y = events["location"].apply(lambda p: coord(p, 1))
    return x, y


def player_raw_aggregates(events: pd.DataFrame) -> pd.DataFrame:
    """Per-player raw sums for one match's events.

    Returns count/sum columns (not ratios) so several matches can be pooled by
    simple addition before the scale-free features are computed. Each player's
    modal position in the match is kept for later labelling.
    """
    df = events.copy()
    x, y = _locations(df)
    df["_x"], df["_y"] = x, y
    df["_absy"] = (y - 40.0).abs()
    df["_has_loc"] = x.notna().astype(int)

    is_pass = df["type"] == "Pass"
    angle = df["pass_angle"] if "pass_angle" in df.columns else pd.Series(np.nan, index=df.index)
    cross = df["pass_cross"] if "pass_cross" in df.columns else pd.Series(False, index=df.index)
    length = df["pass_length"] if "pass_length" in df.columns else pd.Series(np.nan, index=df.index)

    df["_is_pass"] = is_pass.astype(int)
    df["_is_fwd"] = (is_pass & (angle.abs() < np.pi / 2)).astype(int)
    df["_pass_len"] = length.where(is_pass, 0.0).fillna(0.0)
    df["_is_cross"] = (is_pass & cross.fillna(False).astype(bool)).astype(int)
    df["_is_carry"] = (df["type"] == "Carry").astype(int)
    df["_is_dribble"] = (df["type"] == "Dribble").astype(int)
    df["_is_shot"] = (df["type"] == "Shot").astype(int)
    df["_is_def"] = df["type"].isin(DEFENSIVE_TYPES).astype(int)

    rows = []
    for player_id, g in df[df["player_id"].notna()].groupby("player_id"):
        pos = g["position"].mode()
        rows.append({
            "player_id": int(player_id),
            "player": g["player"].iloc[0],
            "position": pos.iat[0] if not pos.empty else None,
            "n_events": int(len(g)),
            "n_loc": int(g["_has_loc"].sum()),
            "sum_x": float(np.nansum(g["_x"])),
            "sum_absy": float(np.nansum(g["_absy"])),
            "sumsq_x": float(np.nansum(g["_x"] ** 2)),
            "sumsq_y": float(np.nansum(g["_y"] ** 2)),
            "sum_y": float(np.nansum(g["_y"])),
            "n_passes": int(g["_is_pass"].sum()),
            "n_fwd": int(g["_is_fwd"].sum()),
            "sum_pass_len": float(g["_pass_len"].sum()),
            "n_cross": int(g["_is_cross"].sum()),
            "n_carry": int(g["_is_carry"].sum()),
            "n_dribble": int(g["_is_dribble"].sum()),
            "n_shot": int(g["_is_shot"].sum()),
            "n_def": int(g["_is_def"].sum()),
        })
    return pd.DataFrame(rows)


_SUM_COLUMNS = [
    "n_events", "n_loc", "sum_x", "sum_absy", "sumsq_x", "sumsq_y", "sum_y",
    "n_passes", "n_fwd", "sum_pass_len", "n_cross", "n_carry", "n_dribble",
    "n_shot", "n_def",
]


def combine_aggregates(raw: pd.DataFrame) -> pd.DataFrame:
    """Pool per-match raw aggregates into one row per player (summed counts).

    A player's label position is taken from the match in which they had the most
    events, so the nominal position reflects where they mostly played.
    """
    if raw.empty:
        return raw
    summed = raw.groupby("player_id")[_SUM_COLUMNS].sum()
    main_pos = (
        raw.sort_values("n_events")
        .groupby("player_id")
        .agg(player=("player", "last"), position=("position", "last"))
    )
    return main_pos.join(summed).reset_index()


def _std(sumsq, s, n):
    if n <= 0:
        return 0.0
    var = sumsq / n - (s / n) ** 2
    return float(np.sqrt(var)) if var > 0 else 0.0


def finalize_features(pooled: pd.DataFrame, min_events: int = MIN_EVENTS) -> pd.DataFrame:
    """Turn pooled raw counts into the scale-free behavioural feature table.

    Players below ``min_events`` are dropped as too small a sample.
    """
    df = pooled[pooled["n_events"] >= min_events].copy()

    n = df["n_events"]
    nl = df["n_loc"].replace(0, np.nan)
    npass = df["n_passes"].replace(0, np.nan)

    df["avg_x"] = (df["sum_x"] / nl).fillna(0.0)
    df["lateral"] = (df["sum_absy"] / nl).fillna(0.0)
    df["x_spread"] = [
        _std(sq, s, k) for sq, s, k in zip(df["sumsq_x"], df["sum_x"], df["n_loc"])
    ]
    df["y_spread"] = [
        _std(sq, s, k) for sq, s, k in zip(df["sumsq_y"], df["sum_y"], df["n_loc"])
    ]
    df["pass_share"] = df["n_passes"] / n
    df["forward_pass_ratio"] = (df["n_fwd"] / npass).fillna(0.0)
    df["avg_pass_length"] = (df["sum_pass_len"] / npass).fillna(0.0)
    df["cross_share"] = (df["n_cross"] / npass).fillna(0.0)
    df["carry_share"] = df["n_carry"] / n
    df["dribble_share"] = df["n_dribble"] / n
    df["shot_share"] = df["n_shot"] / n
    df["defensive_share"] = df["n_def"] / n

    df["position_group"] = df["position"].apply(position_group)
    keep = ["player_id", "player", "position", "position_group", "n_events"] + PLAYER_FEATURES
    return df[keep].reset_index(drop=True)
