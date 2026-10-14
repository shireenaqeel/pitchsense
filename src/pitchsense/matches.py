"""Match context and player display names, so every shot comes with a story.

A freeze-frame on its own is anonymous dots. Knowing it was *Neymar, Brazil vs
Belgium, World Cup 2018 quarter-final, 76th minute* is what makes a learner care
about the answer. StatsBomb's match listing gives the teams, score, stage and
date; each match's lineups give players' common nicknames ("Neymar" rather than
"Neymar da Silva Santos Júnior"). Both are fetched once and cached.

The formatting helpers are pure so they can be unit tested without the network.

    python -m pitchsense.matches
"""

import pandas as pd

from pitchsense.data import COMPETITIONS, DATA_DIR

MATCHES_CACHE = DATA_DIR / "matches.parquet"
NAMES_CACHE = DATA_DIR / "player_names.parquet"

MATCH_COLUMNS = [
    "match_id", "match_date", "competition", "season", "competition_stage",
    "home_team", "away_team", "home_score", "away_score",
]


def tournament_label(competition: str, season: str) -> str:
    """Short tournament name, e.g. 'World Cup 2018' or 'Euro 2024'.

    StatsBomb prefixes the region ('International - FIFA World Cup'), so match on
    the part after the dash.
    """
    name = competition.split(" - ")[-1]
    short = {"FIFA World Cup": "World Cup", "UEFA Euro": "Euro"}.get(name, name)
    return f"{short} {season}"


def stage_label(stage: str) -> str:
    """Friendlier stage name: 'Quarter-finals' -> 'quarter-final', 'Final' -> 'final'."""
    if not isinstance(stage, str) or not stage:
        return ""
    return {
        "Quarter-finals": "quarter-final",
        "Semi-finals": "semi-final",
        "3rd Place Final": "third-place play-off",
    }.get(stage, stage.lower())


def opponent(match: dict, team: str) -> str:
    """The team the shooting side was playing against."""
    return match["away_team"] if match["home_team"] == team else match["home_team"]


def scoreline(match: dict) -> str:
    """Final score as 'Brazil 1–2 Belgium'."""
    return (f"{match['home_team']} {int(match['home_score'])}–"
            f"{int(match['away_score'])} {match['away_team']}")


def ordinal(n: int) -> str:
    """1 -> '1st', 2 -> '2nd', 11 -> '11th', 23 -> '23rd'."""
    if 10 <= n % 100 <= 20:
        suffix = "th"
    else:
        suffix = {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suffix}"


def shot_headline(shot, match: dict | None, display_name: str | None = None) -> str:
    """One-line story for a shot, e.g. 'Neymar · Brazil vs Belgium · 76th minute'."""
    name = display_name or shot.get("player", "Unknown player")
    team = shot.get("team", "")
    minute = int(shot.get("minute", 0)) + 1  # StatsBomb minutes are zero-based
    if match is None:
        return f"{name} · {team} · {ordinal(minute)} minute"
    return f"{name} · {team} vs {opponent(match, team)} · {ordinal(minute)} minute"


def match_subtitle(match: dict | None, include_score: bool = True) -> str:
    """Tournament and stage, plus the final score unless it would spoil a quiz.

    e.g. 'World Cup 2018 quarter-final · final score Brazil 1–2 Belgium'.
    """
    if match is None:
        return ""
    stage = stage_label(match.get("competition_stage", ""))
    text = f"{tournament_label(match['competition'], match['season'])} {stage}".strip()
    return f"{text} · final score {scoreline(match)}" if include_score else text


def build_name_map(lineups: pd.DataFrame) -> dict:
    """Full StatsBomb name -> the name fans know (the nickname when there is one)."""
    names = {}
    for full, nick in zip(lineups["player_name"], lineups["player_nickname"]):
        names[full] = nick if isinstance(nick, str) and nick else full
    return names


def _fetch():
    from statsbombpy import sb  # lazy import so the module stays importable offline

    match_frames, lineup_frames = [], []
    for competition_id, season_id in COMPETITIONS:
        matches = sb.matches(competition_id=competition_id, season_id=season_id)
        match_frames.append(matches[MATCH_COLUMNS])
        for match_id in matches["match_id"]:
            for team_lineup in sb.lineups(match_id=match_id).values():
                lineup_frames.append(team_lineup[["player_name", "player_nickname"]])
    matches = pd.concat(match_frames, ignore_index=True)
    lineups = pd.concat(lineup_frames, ignore_index=True).drop_duplicates("player_name")
    return matches, lineups


def build_caches() -> tuple[int, int]:
    """Fetch match metadata and player names, and write both caches."""
    matches, lineups = _fetch()
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    matches.to_parquet(MATCHES_CACHE, index=False)
    lineups.to_parquet(NAMES_CACHE, index=False)
    return len(matches), len(lineups)


def load_matches() -> dict:
    """match_id -> match dict, or an empty dict if the cache has not been built."""
    if not MATCHES_CACHE.exists():
        return {}
    frame = pd.read_parquet(MATCHES_CACHE)
    return {int(row["match_id"]): row for row in frame.to_dict("records")}


def load_name_map() -> dict:
    """Full name -> display name, or an empty dict if the cache has not been built."""
    if not NAMES_CACHE.exists():
        return {}
    return build_name_map(pd.read_parquet(NAMES_CACHE))


if __name__ == "__main__":
    n_matches, n_players = build_caches()
    print(f"Cached {n_matches} matches and {n_players} player names.")
