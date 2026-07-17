"""Load shot-level event data from StatsBomb open data.

The raw event API is slow and rate-limited, so the assembled shot frame is
cached on disk as a parquet file. Delete the cache to force a refresh.

Training spans several major men's international tournaments (see
``COMPETITIONS``) rather than a single one: a larger, more varied shot sample
gives a better-calibrated xG model and enough data for the gradient-boosted model
to compete with the linear baseline. They are all national-team knockout
tournaments with full event data and shot freeze-frames, so they are stylistically
comparable and share the same feature coverage.
"""

from pathlib import Path

import pandas as pd
from statsbombpy import sb

# (competition_id, season_id) for each tournament in the training set.
COMPETITIONS = [
    (43, 3),     # FIFA World Cup 2018
    (43, 106),   # FIFA World Cup 2022
    (55, 43),    # UEFA Euro 2020
    (55, 282),   # UEFA Euro 2024
]

# A single representative competition, for callers that only need one match (the
# example replay picks its goal from here). Defaults to the first tournament.
COMPETITION_ID, SEASON_ID = COMPETITIONS[0]

DATA_DIR = Path(__file__).resolve().parents[2] / "data"
SHOTS_CACHE = DATA_DIR / "shots.parquet"

# Columns we keep from the raw event frame. Missing ones are filled later.
SHOT_COLUMNS = [
    "id",
    "match_id",
    "team",
    "player",
    "minute",
    "location",
    "shot_end_location",
    "play_pattern",
    "under_pressure",
    "shot_body_part",
    "shot_technique",
    "shot_type",
    "shot_outcome",
    "shot_first_time",
    "shot_one_on_one",
    "shot_freeze_frame",
    "shot_key_pass_id",
    "shot_statsbomb_xg",
    # Attributes of the assisting pass, joined in during the fetch below.
    "assist_cross",
    "assist_cutback",
    "assist_through_ball",
]

# Pass-event boolean fields describing the type of the assisting pass.
_ASSIST_FIELDS = {
    "assist_cross": "pass_cross",
    "assist_cutback": "pass_cut_back",
    "assist_through_ball": "pass_through_ball",
}


def _attach_assist_features(shots: pd.DataFrame, events: pd.DataFrame) -> pd.DataFrame:
    """Join the type of each shot's assisting pass onto the shot row.

    A shot links to the pass that created it via ``shot_key_pass_id`` (the pass
    event's id). We look that pass up and copy across whether it was a cross,
    cutback, or through ball. Shots with no key pass get zeros.
    """
    passes = events[events["type"] == "Pass"].set_index("id")
    for out_col, pass_col in _ASSIST_FIELDS.items():
        if pass_col in passes.columns:
            lookup = passes[pass_col].fillna(False).astype(int)
            shots[out_col] = shots["shot_key_pass_id"].map(lookup).fillna(0).astype(int)
        else:
            shots[out_col] = 0
    return shots


def all_match_ids() -> list:
    """Every match id across the configured competitions."""
    ids = []
    for competition_id, season_id in COMPETITIONS:
        matches = sb.matches(competition_id=competition_id, season_id=season_id)
        ids.extend(matches["match_id"].tolist())
    return ids


def shots_from_events(events: pd.DataFrame, match_id) -> pd.DataFrame:
    """Extract one match's shot rows (with assist features) as ``SHOT_COLUMNS``.

    Shared by the shots loader and the single-pass cache builder so the shot
    assembly logic lives in exactly one place.
    """
    shots = events[events["type"] == "Shot"].copy()
    shots["match_id"] = match_id
    if "shot_key_pass_id" not in shots.columns:
        shots["shot_key_pass_id"] = pd.NA
    shots = _attach_assist_features(shots, events)
    for col in SHOT_COLUMNS:
        if col not in shots.columns:
            shots[col] = pd.NA
    return shots[SHOT_COLUMNS]


def _fetch_shots() -> pd.DataFrame:
    frames = []
    for match_id in all_match_ids():
        events = sb.events(match_id=match_id)
        frames.append(shots_from_events(events, match_id))
    return pd.concat(frames, ignore_index=True)


def load_shots(use_cache: bool = True) -> pd.DataFrame:
    """Return all World Cup 2018 shots as a DataFrame, using the disk cache."""
    if use_cache and SHOTS_CACHE.exists():
        return pd.read_parquet(SHOTS_CACHE)

    shots = _fetch_shots()
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    shots.to_parquet(SHOTS_CACHE, index=False)
    return shots


if __name__ == "__main__":
    df = load_shots()
    print(f"Loaded {len(df)} shots from {df['match_id'].nunique()} matches")
    print(f"Goals: {(df['shot_outcome'] == 'Goal').sum()}")
