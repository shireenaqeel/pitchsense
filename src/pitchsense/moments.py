"""Real decision moments for the game's "What happens next?" mode.

A moment is one touch in the final third of a real tournament match: where the
ball is, where every player the 360 camera could see is standing, how the move
got there, and what the player on the ball actually did next (shot, pass, cross
or dribble), followed by how the move ended. The player sees the picture and
calls the decision before the real one plays out.

Only tournaments with StatsBomb 360 data qualify (``COMPETITIONS_360``): plain
event data has no positions away from shots. A 360 frame is limited to the
broadcast camera's view, but the camera follows the ball, so the players around
the decision are the ones in shot.

Raw events and frames are fetched once from the StatsBomb open-data repository
into ``RAW_DIR`` (git-ignored), and the chosen moments are cached in
``MOMENTS_CACHE``, which is committed so the game export never touches the
network. Everything between the fetch and the cache is a pure function of the
raw JSON, so it is unit tested without network access.
"""

import json
import random
import urllib.request
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pandas as pd

DATA_DIR = Path(__file__).resolve().parents[2] / "data"
RAW_DIR = DATA_DIR / "raw360"
MOMENTS_CACHE = DATA_DIR / "moments.parquet"
OPEN_DATA = "https://raw.githubusercontent.com/statsbomb/open-data/master/data"

# The tournaments in ``data.COMPETITIONS`` that have 360 frames.
COMPETITIONS_360 = [
    (43, 106),   # FIFA World Cup 2022
    (55, 43),    # UEFA Euro 2020
    (55, 282),   # UEFA Euro 2024
]

# The four calls a player can make, in the order the game shows them.
CHOICES = ["shoot", "pass", "cross", "dribble"]

# A decision has to be in the final third, where all four calls are real options.
MIN_X = 80.0
# A carry shorter than this is just taking a touch, not a dribble.
MIN_DRIBBLE = 5.0
# Players the camera must see, besides the one on the ball, for a usable picture.
MIN_VISIBLE = 4
# Ball waypoints shown before the decision, and after it.
LEAD_UP = 4
AFTERMATH = 5

# How many moments of each call the cache keeps. Shots and passes are the most
# common calls, but an even spread keeps the quiz from being "always pass".
QUOTA = {"shoot": 110, "pass": 110, "cross": 90, "dribble": 90}

# Frame player kinds (the same codes as the game's shot frames, plus the actor).
OPPONENT, TEAMMATE, KEEPER, ACTOR = 0, 1, 2, 3

# Pitch zones for "what players usually do from here": edges along x (towards
# goal) and y (across). Central and wide channels, box edge, inside the box.
ZONE_X = [80, 96, 102, 108, 114, 120.1]
ZONE_Y = [0, 18, 30, 50, 62, 80.1]


# --------------------------------------------------------------------------- #
# Fetch
# --------------------------------------------------------------------------- #
def _get_json(url: str):
    with urllib.request.urlopen(url, timeout=60) as response:
        return json.load(response)


def fetch_raw(competitions=COMPETITIONS_360, raw_dir: Path = RAW_DIR, workers: int = 8) -> list:
    """Download events and 360 frames for every match; return the match list.

    Files already on disk are kept, so an interrupted fetch resumes.
    """
    raw_dir.mkdir(parents=True, exist_ok=True)
    matches = []
    for competition_id, season_id in competitions:
        matches += _get_json(f"{OPEN_DATA}/matches/{competition_id}/{season_id}.json")

    def fetch(match_id: int) -> None:
        for kind in ("events", "three-sixty"):
            path = raw_dir / f"{match_id}.{kind}.json"
            if not path.exists():
                data = _get_json(f"{OPEN_DATA}/{kind}/{match_id}.json")
                path.write_text(json.dumps(data), encoding="utf-8")

    with ThreadPoolExecutor(workers) as pool:
        list(pool.map(fetch, [m["match_id"] for m in matches]))
    return matches


# --------------------------------------------------------------------------- #
# Labelling
# --------------------------------------------------------------------------- #
def _distance(a, b) -> float:
    return ((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2) ** 0.5


def decision(event: dict) -> str | None:
    """The call an open-play event represents, or None if it isn't a decision."""
    kind = event.get("type", {}).get("name")
    if kind == "Shot":
        shot = event.get("shot", {})
        return "shoot" if shot.get("type", {}).get("name") == "Open Play" else None
    if kind == "Pass":
        p = event.get("pass", {})
        if "type" in p:  # corners, free kicks, throw-ins, goal kicks, kick-offs
            return None
        return "cross" if p.get("cross") else "pass"
    if kind == "Dribble":
        return "dribble"
    if kind == "Carry":
        end = event.get("carry", {}).get("end_location")
        if end and _distance(event["location"], end) >= MIN_DRIBBLE:
            return "dribble"
    return None


def end_of(event: dict):
    """Where an on-ball event sends the ball, or None."""
    kind = event.get("type", {}).get("name")
    field = {"Pass": "pass", "Carry": "carry", "Shot": "shot"}.get(kind)
    end = event.get(field, {}).get("end_location") if field else None
    return [round(float(end[0]), 1), round(float(end[1]), 1)] if end else None


def compact_360(frame: dict) -> list:
    """``[[x, y, kind], ...]`` for a 360 frame; kind marks the actor and the keeper."""
    players = []
    for p in frame.get("freeze_frame", []):
        x, y = (round(float(v), 1) for v in p["location"][:2])
        if p.get("actor"):
            kind = ACTOR
        elif p.get("teammate"):
            kind = TEAMMATE
        elif p.get("keeper"):
            kind = KEEPER
        else:
            kind = OPPONENT
        players.append([x, y, kind])
    return players


def zone(x: float, y: float) -> int:
    """Index of the pitch zone containing (x, y), row-major over ZONE_X x ZONE_Y."""
    col = next(i for i in range(len(ZONE_Y) - 1) if y < ZONE_Y[i + 1])
    row = next(i for i in range(len(ZONE_X) - 1) if x < ZONE_X[i + 1])
    return row * (len(ZONE_Y) - 1) + col


def outcome(events: list) -> str:
    """How a move ended, from its events after the decision (in order)."""
    for e in events:
        if e.get("type", {}).get("name") == "Shot":
            result = e["shot"].get("outcome", {}).get("name", "")
            return "goal" if result == "Goal" else "shot"
    return "no shot"


def _ball_path(events: list) -> list:
    """Ball waypoints through a run of on-ball events: each start, then each end."""
    path = []
    for e in events:
        for point in (e.get("location"), end_of(e)):
            if point and (not path or _distance(path[-1], point) > 0.5):
                path.append([round(float(point[0]), 1), round(float(point[1]), 1)])
    return path


def match_moments(events: list, frames: list, match_id: int) -> list:
    """Every usable decision moment in one match, as records for the cache."""
    by_id = {f["event_uuid"]: f for f in frames}
    on_ball = ("Pass", "Carry", "Shot", "Dribble")
    moments = []
    for i, e in enumerate(events):
        call = decision(e)
        loc = e.get("location")
        frame = by_id.get(e.get("id"))
        if call is None or not loc or loc[0] < MIN_X or frame is None:
            continue
        players = compact_360(frame)
        if sum(1 for p in players if p[2] != ACTOR) < MIN_VISIBLE or not any(p[2] == ACTOR for p in players):
            continue
        same = [ev for ev in events if ev.get("possession") == e.get("possession")
                and ev.get("team", {}).get("id") == e["team"]["id"] and ev.get("type", {}).get("name") in on_ball]
        k = next(j for j, ev in enumerate(same) if ev["id"] == e["id"])
        before = _ball_path(same[max(0, k - LEAD_UP):k])
        after = _ball_path(same[k:k + AFTERMATH])
        moments.append({
            "id": e["id"],
            "match_id": match_id,
            "minute": int(e.get("minute", 0)),
            "team": e["team"]["name"],
            "player": e.get("player", {}).get("name", ""),
            "call": call,
            "x": round(float(loc[0]), 1),
            "y": round(float(loc[1]), 1),
            "frame": players,
            "before": before,
            "after": after,
            "outcome": outcome(same[k:]),
        })
    return moments


def zone_rates(moments: list) -> dict:
    """Per zone, the share of each call over every moment there (in CHOICES order)."""
    counts: dict = {}
    for m in moments:
        counts.setdefault(zone(m["x"], m["y"]), Counter())[m["call"]] += 1
    return {z: [round(c[call] / sum(c.values()), 3) for call in CHOICES] for z, c in counts.items()}


def pick(moments: list, quota: dict = QUOTA, seed: int = 7) -> list:
    """A reproducible sample with up to ``quota[call]`` moments of each call.

    Each call's moments are shuffled and taken one per match in turn, so no
    single match dominates the sample.
    """
    rng = random.Random(seed)
    chosen = []
    for call, n in quota.items():
        by_match: dict = {}
        for m in moments:
            if m["call"] == call:
                by_match.setdefault(m["match_id"], []).append(m)
        for group in by_match.values():
            rng.shuffle(group)
        order = sorted(by_match)
        rng.shuffle(order)
        taken = []
        while len(taken) < n and any(by_match[mid] for mid in order):
            for mid in order:
                if by_match[mid] and len(taken) < n:
                    taken.append(by_match[mid].pop())
        chosen += taken
    return chosen


# --------------------------------------------------------------------------- #
# Cache
# --------------------------------------------------------------------------- #
def build_moments_cache(raw_dir: Path = RAW_DIR, cache: Path = MOMENTS_CACHE) -> pd.DataFrame:
    """Fetch (if needed), label every match, sample, and write the parquet cache."""
    matches = fetch_raw(raw_dir=raw_dir)
    everything = []
    for m in matches:
        mid = m["match_id"]
        events = json.loads((raw_dir / f"{mid}.events.json").read_text(encoding="utf-8"))
        frames = json.loads((raw_dir / f"{mid}.three-sixty.json").read_text(encoding="utf-8"))
        everything += match_moments(events, frames, mid)
    rates = zone_rates(everything)
    chosen = pick(everything)
    for m in chosen:
        m["rates"] = rates[zone(m["x"], m["y"])]
    frame = pd.DataFrame(chosen)
    # Nested lists are stored as JSON text so the parquet stays schema-simple.
    for col in ("frame", "before", "after", "rates"):
        frame[col] = frame[col].map(json.dumps)
    cache.parent.mkdir(parents=True, exist_ok=True)
    frame.to_parquet(cache, index=False)
    return frame


def load_moments(cache: Path = MOMENTS_CACHE) -> list:
    """The cached moments as dicts, nested fields decoded."""
    frame = pd.read_parquet(cache)
    records = frame.to_dict("records")
    for r in records:
        for col in ("frame", "before", "after", "rates"):
            r[col] = json.loads(r[col])
    return records


if __name__ == "__main__":
    built = build_moments_cache()
    print(f"{len(built)} moments: {built['call'].value_counts().to_dict()}")
