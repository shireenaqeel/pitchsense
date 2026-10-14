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

# Effectiveness and discipline stats. These are deliberately *not* clustering
# features: roles describe how a player plays, while these describe how well and
# how cleanly, and are scored against role peers in ``ratings.py``.
PLAYER_STATS = [
    "pass_completion",   # completed passes / attempted passes
    "dribble_success",   # completed dribbles / attempted dribbles
    "tackle_win",        # tackles won / tackles attempted
    "fouls_per100",      # fouls committed per 100 actions
    "cards_per100",      # card points (yellow 1, second yellow 2, red 3) per 100 actions
    "fouls_won_per100",  # fouls drawn per 100 actions
]

# Pass outcomes that say nothing about the passer's accuracy, excluded from attempts.
_UNSCORED_PASS_OUTCOMES = {"Unknown", "Injury Clearance"}
# Duel outcomes that count as a won tackle.
_TACKLE_WON = {"Won", "Success", "Success In Play", "Success Out"}
CARD_POINTS = {"Yellow Card": 1, "Second Yellow": 2, "Red Card": 3}

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


def _col(df: pd.DataFrame, name: str, default=np.nan) -> pd.Series:
    """A column of the event frame, or a constant series when the match lacks it."""
    return df[name] if name in df.columns else pd.Series(default, index=df.index)


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

    pass_outcome = _col(df, "pass_outcome")
    df["_pass_att"] = (is_pass & ~pass_outcome.isin(_UNSCORED_PASS_OUTCOMES)).astype(int)
    df["_pass_cmp"] = (is_pass & pass_outcome.isna()).astype(int)
    df["_drib_cmp"] = (df["_is_dribble"].astype(bool)
                       & (_col(df, "dribble_outcome") == "Complete")).astype(int)
    is_tackle = (df["type"] == "Duel") & (_col(df, "duel_type") == "Tackle")
    df["_tackle"] = is_tackle.astype(int)
    df["_tackle_won"] = (is_tackle & _col(df, "duel_outcome").isin(_TACKLE_WON)).astype(int)
    df["_foul"] = (df["type"] == "Foul Committed").astype(int)
    df["_foul_won"] = (df["type"] == "Foul Won").astype(int)
    df["_card_pts"] = (_col(df, "foul_committed_card").map(CARD_POINTS).fillna(0)
                       + _col(df, "bad_behaviour_card").map(CARD_POINTS).fillna(0))

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
            "n_pass_att": int(g["_pass_att"].sum()),
            "n_pass_cmp": int(g["_pass_cmp"].sum()),
            "n_drib_cmp": int(g["_drib_cmp"].sum()),
            "n_tackle": int(g["_tackle"].sum()),
            "n_tackle_won": int(g["_tackle_won"].sum()),
            "n_foul": int(g["_foul"].sum()),
            "n_foul_won": int(g["_foul_won"].sum()),
            "card_points": int(g["_card_pts"].sum()),
        })
    return pd.DataFrame(rows)


_SUM_COLUMNS = [
    "n_events", "n_loc", "sum_x", "sum_absy", "sumsq_x", "sumsq_y", "sum_y",
    "n_passes", "n_fwd", "sum_pass_len", "n_cross", "n_carry", "n_dribble",
    "n_shot", "n_def", "n_pass_att", "n_pass_cmp", "n_drib_cmp", "n_tackle",
    "n_tackle_won", "n_foul", "n_foul_won", "card_points",
]


def combine_aggregates(raw: pd.DataFrame) -> pd.DataFrame:
    """Pool per-match raw aggregates into one row per player (summed counts).

    A player's label position is taken from the match in which they had the most
    events, so the nominal position reflects where they mostly played.
    """
    if raw.empty:
        return raw
    # Caches built before the effectiveness stats existed lack those columns.
    raw = raw.assign(**{c: 0 for c in _SUM_COLUMNS if c not in raw.columns})
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

    def ratio(num, den):
        return (df[num] / df[den].replace(0, np.nan)).astype(float)

    df["pass_completion"] = ratio("n_pass_cmp", "n_pass_att")
    df["dribble_success"] = ratio("n_drib_cmp", "n_dribble")
    df["tackle_win"] = ratio("n_tackle_won", "n_tackle")
    df["fouls_per100"] = 100 * df["n_foul"] / n
    df["cards_per100"] = 100 * df["card_points"] / n
    df["fouls_won_per100"] = 100 * df["n_foul_won"] / n

    df["position_group"] = df["position"].apply(position_group)
    keep = (["player_id", "player", "position", "position_group", "n_events",
             "n_dribble", "n_tackle", "n_foul", "card_points"]
            + PLAYER_FEATURES + PLAYER_STATS)
    return df[keep].reset_index(drop=True)
