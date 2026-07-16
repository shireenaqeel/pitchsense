"""Train and evaluate the xG models, comparing a linear baseline to XGBoost.

Metrics reported:
- ROC AUC: how well the model ranks goals above non-goals.
- Log loss: penalises confident wrong probabilities; the key metric for xG
  since we care about calibrated probabilities, not just a yes/no decision.
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
from sklearn.model_selection import train_test_split
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
# The model served to the rest of the app is chosen empirically (lowest log
# loss on the held-out set), not hardcoded — on this dataset the linear model
# beats the tree, and the pipeline should reflect that rather than assume it.
PRIMARY_MODEL_PATH = MODEL_DIR / "xg_baseline.joblib"


def build_models() -> dict:
    return {
        "logistic_regression": Pipeline(
            [
                ("scale", StandardScaler()),
                ("clf", LogisticRegression(max_iter=1000)),
            ]
        ),
        "xgboost": XGBClassifier(
            n_estimators=300,
            max_depth=4,
            learning_rate=0.05,
            subsample=0.9,
            colsample_bytree=0.9,
            min_child_weight=5,
            eval_metric="logloss",
            random_state=42,
        ),
    }


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


def train_and_evaluate(test_size: float = 0.2, random_state: int = 42) -> dict:
    shots = load_shots()
    data = build_feature_frame(shots)
    X = data[FEATURE_COLUMNS]
    y = data[TARGET_COLUMN]

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=test_size, random_state=random_state, stratify=y
    )

    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    results = {}
    calibrations = {}
    for name, model in build_models().items():
        model.fit(X_train, y_train)
        prob = model.predict_proba(X_test)[:, 1]
        results[name] = _score(y_test, prob)
        calibrations[name] = calibration_table(y_test.to_numpy(), prob)
        joblib.dump(model, MODEL_PATHS[name])

    # Pick the primary model by lowest log loss and promote it to the stable
    # serving path used by the rest of the app.
    primary_model = min(results, key=lambda n: results[n]["log_loss"])
    joblib.dump(joblib.load(MODEL_PATHS[primary_model]), PRIMARY_MODEL_PATH)

    metrics = {
        "n_shots": int(len(data)),
        "n_goals": int(y.sum()),
        "goal_rate": float(y.mean()),
        "features": FEATURE_COLUMNS,
        "test_size": test_size,
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
    print(f"Features: {len(m['features'])}\n")
    print(f"{'model':<22}{'ROC AUC':>9}{'log loss':>11}{'Brier':>9}")
    for name, s in m["models"].items():
        print(f"{name:<22}{s['roc_auc']:>9.3f}{s['log_loss']:>11.3f}{s['brier']:>9.3f}")
    print(f"\nCalibration for primary model ({m['primary_model']}):")
    print(result["calibration"].to_string(index=False))
    print(f"\nSaved primary model to {PRIMARY_MODEL_PATH}")
