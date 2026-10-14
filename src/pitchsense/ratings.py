"""Score each player's effectiveness and discipline against their role peers.

Role clustering (``roles.py``) says *how* a player plays; this module says how
*well* and how *cleanly*. The two are kept apart on purpose: folding quality into
the clustering would split roles into "good" and "bad" versions of themselves.

Every stat is turned into a percentile among players of the same detected role,
because raw numbers are not comparable across roles — a centre-back completes
far more passes than a winger simply because their passes are safer.

* **Effectiveness** — mean percentile of pass completion, dribble success, tackle
  win rate, and finishing (non-penalty goals minus the served xG model's
  expectation, per shot). A stat with too few attempts to be stable is left out
  of that player's average rather than guessed.
* **Discipline** — 100 minus the mean percentile of fouls committed and card
  points per 100 actions, so a higher score is cleaner.
* **Fouls drawn** per 100 actions is reported alongside but feeds neither score:
  being fouled is neither skill nor sportsmanship on its own.

These are transparent percentile scores, not a learned model — there is no
ground-truth "effectiveness" label in the data to train against. The scoring
helpers are pure so they can be unit tested without network or model files.

    python -m pitchsense.ratings
"""

import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

DATA_DIR = Path(__file__).resolve().parents[2] / "data"
RATINGS_CACHE = DATA_DIR / "player_ratings.parquet"
MODEL_DIR = Path(__file__).resolve().parents[2] / "models"
METRICS_PATH = MODEL_DIR / "ratings_metrics.json"

EFFECTIVENESS_STATS = ["pass_completion", "dribble_success", "tackle_win", "finishing"]
DISCIPLINE_STATS = ["fouls_per100", "cards_per100"]  # lower is better

# stat -> (attempt-count column, minimum attempts for the stat to count).
MIN_ATTEMPTS = {
    "dribble_success": ("n_dribble", 10),
    "tackle_win": ("n_tackle", 10),
    "finishing": ("n_np_shots", 10),
}


def finishing_table(shots: pd.DataFrame, xg: np.ndarray) -> pd.DataFrame:
    """Per-player non-penalty shots, goals, xG, and goals above expected per shot.

    ``shots`` is the model feature frame (penalties already dropped) and ``xg``
    the served model's probability for each of its rows.
    """
    df = pd.DataFrame({"player": shots["player"].to_numpy(),
                       "goal": shots["is_goal"].to_numpy(), "xg": np.asarray(xg)})
    out = df.groupby("player").agg(n_np_shots=("goal", "size"),
                                   np_goals=("goal", "sum"), np_xg=("xg", "sum"))
    out["finishing"] = (out["np_goals"] - out["np_xg"]) / out["n_np_shots"]
    return out.reset_index()


def mask_small_samples(df: pd.DataFrame, rules: dict = MIN_ATTEMPTS) -> pd.DataFrame:
    """Blank out stats a player has too few attempts at to be meaningful."""
    df = df.copy()
    for stat, (count_col, minimum) in rules.items():
        df.loc[df[count_col].fillna(0) < minimum, stat] = np.nan
    return df


def peer_percentiles(df: pd.DataFrame, stats, group_col: str = "role") -> pd.DataFrame:
    """Percentile (0-100) of each stat within the player's group; NaN stays NaN."""
    return df.groupby(group_col)[stats].rank(pct=True) * 100


def score_players(df: pd.DataFrame, group_col: str = "role") -> pd.DataFrame:
    """Add per-stat peer percentiles plus the effectiveness and discipline scores."""
    df = df.copy()
    eff = peer_percentiles(df, EFFECTIVENESS_STATS, group_col)
    disc = peer_percentiles(df, DISCIPLINE_STATS, group_col)
    for stat in EFFECTIVENESS_STATS + DISCIPLINE_STATS:
        df[f"{stat}_pct"] = (eff if stat in eff else disc)[stat]
    df["effectiveness"] = eff.mean(axis=1, skipna=True)
    df["discipline"] = 100 - disc.mean(axis=1, skipna=True)
    df["effectiveness_n_stats"] = eff.notna().sum(axis=1)
    return df


def _role_summary(df: pd.DataFrame) -> list:
    stats = EFFECTIVENESS_STATS + DISCIPLINE_STATS + ["fouls_won_per100"]
    rows = []
    for role, g in df.groupby("role"):
        rows.append({
            "role": role,
            "players": int(len(g)),
            "medians": {s: None if g[s].isna().all() else round(float(g[s].median()), 4)
                        for s in stats},
            "coverage": {s: int(g[s].notna().sum()) for s in EFFECTIVENESS_STATS},
        })
    return rows


def _top(df: pd.DataFrame, col: str, n: int = 10) -> list:
    best = df.dropna(subset=[col]).nlargest(n, col)
    return [{"player": r["player"], "role": r["role"], col: round(float(r[col]), 1)}
            for _, r in best.iterrows()]


def build_ratings() -> dict:
    """Score every regular player and save the table and a metrics report."""
    from pitchsense.data import load_shots
    from pitchsense.features import FEATURE_COLUMNS, build_feature_frame
    from pitchsense.roles import assign_roles, load_player_data, load_roles
    from pitchsense.train import PRIMARY_MODEL_PATH

    players = load_player_data()
    missing = [c for c in ("pass_completion", "n_tackle") if c not in players.columns]
    if missing:
        raise SystemExit("The player cache predates the effectiveness stats. Rebuild it "
                         "with `python -m pitchsense.build_data`.")

    players["role"] = assign_roles(load_roles(), players)

    shots = build_feature_frame(load_shots())
    xg = joblib.load(PRIMARY_MODEL_PATH).predict_proba(shots[FEATURE_COLUMNS])[:, 1]
    players = players.merge(finishing_table(shots, xg), on="player", how="left")

    scored = score_players(mask_small_samples(players))

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    scored.to_parquet(RATINGS_CACHE, index=False)

    corr = scored[EFFECTIVENESS_STATS + DISCIPLINE_STATS].corr(method="spearman")
    metrics = {
        "n_players": int(len(scored)),
        "effectiveness_stats": EFFECTIVENESS_STATS,
        "discipline_stats": DISCIPLINE_STATS,
        "min_attempts": {s: m for s, (_, m) in MIN_ATTEMPTS.items()},
        "coverage": {s: int(scored[s].notna().sum()) for s in EFFECTIVENESS_STATS},
        "effectiveness_vs_discipline_spearman": round(float(
            scored["effectiveness"].corr(scored["discipline"], method="spearman")), 3),
        "stat_spearman": {a: {b: round(float(corr.loc[a, b]), 3) for b in corr.columns}
                          for a in corr.index},
        "roles": _role_summary(scored),
        "top_effectiveness": _top(scored[scored["effectiveness_n_stats"] >= 3],
                                  "effectiveness"),
        "top_discipline": _top(scored, "discipline"),
    }
    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    with open(METRICS_PATH, "w") as f:
        json.dump(metrics, f, indent=2)
    return {"metrics": metrics, "data": scored}


def load_ratings() -> pd.DataFrame:
    return pd.read_parquet(RATINGS_CACHE)


if __name__ == "__main__":
    m = build_ratings()["metrics"]
    print(f"Scored {m['n_players']} players.  Stat coverage: {m['coverage']}")
    print(f"Effectiveness vs discipline (Spearman): "
          f"{m['effectiveness_vs_discipline_spearman']}\n")
    for r in m["roles"]:
        med = r["medians"]
        print(f"{r['role']:<28} n={r['players']:>3}  pass {med['pass_completion']:.0%}  "
              f"fouls/100 {med['fouls_per100']:.2f}  drawn/100 {med['fouls_won_per100']:.2f}")
    print("\nMost effective (3+ stats):")
    for r in m["top_effectiveness"]:
        print(f"  {r['effectiveness']:>5.1f}  {r['player']} ({r['role']})")
    print(f"\nSaved {RATINGS_CACHE}\nSaved {METRICS_PATH}")
