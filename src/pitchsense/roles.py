"""Cluster players into behavioural roles (k-means + PCA).

Players are described by scale-free behavioural features (``players.py``) and
grouped with k-means; the number of clusters is chosen by silhouette. The
discovered clusters are then labelled by the dominant *nominal* position of the
players inside them, and each cluster's positional purity is reported — so the
labels are validated against how players are actually listed, not asserted.
PCA projects the feature space to two dimensions for a role-map figure.

The point is behavioural: two players listed at the same position can fall into
different clusters (a ball-playing centre-back vs a stopper), and the purity
figure shows how cleanly behaviour lines up with the position label.
"""

import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.decomposition import PCA
from sklearn.metrics import silhouette_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from pitchsense.players import (
    PLAYER_FEATURES,
    combine_aggregates,
    finalize_features,
    player_raw_aggregates,
)

K_RANGE = range(5, 9)

DATA_DIR = Path(__file__).resolve().parents[2] / "data"
PLAYERS_CACHE = DATA_DIR / "wc2018_players.parquet"

MODEL_DIR = Path(__file__).resolve().parents[2] / "models"
MODEL_PATH = MODEL_DIR / "roles_kmeans.joblib"
METRICS_PATH = MODEL_DIR / "roles_metrics.json"

DOCS_DIR = Path(__file__).resolve().parents[2] / "docs"
ROLE_MAP_PATH = DOCS_DIR / "player_roles.png"

# Short phrase for the standout feature of a cluster, used to tell apart two
# clusters that share a dominant position group.
_FEATURE_PHRASES = {
    "avg_x": "advanced",
    "lateral": "wide",
    "x_spread": "roaming",
    "y_spread": "roaming",
    "pass_share": "pass-heavy",
    "forward_pass_ratio": "direct",
    "avg_pass_length": "long passing",
    "cross_share": "crossing",
    "carry_share": "ball-carrying",
    "dribble_share": "dribbling",
    "shot_share": "shot-heavy",
    "defensive_share": "defensive",
}


def load_player_data(use_cache: bool = True) -> pd.DataFrame:
    """Behavioural feature table for every regular player, using the disk cache.

    Fetches every match's events, reduces each to per-player raw aggregates,
    pools them across matches, and finalises the scale-free features. Only the
    small player table is cached. Delete the cache to force a refresh.
    """
    if use_cache and PLAYERS_CACHE.exists():
        return pd.read_parquet(PLAYERS_CACHE)

    from statsbombpy import sb  # lazy: keeps the module importable offline

    from pitchsense.data import COMPETITION_ID, SEASON_ID

    matches = sb.matches(competition_id=COMPETITION_ID, season_id=SEASON_ID)
    frames = [player_raw_aggregates(sb.events(match_id=mid)) for mid in matches["match_id"]]
    pooled = combine_aggregates(pd.concat(frames, ignore_index=True))
    data = finalize_features(pooled)

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    data.to_parquet(PLAYERS_CACHE, index=False)
    return data


def choose_k(scaled, k_range=K_RANGE, random_state: int = 42):
    """Pick the cluster count with the best silhouette; return (k, {k: score})."""
    scores = {}
    for k in k_range:
        km = KMeans(n_clusters=k, n_init=10, random_state=random_state)
        scores[k] = float(silhouette_score(scaled, km.fit_predict(scaled)))
    best = max(scores, key=scores.get)
    return best, scores


def _distinctive_trait(centroid_z: pd.Series) -> str:
    """Phrase for the feature a cluster is most above average on."""
    feature = centroid_z.idxmax()
    return _FEATURE_PHRASES.get(feature, feature)


def label_clusters(feats: pd.DataFrame, assignments, z_centroids: pd.DataFrame):
    """Name each cluster by its dominant position group; report purity.

    When two clusters share a dominant group, the one that is not the larger gets
    a distinguishing trait appended so the labels stay unique and readable.
    """
    df = feats.copy()
    df["cluster"] = assignments

    labels, purity, groups = {}, {}, {}
    for cluster, g in df.groupby("cluster"):
        counts = g["position_group"].value_counts()
        labels[cluster] = counts.idxmax()
        purity[cluster] = float(counts.max() / counts.sum())
        groups[cluster] = counts.to_dict()

    by_name = {}
    for cluster, name in labels.items():
        by_name.setdefault(name, []).append(cluster)
    for name, clusters in by_name.items():
        if len(clusters) > 1:
            for cluster in clusters:
                trait = _distinctive_trait(z_centroids.loc[cluster])
                labels[cluster] = f"{name} ({trait})"
    return labels, purity, groups


def train_roles(random_state: int = 42) -> dict:
    """Fit the player-role clusterer, label the clusters, and save everything."""
    data = load_player_data()
    X = data[PLAYER_FEATURES]

    scaler = StandardScaler().fit(X)
    scaled = scaler.transform(X)

    k, sil_scores = choose_k(scaled, random_state=random_state)
    kmeans = KMeans(n_clusters=k, n_init=10, random_state=random_state)
    assignments = kmeans.fit_predict(scaled)
    model = Pipeline([("scale", scaler), ("kmeans", kmeans)])

    pca = PCA(n_components=2, random_state=random_state).fit(scaled)

    # Centroids as z-scores (scaled space) tell us what each cluster is high on.
    z = pd.DataFrame(scaled, columns=PLAYER_FEATURES)
    z["cluster"] = assignments
    z_centroids = z.groupby("cluster").mean()
    raw_centroids = X.copy()
    raw_centroids["cluster"] = assignments
    raw_centroids = raw_centroids.groupby("cluster").mean()

    labels, purity, groups = label_clusters(data, assignments, z_centroids)

    summary = []
    for cluster in sorted(labels):
        means = raw_centroids.loc[cluster]
        summary.append({
            "cluster": int(cluster),
            "label": labels[cluster],
            "size": int((assignments == cluster).sum()),
            "purity": round(purity[cluster], 3),
            "positions": {k2: int(v) for k2, v in groups[cluster].items()},
            "means": {f: round(float(means[f]), 3) for f in PLAYER_FEATURES},
        })

    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    joblib.dump(
        {"model": model, "labels": labels, "pca": pca, "features": PLAYER_FEATURES},
        MODEL_PATH,
    )

    metrics = {
        "n_players": int(len(data)),
        "n_clusters": int(k),
        "silhouette": sil_scores[k],
        "silhouette_by_k": {str(kk): round(v, 3) for kk, v in sil_scores.items()},
        "features": PLAYER_FEATURES,
        "clusters": summary,
    }
    with open(METRICS_PATH, "w") as f:
        json.dump(metrics, f, indent=2)

    return {"metrics": metrics, "data": data, "assignments": assignments, "pca": pca}


def render_role_map(result=None, save_path: Path | None = None) -> Path:
    """Scatter players in PCA space, coloured by role cluster, to a PNG."""
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    if result is None:
        result = train_roles()
    if save_path is None:
        save_path = ROLE_MAP_PATH

    data, assignments, pca = result["data"], result["assignments"], result["pca"]
    labels = joblib.load(MODEL_PATH)["labels"]
    coords = pca.transform(StandardScaler().fit_transform(data[PLAYER_FEATURES]))

    fig, ax = plt.subplots(figsize=(11, 8))
    for cluster in sorted(set(assignments)):
        mask = assignments == cluster
        ax.scatter(coords[mask, 0], coords[mask, 1], s=35, alpha=0.7, label=labels[cluster])
    ax.set_xlabel("PCA 1")
    ax.set_ylabel("PCA 2")
    ax.set_title("Player roles from behaviour (World Cup 2018)")
    ax.legend(loc="best", fontsize=9)
    save_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(save_path, dpi=120, bbox_inches="tight")
    plt.close(fig)
    return save_path


def load_roles():
    return joblib.load(MODEL_PATH)


def predict_role(bundle, features: dict) -> str:
    row = pd.DataFrame([[features[f] for f in bundle["features"]]], columns=bundle["features"])
    cluster = int(bundle["model"].predict(row)[0])
    return bundle["labels"][cluster]


def assign_roles(bundle, data: pd.DataFrame) -> pd.Series:
    """Role label for every row of a player feature frame."""
    clusters = bundle["model"].predict(data[bundle["features"]])
    return pd.Series([bundle["labels"][int(c)] for c in clusters], index=data.index)


if __name__ == "__main__":
    result = train_roles()
    m = result["metrics"]
    print(f"Players: {m['n_players']}  Clusters: {m['n_clusters']}  "
          f"Silhouette: {m['silhouette']:.3f}")
    print(f"Silhouette by k: {m['silhouette_by_k']}\n")
    for c in m["clusters"]:
        mean = c["means"]
        print(f"[{c['size']:>3}] {c['label']:<28} purity {c['purity']:.0%}")
        print(f"      x {mean['avg_x']:.1f}  wide {mean['lateral']:.1f}  "
              f"pass {mean['pass_share']:.2f}  def {mean['defensive_share']:.2f}  "
              f"shot {mean['shot_share']:.3f}  dribble {mean['dribble_share']:.3f}")
    path = render_role_map(result)
    print(f"\nSaved model to {MODEL_PATH}\nSaved role map to {path}")
