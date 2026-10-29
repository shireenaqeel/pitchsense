"""Bake the real data and the trained models into JSON for the browser game.

The game (``game/``) is a static site with no Python at runtime, so everything
it needs is computed here once: every quiz shot with its freeze-frame, the
served model's xG and chance band, post-shot xG for shots on target, and the
model's own reasons for its rating. On top of that sit the two hand-built game
structures — the career (each tournament played as the champion's road to the
trophy) and the striker puzzles (a fixed defence, and the model's xG for every
spot the striker can reach).

The game never invents a number: every probability it shows came out of a model
trained in this repo. The builders below are pure and take their inputs as
arguments, so they can be unit tested without the caches.

    python -m pitchsense.export_game
"""

import json
import math
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

from pitchsense.concepts import ALL_CONCEPTS, shot_concepts
from pitchsense.data import load_shots
from pitchsense.explain import reasons
from pitchsense.features import (
    FEATURE_COLUMNS,
    build_feature_frame,
    distance_to_goal,
    placement_from_center,
    placement_height,
)
from pitchsense.matches import load_matches, load_name_map, tournament_label
from pitchsense.moments import CHOICES, MOMENTS_CACHE, load_moments
from pitchsense.postshot import (
    ON_TARGET_OUTCOMES,
    POSTSHOT_FEATURES,
    PRIMARY_MODEL_PATH as PSXG_MODEL_PATH,
)
from pitchsense.quiz import CHANCE_BUCKETS, bucket_index
from pitchsense.sandbox import Scenario, keeper_point
from pitchsense.train import PRIMARY_MODEL_PATH

GAME_DATA_DIR = Path(__file__).resolve().parents[2] / "game" / "public" / "data"

# Career order: oldest tournament first, so the game reads as a scouting career.
CAREER_ORDER = [
    "World Cup 2018", "Euro 2020", "World Cup 2022",
    "AFCON 2023", "Copa América 2024", "Euro 2024",
]

# Finals decided on penalties end level in the match listing, so the winner
# cannot be read off the score; the champions are named instead.
CHAMPIONS = {
    "World Cup 2018": "France",
    "Euro 2020": "Italy",
    "World Cup 2022": "Argentina",
    "AFCON 2023": "Côte d'Ivoire",
    "Copa América 2024": "Argentina",
    "Euro 2024": "Spain",
}

KNOCKOUT_STAGES = ["Round of 16", "Quarter-finals", "Semi-finals", "Final"]

# A career match is a handful of real shots, not all thirty: enough for a
# story, short enough to play in two minutes.
MAX_SHOTS_PER_MATCH = 10

# Freeze-frame player kinds, as the game draws them.
OPPONENT, TEAMMATE, KEEPER = 0, 1, 2


# --------------------------------------------------------------------------- #
# Shots
# --------------------------------------------------------------------------- #
def compact_frame(freeze_frame) -> list:
    """``[[x, y, kind], ...]`` for a freeze-frame, kind = opponent/teammate/keeper.

    Only the defending goalkeeper is singled out; the shooting side's own keeper
    is a teammate dot far up the pitch and rarely in view.
    """
    players = []
    for player in freeze_frame if freeze_frame is not None else []:
        x, y = (float(v) for v in player["location"][:2])
        position = (player.get("position") or {}).get("name", "")
        if player.get("teammate"):
            kind = TEAMMATE
        elif position == "Goalkeeper":
            kind = KEEPER
        else:
            kind = OPPONENT
        players.append([round(x, 1), round(y, 1), kind])
    return players


def end_point(end_location) -> list | None:
    """``[x, y, z]`` where the shot finished, or None when StatsBomb has none."""
    if not isinstance(end_location, (list, np.ndarray)) or len(end_location) < 2:
        return None
    z = float(end_location[2]) if len(end_location) >= 3 else 0.0
    return [round(float(end_location[0]), 1), round(float(end_location[1]), 1), round(z, 2)]


def shot_record(shot, xg: float, psxg: float | None, why: dict, display_name: str) -> dict:
    """Everything the game needs to stage, score and explain one shot."""
    return {
        "id": shot["id"],
        "match": int(shot["match_id"]),
        "player": display_name,
        "team": shot["team"],
        "minute": int(shot["minute"]) + 1,  # StatsBomb minutes are zero-based
        "x": round(float(shot["x"]), 1),
        "y": round(float(shot["y"]), 1),
        "end": end_point(shot["shot_end_location"]),
        "outcome": shot["shot_outcome"],
        "goal": int(shot["is_goal"]),
        "header": int(shot["is_header"]),
        "xg": round(float(xg), 4),
        "band": bucket_index(xg),
        "psxg": None if psxg is None else round(float(psxg), 4),
        "distance": round(float(shot["distance"]), 1),
        "angleDeg": round(math.degrees(float(shot["angle"])), 1),
        "concepts": [ALL_CONCEPTS.index(c) for c in shot_concepts(shot)],
        "helped": [[factor, text] for _, factor, text in why["helped"]],
        "hurt": [[factor, text] for _, factor, text in why["hurt"]],
        "frame": compact_frame(shot["shot_freeze_frame"]),
    }


def postshot_xg(psxg_model, shots: pd.DataFrame) -> list:
    """Post-shot xG per shot, None for shots that were off target or blocked."""
    if psxg_model is None:
        return [None] * len(shots)
    rows = shots[FEATURE_COLUMNS].copy()
    rows["placement_from_center"] = shots["shot_end_location"].apply(placement_from_center)
    rows["placement_height"] = shots["shot_end_location"].apply(placement_height)
    probs = psxg_model.predict_proba(rows[POSTSHOT_FEATURES])[:, 1]
    on_target = shots["shot_outcome"].isin(ON_TARGET_OUTCOMES).to_numpy()
    return [float(p) if hit else None for p, hit in zip(probs, on_target)]


# --------------------------------------------------------------------------- #
# Career: each tournament is the champion's road to the trophy
# --------------------------------------------------------------------------- #
def pick_match_shots(minutes, goals, limit: int = MAX_SHOTS_PER_MATCH) -> list:
    """Positions of at most ``limit`` shots from a match, in match order.

    Every goal is kept (a match without its goals is not the match); the rest
    are spread evenly through the game so the story has a beginning and an end.
    """
    order = sorted(range(len(minutes)), key=lambda i: minutes[i])
    if len(order) <= limit:
        return order
    keep = [i for i in order if goals[i]][:limit]
    others = [i for i in order if not goals[i]]
    room = limit - len(keep)
    if room > 0 and others:
        picks = np.linspace(0, len(others) - 1, room).round().astype(int)
        keep += [others[p] for p in sorted(set(picks))]
    return sorted(keep, key=lambda i: minutes[i])


def champion_road(matches: list, champion: str) -> list:
    """The champion's matches in date order: ``[(stage, match dict), ...]``.

    Third-place play-offs are skipped — the champion never plays one.
    """
    road = [m for m in matches
            if champion in (m["home_team"], m["away_team"])
            and m["competition_stage"] in ["Group Stage", *KNOCKOUT_STAGES]]
    road.sort(key=lambda m: str(m["match_date"]))
    return [(m["competition_stage"], m) for m in road]


def goal_events(raw_shots: pd.DataFrame) -> dict:
    """match_id -> ``[[minute, team], ...]`` for every goal scored from a shot.

    Built from the raw shots, penalties included, so the in-game scoreboard
    ticks over for a penalty the quiz itself never asks about. Own goals are not
    shots and are missing; the final whistle shows the real score.
    """
    goals = raw_shots[raw_shots["shot_outcome"] == "Goal"].sort_values("minute")
    events = {}
    for mid, minute, team in zip(goals["match_id"], goals["minute"], goals["team"]):
        events.setdefault(int(mid), []).append([int(minute) + 1, team])
    return events


def build_career(matches_by_id: dict, shots: pd.DataFrame, goals: dict | None = None) -> list:
    """The career map: one world per tournament, one level per champion match."""
    goals = goals or {}
    by_tournament = {}
    for match in matches_by_id.values():
        label = tournament_label(match["competition"], str(match["season"]))
        by_tournament.setdefault(label, []).append(match)

    worlds = []
    for label in CAREER_ORDER:
        champion = CHAMPIONS[label]
        levels = []
        for stage, match in champion_road(by_tournament.get(label, []), champion):
            in_match = shots[shots["match_id"] == match["match_id"]]
            if in_match.empty:
                continue
            picks = pick_match_shots(in_match["minute"].tolist(), in_match["is_goal"].tolist())
            levels.append({
                "stage": stage,
                "match": int(match["match_id"]),
                "home": match["home_team"],
                "away": match["away_team"],
                "homeScore": int(match["home_score"]),
                "awayScore": int(match["away_score"]),
                "date": str(match["match_date"]),
                "boss": stage == "Final",
                "goals": goals.get(int(match["match_id"]), []),
                "shots": [in_match.iloc[p]["id"] for p in picks],
            })
        worlds.append({"name": label, "champion": champion, "levels": levels})
    return worlds


# --------------------------------------------------------------------------- #
# Striker puzzles: a fixed defence, and the xG of every spot you can reach
# --------------------------------------------------------------------------- #
# Each puzzle puts the ball at ``start`` and lets the player carry it up to
# ``reach`` yards before shooting. The defence does not move, so the puzzle is
# a real decision: drift wide for space, or drive at goal into the bodies?
# The keeper is the exception: a real keeper sets themselves on the line from
# goal to ball wherever you go, so they are placed the way the sandbox places
# them (``keeper_point``), at the puzzle's starting distance off their line. A
# keeper frozen in one spot would leave open goals the model has never seen and
# would rate absurdly high.
PUZZLES = [
    {"name": "Find the gap", "start": [96, 40], "reach": 8,
     "defenders": [[103, 37], [103, 43], [106, 40], [110, 32], [110, 48], [92, 44]]},
    {"name": "Cut inside", "start": [104, 18], "reach": 10,
     "defenders": [[108, 24], [112, 33], [110, 41], [113, 47], [100, 22]]},
    {"name": "Wide open", "start": [92, 52], "reach": 12,
     "defenders": [[104, 46], [100, 34], [109, 38], [110, 30], [88, 48]]},
    {"name": "Crowded box", "start": [100, 46], "reach": 8,
     "defenders": [[105, 44], [107, 40], [108, 36], [104, 38], [110, 44], [96, 48]]},
    {"name": "Keeper's off the line", "start": [94, 34], "reach": 10, "keeper": "Rushing out",
     "defenders": [[100, 30], [99, 40], [106, 46], [90, 30]]},
    {"name": "Byline drama", "start": [112, 62], "reach": 9,
     "defenders": [[115, 50], [113, 44], [116, 38], [108, 58], [110, 36]]},
    {"name": "Header at the back post", "start": [108, 48], "reach": 6, "header": True,
     "assist": "Cross", "defenders": [[110, 44], [111, 40], [113, 36], [112, 50]]},
    {"name": "Through ball", "start": [90, 40], "reach": 14, "assist": "Through ball",
     "defenders": [[92, 33], [93, 47], [88, 40]]},
]

PUZZLE_STEP = 1.0


def _synthetic_shot(x: float, y: float, puzzle: dict) -> dict:
    """A StatsBomb-shaped shot row at ``(x, y)`` against the puzzle's defence."""
    keeper = keeper_point(Scenario(x=x, y=y, keeper=puzzle.get("keeper", "On the line")))
    frame = [{"location": np.array(keeper, dtype=float), "teammate": False,
              "position": {"name": "Goalkeeper"}}]
    frame += [{"location": np.array(d, dtype=float), "teammate": False,
               "position": {"name": "Center Back"}} for d in puzzle["defenders"]]
    assist = puzzle.get("assist", "None")
    return {
        "id": "puzzle", "match_id": 0, "team": "You", "player": "You", "minute": 0,
        "location": np.array([x, y], dtype=float), "shot_end_location": None,
        "play_pattern": "Regular Play", "under_pressure": False,
        "shot_body_part": "Head" if puzzle.get("header") else "Right Foot",
        "shot_technique": "Normal", "shot_type": "Open Play", "shot_outcome": "Unknown",
        "shot_first_time": False, "shot_one_on_one": assist == "Through ball",
        "shot_freeze_frame": np.array(frame, dtype=object),
        "shot_key_pass_id": None, "shot_statsbomb_xg": None,
        "assist_cross": int(assist == "Cross"),
        "assist_cutback": int(assist == "Cutback"),
        "assist_through_ball": int(assist == "Through ball"),
    }


def reachable_spots(puzzle: dict, step: float = PUZZLE_STEP) -> list:
    """Grid points within ``reach`` of the start, on the pitch, and no further
    from goal than the start.

    Carrying the ball *away* from goal is ruled out on purpose: drop deep enough
    and every defender ends up goal-side, a shape the training data only shows
    as a counter-attack, so the model rates a 40-yard hopeful punt as a chance.
    """
    sx, sy = puzzle["start"]
    r = puzzle["reach"]
    start_dist = distance_to_goal(sx, sy)
    spots = []
    for x in np.arange(sx - r, sx + r + 1e-9, step):
        for y in np.arange(sy - r, sy + r + 1e-9, step):
            if (math.hypot(x - sx, y - sy) <= r and 0 < x < 119.5 and 0.5 < y < 79.5
                    and distance_to_goal(x, y) <= start_dist + 1e-9):
                spots.append((round(float(x), 1), round(float(y), 1)))
    return spots


def build_puzzle(model, puzzle: dict, step: float = PUZZLE_STEP) -> dict:
    """The puzzle plus the model's xG at every reachable spot."""
    spots = reachable_spots(puzzle, step)
    feats = build_feature_frame(pd.DataFrame([_synthetic_shot(x, y, puzzle) for x, y in spots]))
    probs = model.predict_proba(feats[FEATURE_COLUMNS])[:, 1]
    best = int(np.argmax(probs))
    return {
        **puzzle,
        "header": bool(puzzle.get("header", False)),
        "assist": puzzle.get("assist", "None"),
        "keeper": puzzle.get("keeper", "On the line"),
        "step": step,
        "spots": [[x, y, round(float(p), 4)] for (x, y), p in zip(spots, probs)],
        "best": [spots[best][0], spots[best][1], round(float(probs[best]), 4)],
    }


# --------------------------------------------------------------------------- #
# What happens next?
# --------------------------------------------------------------------------- #
def moment_record(moment: dict, display_name: str) -> dict:
    """One real decision moment as the game reads it (see ``moments.py``)."""
    return {
        "id": moment["id"],
        "match": int(moment["match_id"]),
        "minute": int(moment["minute"]),
        "player": display_name,
        "team": moment["team"],
        "call": CHOICES.index(moment["call"]),
        "x": moment["x"],
        "y": moment["y"],
        "frame": moment["frame"],
        "before": moment["before"],
        "after": moment["after"],
        "outcome": moment["outcome"],
        "rates": moment["rates"],
    }


# --------------------------------------------------------------------------- #
# Assembly
# --------------------------------------------------------------------------- #
def build_meta(matches_by_id: dict) -> dict:
    """Bands, concepts and per-match context the game shows alongside a shot."""
    return {
        "bands": [{"label": label, "emoji": emoji, "lower": lower, "p": p, "gloss": gloss}
                  for label, emoji, lower, p, gloss in CHANCE_BUCKETS],
        "concepts": ALL_CONCEPTS,
        "matches": {
            str(mid): {
                "tournament": tournament_label(m["competition"], str(m["season"])),
                "stage": m["competition_stage"],
                "home": m["home_team"], "away": m["away_team"],
                "homeScore": int(m["home_score"]), "awayScore": int(m["away_score"]),
            }
            for mid, m in matches_by_id.items()
        },
    }


def _write(name: str, payload, out_dir: Path) -> int:
    path = out_dir / name
    path.write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    return path.stat().st_size


def export(out_dir: Path = GAME_DATA_DIR) -> dict:
    """Write shots.json, career.json, puzzles.json, meta.json and moments.json; return sizes."""
    out_dir.mkdir(parents=True, exist_ok=True)
    model = joblib.load(PRIMARY_MODEL_PATH)
    psxg_model = joblib.load(PSXG_MODEL_PATH) if PSXG_MODEL_PATH.exists() else None
    matches_by_id, names = load_matches(), load_name_map()

    raw = load_shots()
    shots = build_feature_frame(raw)
    shots = shots[shots["shot_freeze_frame"].notna()].reset_index(drop=True)
    xgs = model.predict_proba(shots[FEATURE_COLUMNS])[:, 1]
    psxgs = postshot_xg(psxg_model, shots)

    records = []
    for i in range(len(shots)):
        shot = shots.iloc[i]
        records.append(shot_record(shot, xgs[i], psxgs[i], reasons(model, shot),
                                   names.get(shot["player"], shot["player"])))

    sizes = {
        "shots.json": _write("shots.json", records, out_dir),
        "career.json": _write("career.json", build_career(matches_by_id, shots, goal_events(raw)), out_dir),
        "puzzles.json": _write("puzzles.json", [build_puzzle(model, p) for p in PUZZLES], out_dir),
        "meta.json": _write("meta.json", build_meta(matches_by_id), out_dir),
    }
    if MOMENTS_CACHE.exists():
        moments = [moment_record(m, names.get(m["player"], m["player"])) for m in load_moments()]
        sizes["moments.json"] = _write("moments.json", moments, out_dir)
    return sizes


if __name__ == "__main__":
    for name, size in export().items():
        print(f"{name:14s} {size / 1024:8.1f} KB")
