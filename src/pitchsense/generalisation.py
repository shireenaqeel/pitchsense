"""Leave-one-tournament-out test: does xG transfer to an unseen competition?

A random train/test split lets shots from every tournament land in both halves,
so it can flatter a model that has quietly learned tournament-specific quirks
(a particular era's shooting, a broadcaster's tracking). This is a stricter test:
hold out one whole tournament, tune and train on the other three, and evaluate on
the unseen one — repeated with each tournament held out in turn. The gap between
this and the random-split score is the honest measure of how well the model would
do on a competition it has never seen, which is what real use would demand.

The hyperparameter search is re-run inside each fold on the three training
tournaments only, so the held-out tournament never influences model selection.
This is an evaluation, not a training step — it changes no served model, only
writes a report to ``models/xg_generalisation.json``.
"""

import json

import numpy as np
from sklearn.model_selection import StratifiedKFold

from pitchsense.data import COMPETITIONS, load_shots
from pitchsense.features import FEATURE_COLUMNS, TARGET_COLUMN, build_feature_frame
from pitchsense.train import (
    CV_FOLDS,
    MODEL_DIR,
    METRICS_PATH as XG_METRICS_PATH,
    XGB_SEARCH_ITER,
    _run_search,
    _score,
    build_searches,
)

# Human-readable label per configured (competition_id, season_id).
TOURNAMENT_NAMES = {
    (43, 3): "World Cup 2018",
    (43, 106): "World Cup 2022",
    (55, 43): "Euro 2020",
    (55, 282): "Euro 2024",
}

METRICS_PATH = MODEL_DIR / "xg_generalisation.json"


def tournaments_in_order() -> list:
    """Tournament labels in the configured competition order."""
    return [TOURNAMENT_NAMES.get(c, f"{c[0]}/{c[1]}") for c in COMPETITIONS]


def match_tournament_map() -> dict:
    """``{match_id: tournament label}`` across the configured competitions."""
    from statsbombpy import sb  # lazy: only match lists, no events

    labels = {}
    for competition_id, season_id in COMPETITIONS:
        name = TOURNAMENT_NAMES.get((competition_id, season_id), f"{competition_id}/{season_id}")
        for match_id in sb.matches(competition_id=competition_id, season_id=season_id)["match_id"]:
            labels[int(match_id)] = name
    return labels


def label_tournaments(data, labels: dict):
    """Attach a ``tournament`` column from a match_id→label map, dropping unmapped."""
    data = data.copy()
    data["tournament"] = data["match_id"].map(labels)
    return data.dropna(subset=["tournament"])


def holdout_split(data, held: str):
    """Split into (train on every other tournament, test on the held-out one)."""
    return data[data["tournament"] != held], data[data["tournament"] == held]


def summarise(per_model: dict, tournaments: list) -> dict:
    """Mean AUC / log loss across the held-out tournaments, per model."""
    summary = {}
    for name, per in per_model.items():
        aucs = [per[t]["roc_auc"] for t in tournaments]
        lls = [per[t]["log_loss"] for t in tournaments]
        summary[name] = {
            "mean_roc_auc": float(np.mean(aucs)),
            "mean_log_loss": float(np.mean(lls)),
            "per_tournament": per,
        }
    return summary


def evaluate(n_iter: int = XGB_SEARCH_ITER, cv_folds: int = CV_FOLDS,
             random_state: int = 42, search: bool = True) -> dict:
    data = label_tournaments(build_feature_frame(load_shots()), match_tournament_map())
    tournaments = tournaments_in_order()

    per_model = {}
    for held in tournaments:
        train, test = holdout_split(data, held)
        X_tr, y_tr = train[FEATURE_COLUMNS], train[TARGET_COLUMN]
        X_te, y_te = test[FEATURE_COLUMNS], test[TARGET_COLUMN]
        cv = StratifiedKFold(n_splits=cv_folds, shuffle=True, random_state=random_state)

        for name, (estimator, space, kind) in build_searches().items():
            if search:
                best = _run_search(estimator, space, kind, X_tr, y_tr, cv, n_iter, random_state).best_estimator_
            else:
                best = estimator
            best.fit(X_tr, y_tr)
            prob = best.predict_proba(X_te)[:, 1]
            entry = _score(y_te, prob)
            entry["n"] = int(len(test))
            entry["goals"] = int(y_te.sum())
            per_model.setdefault(name, {})[held] = entry

    summary = summarise(per_model, tournaments)
    metrics = {
        "tournaments": tournaments,
        "n_shots": int(len(data)),
        "features": FEATURE_COLUMNS,
        "cv_folds": cv_folds,
        "search_iter": n_iter,
        "models": summary,
    }
    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    with open(METRICS_PATH, "w") as f:
        json.dump(metrics, f, indent=2)
    return metrics


def _random_split_reference() -> dict:
    """Random-split test AUCs from the standard training run, for comparison."""
    if not XG_METRICS_PATH.exists():
        return {}
    m = json.loads(XG_METRICS_PATH.read_text(encoding="utf-8"))
    return {name: s["test"]["roc_auc"] for name, s in m["models"].items()}


if __name__ == "__main__":
    metrics = evaluate()
    tournaments = metrics["tournaments"]
    reference = _random_split_reference()

    print(f"Leave-one-tournament-out xG, {metrics['n_shots']} shots "
          f"across {len(tournaments)} tournaments (ROC AUC on the held-out one)\n")
    header = "held out ->".ljust(22) + "".join(t.rjust(18) for t in tournaments) + "  mean   (random)"
    print(header)
    for name, s in metrics["models"].items():
        row = name.ljust(22)
        for t in tournaments:
            row += f"{s['per_tournament'][t]['roc_auc']:>18.3f}"
        ref = reference.get(name)
        row += f"{s['mean_roc_auc']:>7.3f}"
        row += f"{('   ' + format(ref, '.3f')) if ref is not None else '':>10}"
        print(row)
    print(f"\nSaved report to {METRICS_PATH}")
