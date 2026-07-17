"""Train and evaluate the xG models with cross-validated hyperparameter search.

Each model's hyperparameters are chosen by k-fold cross-validation on the
training data (grid search for the small logistic-regression space, randomized
search for the larger XGBoost space), optimising log loss because a good xG model
must be *calibrated*, not merely rank shots correctly. The chosen configuration
is then reported two ways: its cross-validated metrics (mean ± std across folds,
which reflect stability) and its score on a held-out test set never seen during
the search (an unbiased final estimate).

Metrics reported:
- ROC AUC: how well the model ranks goals above non-goals.
- Log loss: penalises confident wrong probabilities; the key metric for xG since
  we care about calibrated probabilities, not just a yes/no decision.
- Brier score: mean squared error of the predicted probabilities.
- A calibration table: for shots grouped by predicted xG, does the average
  prediction match the actual goal rate? A trustworthy xG model is calibrated.
"""

import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import brier_score_loss, log_loss, roc_auc_score
from sklearn.model_selection import (
    GridSearchCV,
    RandomizedSearchCV,
    StratifiedKFold,
    cross_validate,
    train_test_split,
)
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from xgboost import XGBClassifier

from pitchsense.data import load_shots
from pitchsense.features import FEATURE_COLUMNS, TARGET_COLUMN, build_feature_frame

MODEL_DIR = Path(__file__).resolve().parents[2] / "models"
METRICS_PATH = MODEL_DIR / "xg_metrics.json"
MODEL_PATHS = {
    "logistic_regression": MODEL_DIR / "xg_logreg.joblib",
    "xgboost": MODEL_DIR / "xg_xgboost.joblib",
}
# The model served to the rest of the app is chosen empirically (lowest
# cross-validated log loss), not hardcoded — the pipeline reflects whichever
# model actually calibrates best rather than assuming it.
PRIMARY_MODEL_PATH = MODEL_DIR / "xg_baseline.joblib"

CV_FOLDS = 5
XGB_SEARCH_ITER = 40
# Selection criterion for the search: log loss (calibration), not accuracy.
SEARCH_SCORING = "neg_log_loss"

# Metrics computed per fold for the chosen config; the negated ones are sklearn
# "greater-is-better" scorers we flip back to their natural (lower-is-better) sign.
CV_SCORING = {"roc_auc": "roc_auc", "log_loss": "neg_log_loss", "brier": "neg_brier_score"}
_NEGATED_SCORERS = {"log_loss", "brier"}


def build_searches() -> dict:
    """Per model: (estimator, hyperparameter space, search kind)."""
    logreg = Pipeline([
        ("scale", StandardScaler()),
        ("clf", LogisticRegression(max_iter=2000)),
    ])
    logreg_space = {"clf__C": [0.01, 0.03, 0.1, 0.3, 1.0, 3.0, 10.0]}

    xgb = XGBClassifier(eval_metric="logloss", random_state=42, n_jobs=1)
    xgb_space = {
        "n_estimators": [200, 300, 400, 600],
        "max_depth": [2, 3, 4, 5],
        "learning_rate": [0.01, 0.02, 0.05, 0.1],
        "subsample": [0.7, 0.8, 0.9, 1.0],
        "colsample_bytree": [0.7, 0.8, 0.9, 1.0],
        "min_child_weight": [1, 3, 5, 10],
        "gamma": [0.0, 0.5, 1.0],
    }
    return {
        "logistic_regression": (logreg, logreg_space, "grid"),
        "xgboost": (xgb, xgb_space, "random"),
    }


def _run_search(estimator, space, kind, X, y, cv, n_iter, random_state):
    if kind == "grid":
        search = GridSearchCV(estimator, space, scoring=SEARCH_SCORING, cv=cv, n_jobs=-1)
    else:
        search = RandomizedSearchCV(
            estimator, space, n_iter=n_iter, scoring=SEARCH_SCORING, cv=cv,
            n_jobs=-1, random_state=random_state,
        )
    search.fit(X, y)
    return search


def summarise_cv(cv_results: dict) -> dict:
    """Mean/std per metric from a ``cross_validate`` result, sign-corrected.

    sklearn reports log loss and Brier as negated "greater-is-better" scores; we
    flip them back so the reported numbers are the usual lower-is-better values.
    """
    summary = {}
    for name in CV_SCORING:
        arr = np.asarray(cv_results[f"test_{name}"], dtype=float)
        if name in _NEGATED_SCORERS:
            arr = -arr
        summary[name] = {"mean": float(arr.mean()), "std": float(arr.std())}
    return summary


def calibration_table(y_true: np.ndarray, y_prob: np.ndarray, bins: int = 10) -> pd.DataFrame:
    df = pd.DataFrame({"y": y_true, "p": y_prob})
    df["bucket"] = pd.qcut(df["p"], q=bins, duplicates="drop")
    grouped = df.groupby("bucket", observed=True).agg(
        n=("y", "size"), predicted=("p", "mean"), actual=("y", "mean")
    )
    return grouped.reset_index(drop=True)


def _score(y_true, prob) -> dict:
    return {
        "roc_auc": float(roc_auc_score(y_true, prob)),
        "log_loss": float(log_loss(y_true, prob)),
        "brier": float(brier_score_loss(y_true, prob)),
    }


def train_and_evaluate(test_size: float = 0.2, random_state: int = 42,
                       cv_folds: int = CV_FOLDS, n_iter: int = XGB_SEARCH_ITER,
                       search: bool = True) -> dict:
    shots = load_shots()
    data = build_feature_frame(shots)
    X = data[FEATURE_COLUMNS]
    y = data[TARGET_COLUMN]

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=test_size, random_state=random_state, stratify=y
    )
    cv = StratifiedKFold(n_splits=cv_folds, shuffle=True, random_state=random_state)

    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    results = {}
    calibrations = {}
    for name, (estimator, space, kind) in build_searches().items():
        if search:
            found = _run_search(estimator, space, kind, X_train, y_train, cv, n_iter, random_state)
            best = found.best_estimator_
            best_params = found.best_params_
        else:
            best = estimator.fit(X_train, y_train)
            best_params = {}

        # Cross-validated metrics of the chosen config (stability across folds).
        cv_results = cross_validate(best, X_train, y_train, cv=cv, scoring=CV_SCORING)
        cv_metrics = summarise_cv(cv_results)

        # Unbiased final estimate on the held-out test set.
        best.fit(X_train, y_train)
        prob = best.predict_proba(X_test)[:, 1]
        results[name] = {"best_params": best_params, "cv": cv_metrics, "test": _score(y_test, prob)}
        calibrations[name] = calibration_table(y_test.to_numpy(), prob)
        joblib.dump(best, MODEL_PATHS[name])

    # Pick the primary model by cross-validated log loss — a more robust choice
    # than a single split — and promote it to the stable serving path.
    primary_model = min(results, key=lambda n: results[n]["cv"]["log_loss"]["mean"])
    joblib.dump(joblib.load(MODEL_PATHS[primary_model]), PRIMARY_MODEL_PATH)

    metrics = {
        "n_shots": int(len(data)),
        "n_goals": int(y.sum()),
        "goal_rate": float(y.mean()),
        "features": FEATURE_COLUMNS,
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
    result = train_and_evaluate()
    m = result["metrics"]
    print(f"Shots: {m['n_shots']}  Goals: {m['n_goals']}  Goal rate: {m['goal_rate']:.3f}")
    print(f"Features: {len(m['features'])}  CV folds: {m['cv_folds']}  "
          f"Search iters (xgb): {m['search_iter']}\n")

    print(f"{'model':<22}{'CV log loss':>16}{'CV ROC AUC':>16}{'test log loss':>15}{'test AUC':>10}")
    for name, s in m["models"].items():
        cv, test = s["cv"], s["test"]
        print(f"{name:<22}"
              f"{cv['log_loss']['mean']:>10.3f}±{cv['log_loss']['std']:<4.3f}"
              f"{cv['roc_auc']['mean']:>10.3f}±{cv['roc_auc']['std']:<4.3f}"
              f"{test['log_loss']:>15.3f}{test['roc_auc']:>10.3f}")

    print(f"\nPrimary model (lowest CV log loss): {m['primary_model']}")
    print("Best hyperparameters:")
    for name, s in m["models"].items():
        print(f"  {name}: {s['best_params']}")
    print(f"\nCalibration for primary model ({m['primary_model']}):")
    print(result["calibration"].to_string(index=False))
    print(f"\nSaved primary model to {PRIMARY_MODEL_PATH}")
