"""Cluster possessions into tactical patterns (unsupervised).

There are no tactical labels in StatsBomb data, so patterns are discovered, not
taught: possessions are described by shape-and-tempo features (``possessions.py``)
and grouped with k-means. The resulting clusters are then given human-readable
names by inspecting their centroids, so a fast, direct, shot-ending cluster reads
as a counter-attack and a slow, pass-heavy one as build-up.

The labels are an *interpretation* of the discovered clusters, not ground truth —
the honest framing for an unsupervised model. Three clusters are used to match
the three archetypes the project targets (build-up, counter-attack, regain); the
silhouette score is reported so the choice can be sanity-checked.
"""

import json
from pathlib import Path

import joblib
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from pitchsense.possessions import (
    POSSESSION_FEATURES,
    build_possession_frame,
)

N_CLUSTERS = 3

DATA_DIR = Path(__file__).resolve().parents[2] / "data"
POSSESSIONS_CACHE = DATA_DIR / "wc2018_possessions.parquet"

MODEL_DIR = Path(__file__).resolve().parents[2] / "models"
MODEL_PATH = MODEL_DIR / "tactics_kmeans.joblib"
METRICS_PATH = MODEL_DIR / "tactics_metrics.json"

# Fallback name for any cluster the ranking rules do not otherwise claim.
_TRANSITION_LABEL = "Quick regain / transition"


def load_possession_data(use_cache: bool = True) -> pd.DataFrame:
    """All World Cup 2018 possession features, using the disk cache.

    Fetches every match's events, reduces each to a compact possession feature
    table, and caches the concatenation. Only the small feature frame is stored,
    not the raw events. Delete the cache to force a refresh.
    """
    if use_cache and POSSESSIONS_CACHE.exists():
        return pd.read_parquet(POSSESSIONS_CACHE)

    from statsbombpy import sb  # lazy: keeps the module importable offline

    from pitchsense.data import COMPETITION_ID, SEASON_ID

    matches = sb.matches(competition_id=COMPETITION_ID, season_id=SEASON_ID)
    frames = []
    for match_id in matches["match_id"]:
        events = sb.events(match_id=match_id)
        events["match_id"] = match_id
        frames.append(build_possession_frame(events))
    data = pd.concat(frames, ignore_index=True)

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    data.to_parquet(POSSESSIONS_CACHE, index=False)
    return data


def cluster_centroids(data: pd.DataFrame, labels) -> pd.DataFrame:
    """Mean of each feature per cluster, in original (un-scaled) units."""
    df = data[POSSESSION_FEATURES].copy()
    df["cluster"] = labels
    return df.groupby("cluster").mean()


def label_clusters(centroids: pd.DataFrame) -> dict:
    """Name each cluster from its centroid, deterministically.

    Ranks the clusters against each other rather than using absolute cut-offs, so
    the names describe the patterns actually present:

    - the cluster moving upfield fastest is the counter-attack / direct transition;
    - of those left, the most pass-heavy is the patient build-up;
    - whatever remains is short, broken play — a quick regain / transition.
    """
    remaining = list(centroids.index)

    counter = centroids.loc[remaining, "forward_speed"].idxmax()
    labels = {counter: "Counter-attack / direct"}
    remaining.remove(counter)

    if remaining:
        buildup = centroids.loc[remaining, "n_passes"].idxmax()
        labels[buildup] = "Patient build-up"
        remaining.remove(buildup)

    for cluster in remaining:
        labels[cluster] = _TRANSITION_LABEL
    return labels


def train_classifier(n_clusters: int = N_CLUSTERS, random_state: int = 42) -> dict:
    """Fit the k-means tactical clusterer, label the clusters, and save both."""
    data = load_possession_data()
    X = data[POSSESSION_FEATURES]

    model = Pipeline([
        ("scale", StandardScaler()),
        ("kmeans", KMeans(n_clusters=n_clusters, n_init=10, random_state=random_state)),
    ])
    assignments = model.fit_predict(X)

    scaled = model.named_steps["scale"].transform(X)
    silhouette = float(silhouette_score(scaled, assignments))

    centroids = cluster_centroids(data, assignments)
    labels = label_clusters(centroids)

    summary = []
    for cluster in sorted(centroids.index):
        means = centroids.loc[cluster]
        summary.append({
            "cluster": int(cluster),
            "label": labels[cluster],
            "size": int((assignments == cluster).sum()),
            "means": {f: round(float(means[f]), 3) for f in POSSESSION_FEATURES},
        })

    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    joblib.dump({"model": model, "labels": labels}, MODEL_PATH)

    metrics = {
        "n_possessions": int(len(data)),
        "n_clusters": n_clusters,
        "silhouette": silhouette,
        "features": POSSESSION_FEATURES,
        "clusters": summary,
    }
    with open(METRICS_PATH, "w") as f:
        json.dump(metrics, f, indent=2)

    return metrics


def load_classifier():
    """Load the saved model bundle: ``{"model", "labels"}``."""
    return joblib.load(MODEL_PATH)


def predict_pattern(bundle, features: dict) -> str:
    """Name the tactical pattern of one possession's feature dict."""
    row = pd.DataFrame([[features[f] for f in POSSESSION_FEATURES]], columns=POSSESSION_FEATURES)
    cluster = int(bundle["model"].predict(row)[0])
    return bundle["labels"][cluster]


if __name__ == "__main__":
    m = train_classifier()
    print(f"Possessions: {m['n_possessions']}  Clusters: {m['n_clusters']}  "
          f"Silhouette: {m['silhouette']:.3f}\n")
    for c in m["clusters"]:
        mean = c["means"]
        print(f"[{c['size']:>4}] {c['label']}")
        print(f"        passes {mean['n_passes']:.1f}  dur {mean['duration']:.1f}s  "
              f"fwd {mean['net_forward']:.1f}y  direct {mean['directness']:.2f}  "
              f"speed {mean['forward_speed']:.2f}y/s  shot% {mean['ends_in_shot']*100:.0f}")
    print(f"\nSaved model to {MODEL_PATH}")
