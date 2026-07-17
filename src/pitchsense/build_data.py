"""Build every on-disk cache in a single pass over the match events.

Each of the three models draws on the same raw StatsBomb events. Fetching those
events once per model would download every match three times, so this module
walks the configured competitions once, and from each match's events assembles
the shot table, the possession table, and the player aggregates together. Run it
before training to populate the caches; the individual loaders then find their
cache and skip the network entirely.

    python -m pitchsense.build_data
"""

import pandas as pd

from pitchsense.data import (
    DATA_DIR,
    SHOTS_CACHE,
    all_match_ids,
    shots_from_events,
)
from pitchsense.players import (
    combine_aggregates,
    finalize_features,
    player_raw_aggregates,
)
from pitchsense.possessions import build_possession_frame
from pitchsense.roles import PLAYERS_CACHE
from pitchsense.tactics import POSSESSIONS_CACHE


def build_all_caches() -> dict:
    """Fetch every match once and write the shots, possessions, and player caches."""
    from statsbombpy import sb  # lazy import so the module stays importable offline

    match_ids = all_match_ids()
    shot_frames, possession_frames, player_frames = [], [], []

    for i, match_id in enumerate(match_ids, start=1):
        events = sb.events(match_id=match_id)
        events["match_id"] = match_id
        shot_frames.append(shots_from_events(events, match_id))
        possession_frames.append(build_possession_frame(events))
        player_frames.append(player_raw_aggregates(events))
        print(f"  [{i:>3}/{len(match_ids)}] match {match_id} processed", flush=True)

    shots = pd.concat(shot_frames, ignore_index=True)
    possessions = pd.concat(possession_frames, ignore_index=True)
    players = finalize_features(combine_aggregates(pd.concat(player_frames, ignore_index=True)))

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    shots.to_parquet(SHOTS_CACHE, index=False)
    possessions.to_parquet(POSSESSIONS_CACHE, index=False)
    players.to_parquet(PLAYERS_CACHE, index=False)

    return {"matches": len(match_ids), "shots": len(shots),
            "possessions": len(possessions), "players": len(players)}


if __name__ == "__main__":
    counts = build_all_caches()
    print(
        f"\nBuilt caches from {counts['matches']} matches: "
        f"{counts['shots']} shots, {counts['possessions']} possessions, "
        f"{counts['players']} players."
    )
