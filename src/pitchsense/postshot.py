"""Post-shot expected goals (PSxG) — a separate model that uses shot placement.

Pre-shot xG (``train.py``) answers "how good a chance was this?" from the
situation *before* the ball was struck. Post-shot xG answers a different
question — "given the shot was taken and placed *here*, how likely was it to
score?" — and so is allowed to use where the ball ended up (its lateral position
in the goal and its height). That placement is the *result* of the shot, not a
pre-shot condition, so it is deliberately kept out of the served xG model and put
in this separate one; mixing it in would be target leakage.

By convention PSxG is defined only over **on-target** shots (goals and saves) —
the shots a keeper actually had to deal with — because an off-target shot never
had a placement that could score. The model reuses the pre-shot features and adds
the two placement features on top, and shares the exact cross-validated search
machinery in ``train.py``.
"""

import json

from sklearn.model_selection import train_test_split

from pitchsense.data import load_shots
from pitchsense.features import (
    FEATURE_COLUMNS,
    build_feature_frame,
    placement_from_center,
    placement_height,
)
from pitchsense.train import (
    CV_FOLDS,
    MODEL_DIR,
    SEARCH_SCORING,
    XGB_SEARCH_ITER,
    compare_models,
)

# Shots the keeper had to deal with: goals and saves (including tipped onto the
# post). Off-target, wayward, blocked, and post-strikes are excluded.
ON_TARGET_OUTCOMES = {"Goal", "Saved", "Saved to Post"}

PLACEMENT_FEATURES = ["placement_from_center", "placement_height"]
POSTSHOT_FEATURES = FEATURE_COLUMNS + PLACEMENT_FEATURES

MODEL_PATHS = {
    "logistic_regression": MODEL_DIR / "psxg_logreg.joblib",
    "xgboost": MODEL_DIR / "psxg_xgboost.joblib",
}
PRIMARY_MODEL_PATH = MODEL_DIR / "psxg_baseline.joblib"
METRICS_PATH = MODEL_DIR / "psxg_metrics.json"


def build_postshot_frame(shots) -> "pd.DataFrame":
    """On-target shots with the pre-shot features plus the placement features."""
    df = build_feature_frame(shots)
    df = df[df["shot_outcome"].isin(ON_TARGET_OUTCOMES)].copy()
    df["placement_from_center"] = df["shot_end_location"].apply(placement_from_center)
    df["placement_height"] = df["shot_end_location"].apply(placement_height)
    return df


def train_postshot(test_size: float = 0.2, random_state: int = 42,
                   cv_folds: int = CV_FOLDS, n_iter: int = XGB_SEARCH_ITER,
                   search: bool = True) -> dict:
    data = build_postshot_frame(load_shots())
    X = data[POSTSHOT_FEATURES]
    y = data["is_goal"]

    results, calibrations, primary_model = compare_models(
        X, y, MODEL_PATHS, PRIMARY_MODEL_PATH, test_size, random_state, cv_folds, n_iter, search
    )

    metrics = {
        "n_shots": int(len(data)),
        "n_goals": int(y.sum()),
        "goal_rate": float(y.mean()),
        "features": POSTSHOT_FEATURES,
        "placement_features": PLACEMENT_FEATURES,
        "test_size": test_size,
        "cv_folds": cv_folds,
        "search_iter": n_iter,
        "search_scoring": SEARCH_SCORING,
        "primary_model": primary_model,
        "models": results,
    }
    with open(METRICS_PATH, "w") as f:
        json.dump(metrics, f, indent=2)

    return {"metrics": metrics, "calibration": calibrations[primary_model]}


if __name__ == "__main__":
    result = train_postshot()
    m = result["metrics"]
    print(f"On-target shots: {m['n_shots']}  Goals: {m['n_goals']}  "
          f"Goal rate: {m['goal_rate']:.3f}  (a save-vs-goal split)")
    print(f"Features: {len(m['features'])} ({len(m['placement_features'])} placement)  "
          f"CV folds: {m['cv_folds']}\n")

    print(f"{'model':<22}{'CV log loss':>16}{'CV ROC AUC':>16}{'test log loss':>15}{'test AUC':>10}")
    for name, s in m["models"].items():
        cv, test = s["cv"], s["test"]
        print(f"{name:<22}"
              f"{cv['log_loss']['mean']:>10.3f}±{cv['log_loss']['std']:<4.3f}"
              f"{cv['roc_auc']['mean']:>10.3f}±{cv['roc_auc']['std']:<4.3f}"
              f"{test['log_loss']:>15.3f}{test['roc_auc']:>10.3f}")

    print(f"\nPrimary post-shot model (lowest CV log loss): {m['primary_model']}")
    print(f"Saved primary model to {PRIMARY_MODEL_PATH}")
