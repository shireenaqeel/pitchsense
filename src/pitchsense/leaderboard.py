"""Persistent local leaderboard for the predict-and-compare quiz.

A quiz session scores the user against the trained model with the Brier rule
(``quiz.py``). This module keeps a running high-score table across sessions so a
player can see how their intuition ranks. There are no accounts — the board is a
single JSON file on disk, keyed only by whatever name the player types — so it is
a local scoreboard, not an online one.

Players are ranked by their **average points per round**, which is fair across
sessions of different lengths, and must have played at least ``MIN_ROUNDS`` to
qualify so a single lucky guess cannot top the board. The margin over the model
(how many points per round the player beat the model's own estimate by) is kept
too, as a tie-break and a talking point. All logic here is pure and takes the
file path as an argument, so it can be unit tested against a temporary file.
"""

import json
import re
import unicodedata
from datetime import datetime, timezone
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parents[2] / "data"
LEADERBOARD_PATH = DATA_DIR / "leaderboard.json"

# Rounds a player must complete before their score is ranked.
MIN_ROUNDS = 5

# The board is shared by everyone using a deployed app, so names are cleaned
# and the file is capped: only the best MAX_ENTRIES rows are kept on disk.
MAX_NAME = 20
MAX_ENTRIES = 200


def clean_name(name: str | None) -> str:
    """A display-safe name: no control or invisible characters, single spaces,
    at most ``MAX_NAME`` characters, "Anonymous" if nothing is left."""
    text = unicodedata.normalize("NFKC", name or "")
    text = "".join(ch for ch in text if unicodedata.category(ch)[0] not in "CZ" or ch == " ")
    text = re.sub(r"\s+", " ", text).strip()[:MAX_NAME].strip()
    return text or "Anonymous"


def make_entry(name: str, total_points: int, model_points: int, rounds: int,
               when: datetime | None = None) -> dict:
    """Build a leaderboard row from a session's running totals.

    ``total_points`` / ``model_points`` are the summed Brier points over
    ``rounds`` rounds for the player and the model respectively. Averages and the
    margin over the model are precomputed so ranking and display need no division.
    """
    if rounds < 1:
        raise ValueError("a leaderboard entry needs at least one round")
    name = clean_name(name)
    when = when or datetime.now(timezone.utc)
    avg_points = total_points / rounds
    model_avg = model_points / rounds
    return {
        "name": name,
        "rounds": int(rounds),
        "avg_points": round(avg_points, 2),
        "model_avg": round(model_avg, 2),
        "vs_model": round(avg_points - model_avg, 2),
        "date": when.date().isoformat(),
    }


def load_scores(path: Path = LEADERBOARD_PATH) -> list:
    """Return the saved entries, or an empty list if there are none.

    A missing or unreadable file yields an empty board rather than an error, so a
    hand-edited or first-run file never crashes the app.
    """
    path = Path(path)
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []
    return data if isinstance(data, list) else []


def save_scores(scores: list, path: Path = LEADERBOARD_PATH) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(scores, indent=2), encoding="utf-8")


def add_score(entry: dict, path: Path = LEADERBOARD_PATH, max_entries: int = MAX_ENTRIES) -> list:
    """Add one entry to the saved board and return the updated list.

    Only the best ``max_entries`` qualifying rows are kept (see ``ranked``), so
    the file cannot grow without bound however many scores are submitted.
    """
    scores = sorted(load_scores(path) + [entry], key=_rank_key, reverse=True)[:max_entries]
    save_scores(scores, path)
    return scores


def _rank_key(s: dict) -> tuple:
    return (s.get("avg_points", 0), s.get("vs_model", 0), s.get("rounds", 0))


def ranked(scores: list, min_rounds: int = MIN_ROUNDS) -> list:
    """Qualifying entries, best first.

    Sorted by average points per round, then by the margin over the model, then by
    rounds played, so a higher, model-beating, more-tested score ranks above a
    thinner one.
    """
    qualifying = [s for s in scores if s.get("rounds", 0) >= min_rounds]
    return sorted(qualifying, key=_rank_key, reverse=True)


def top(scores: list, n: int = 10, min_rounds: int = MIN_ROUNDS) -> list:
    """The best ``n`` qualifying entries."""
    return ranked(scores, min_rounds)[:n]
