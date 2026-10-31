"""The shared leaderboard for the predict-and-compare quiz.

A quiz session scores the user against the trained model with the Brier rule
(``quiz.py``). This module keeps a high-score table across sessions so a player
can see how their intuition ranks. There are no accounts: a row is keyed only by
whatever name the player types.

Players are ranked by their **average points per round**, which is fair across
sessions of different lengths, and must have played at least ``MIN_ROUNDS`` to
qualify so a single lucky guess cannot top the board. The margin over the model
(how many points per round the player beat the model's own estimate by) is kept
too, as a tie-break and a talking point.

Where the rows live depends on the environment (``get_store``). The deployed app
sets ``SUPABASE_URL`` and ``SUPABASE_KEY`` and keeps them in a Postgres table
(``supabase/leaderboard.sql``), which survives restarts and redeploys. Without
them, a JSON file on disk is used, which is all a local run needs. Both stores
take the same rows, and the ranking logic here is pure, so everything but the
HTTP call is unit tested.
"""

import json
import logging
import os
import re
import threading
import time
import unicodedata
from collections import deque
from datetime import datetime, timezone
from pathlib import Path

import requests

log = logging.getLogger(__name__)

DATA_DIR = Path(__file__).resolve().parents[2] / "data"
LEADERBOARD_PATH = DATA_DIR / "leaderboard.json"

# Rounds a player must complete before their score is ranked.
MIN_ROUNDS = 5

# The board is shared by everyone using a deployed app, so names are cleaned
# and the file is capped: only the best MAX_ENTRIES rows are kept on disk.
MAX_NAME = 20
MAX_ENTRIES = 200

# Saves allowed across the whole app per minute. A refreshed page is a new game,
# so one save per game alone doesn't stop someone filling the board.
SAVES_PER_MINUTE = 10

# Fields a row carries, in both stores.
FIELDS = ("name", "rounds", "avg_points", "model_avg", "vs_model", "date")


class LeaderboardError(RuntimeError):
    """A score could not be saved (rate limited, or the store is unreachable)."""


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
    """Write the board in one step: a reader never sees a half-written file."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(scores, indent=2), encoding="utf-8")
    os.replace(tmp, path)


# Every visitor's session runs in its own thread of one process, so two saves can
# land at once; the lock stops one overwriting the other's row.
_file_lock = threading.Lock()


def add_score(entry: dict, path: Path = LEADERBOARD_PATH, max_entries: int = MAX_ENTRIES) -> list:
    """Add one entry to the saved board and return the updated list.

    Only the best ``max_entries`` qualifying rows are kept (see ``ranked``), so
    the file cannot grow without bound however many scores are submitted.
    """
    with _file_lock:
        scores = sorted(load_scores(path) + [entry], key=_rank_key, reverse=True)[:max_entries]
        save_scores(scores, path)
    return scores


class RateLimiter:
    """At most ``limit`` events in any ``window`` seconds, across all sessions."""

    def __init__(self, limit: int, window: float = 60.0, clock=time.monotonic):
        self.limit, self.window, self.clock = limit, window, clock
        self._times: deque = deque()
        self._lock = threading.Lock()

    def allow(self) -> bool:
        with self._lock:
            now = self.clock()
            while self._times and now - self._times[0] >= self.window:
                self._times.popleft()
            if len(self._times) >= self.limit:
                return False
            self._times.append(now)
            return True


class FileStore:
    """The board as a JSON file on disk, for local runs."""

    name = "file"

    def __init__(self, path: Path = LEADERBOARD_PATH):
        self.path = Path(path)

    def load(self) -> list:
        return load_scores(self.path)

    def add(self, entry: dict) -> None:
        add_score(entry, self.path)


class SupabaseStore:
    """The board as a Postgres table behind Supabase's REST API.

    The key is the project's publishable (anon) key. It only ever lives on the
    server, and the table's row-level security lets it read and insert, never
    change or delete, so even a leaked key can't rewrite the board.
    """

    name = "supabase"
    TIMEOUT = 5

    def __init__(self, url: str, key: str, session=None):
        self.endpoint = url.rstrip("/") + "/rest/v1/leaderboard"
        self.headers = {"apikey": key}
        if not key.startswith("sb_"):  # a legacy anon key is a JWT, sent as a bearer token too
            self.headers["Authorization"] = f"Bearer {key}"
        self.http = session or requests.Session()

    def load(self) -> list:
        params = {
            "select": ",".join(FIELDS),
            "rounds": f"gte.{MIN_ROUNDS}",
            "order": "avg_points.desc,vs_model.desc,rounds.desc",
            "limit": str(MAX_ENTRIES),
        }
        response = self.http.get(self.endpoint, params=params, headers=self.headers, timeout=self.TIMEOUT)
        response.raise_for_status()
        return response.json()

    def add(self, entry: dict) -> None:
        row = {k: entry[k] for k in FIELDS}
        headers = {**self.headers, "Prefer": "return=minimal"}
        response = self.http.post(self.endpoint, json=row, headers=headers, timeout=self.TIMEOUT)
        response.raise_for_status()


def get_store(env=os.environ):
    """Supabase when the deployment provides its URL and key, else the local file."""
    url, key = env.get("SUPABASE_URL"), env.get("SUPABASE_KEY")
    return SupabaseStore(url, key) if url and key else FileStore()


_saves = RateLimiter(SAVES_PER_MINUTE)


def board(store) -> list | None:
    """The saved rows, or None if the store can't be reached right now."""
    try:
        return store.load()
    except (requests.RequestException, ValueError) as err:
        log.warning("Leaderboard unavailable from %s store: %s", store.name, err)
        return None


def save(store, entry: dict, limiter: RateLimiter = _saves) -> None:
    """Save a row, or raise ``LeaderboardError`` with a message for the player."""
    if not limiter.allow():
        log.warning("Leaderboard save rate limited")
        raise LeaderboardError("Lots of scores are being saved right now. Try again in a minute.")
    try:
        store.add(entry)
    except (requests.RequestException, OSError) as err:
        log.error("Leaderboard save to %s store failed: %s", store.name, err)
        raise LeaderboardError("The leaderboard can't be reached right now. Try again shortly.") from err
    log.info("Leaderboard score saved to %s store (%s rounds)", store.name, entry["rounds"])


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
