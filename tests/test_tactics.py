"""Tests for the tactical cluster labeling (no network, no model fit)."""

import numpy as np
import pandas as pd

from pitchsense.possessions import POSSESSION_FEATURES
from pitchsense.tactics import (
    _TRANSITION_LABEL,
    cluster_centroids,
    label_clusters,
    label_possessions,
)


class _StubModel:
    """Stand-in clusterer that returns preset cluster ids in order."""

    def __init__(self, clusters):
        self._clusters = clusters

    def predict(self, X):
        return np.array(self._clusters[: len(X)])


def _centroids(rows: dict) -> pd.DataFrame:
    """Build a centroid frame from {cluster: {feature: value}}, zero-filled."""
    data = {}
    for cluster, feats in rows.items():
        data[cluster] = {f: feats.get(f, 0.0) for f in POSSESSION_FEATURES}
    df = pd.DataFrame(data).T
    df.index.name = "cluster"
    return df


def test_labels_map_clusters_to_archetypes():
    centroids = _centroids({
        0: {"n_passes": 8, "duration": 30, "forward_speed": 0.5},   # build-up
        1: {"n_passes": 2, "duration": 5, "forward_speed": 6.0},    # counter
        2: {"n_passes": 3, "duration": 8, "forward_speed": 1.0},    # transition
    })
    labels = label_clusters(centroids)
    assert labels[1] == "Counter-attack / direct"   # fastest upfield
    assert labels[0] == "Patient build-up"          # most passes of the rest
    assert labels[2] == _TRANSITION_LABEL           # leftover


def test_every_cluster_is_named_exactly_once():
    centroids = _centroids({
        0: {"n_passes": 5, "forward_speed": 1.0},
        1: {"n_passes": 9, "forward_speed": 2.0},
        2: {"n_passes": 1, "forward_speed": 9.0},
    })
    labels = label_clusters(centroids)
    assert set(labels.keys()) == {0, 1, 2}
    assert "Counter-attack / direct" in labels.values()
    assert "Patient build-up" in labels.values()


def test_labeling_is_relative_not_absolute():
    # Even an all-slow set still yields one (relatively) fastest counter cluster.
    centroids = _centroids({
        0: {"n_passes": 10, "forward_speed": 0.1},
        1: {"n_passes": 4, "forward_speed": 0.3},
    })
    labels = label_clusters(centroids)
    assert labels[1] == "Counter-attack / direct"
    assert labels[0] == "Patient build-up"


def test_label_possessions_maps_each_row_to_its_pattern():
    data = pd.DataFrame({f: [0.0, 0.0, 0.0] for f in POSSESSION_FEATURES})
    bundle = {"model": _StubModel([2, 0, 1]),
              "labels": {0: "Build-up", 1: "Counter", 2: "Regain"}}
    out = label_possessions(bundle, data)
    assert list(out) == ["Regain", "Build-up", "Counter"]
    assert list(out.index) == [0, 1, 2]


def test_cluster_centroids_average_per_group():
    data = pd.DataFrame([
        {f: 0.0 for f in POSSESSION_FEATURES} | {"n_passes": 2},
        {f: 0.0 for f in POSSESSION_FEATURES} | {"n_passes": 4},
        {f: 0.0 for f in POSSESSION_FEATURES} | {"n_passes": 10},
    ])
    centroids = cluster_centroids(data, labels=[0, 0, 1])
    assert centroids.loc[0, "n_passes"] == 3.0   # (2 + 4) / 2
    assert centroids.loc[1, "n_passes"] == 10.0
