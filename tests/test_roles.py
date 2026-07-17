"""Tests for player-role cluster labelling (no network, no full fit)."""

import numpy as np
import pandas as pd

from pitchsense.players import PLAYER_FEATURES
from pitchsense.roles import choose_k, label_clusters


def _feats(rows):
    """Build a player feature frame from (position_group, ) rows."""
    return pd.DataFrame([
        {"player": f"P{i}", "position_group": grp,
         **{f: 0.0 for f in PLAYER_FEATURES}}
        for i, grp in enumerate(rows)
    ])


def _zero_z(clusters):
    z = pd.DataFrame(0.0, index=sorted(set(clusters)), columns=PLAYER_FEATURES)
    z.index.name = "cluster"
    return z


def test_label_by_dominant_position_group():
    feats = _feats(["Centre-back", "Centre-back", "Forward"])
    assignments = [0, 0, 1]
    labels, purity, groups = label_clusters(feats, assignments, _zero_z(assignments))
    assert labels[0] == "Centre-back"
    assert labels[1] == "Forward"
    assert purity[0] == 1.0
    assert purity[1] == 1.0


def test_purity_reflects_mixed_cluster():
    feats = _feats(["Centre-back", "Centre-back", "Full-back"])
    assignments = [0, 0, 0]
    labels, purity, groups = label_clusters(feats, assignments, _zero_z(assignments))
    assert labels[0] == "Centre-back"          # 2 of 3
    assert purity[0] == 2 / 3
    assert groups[0]["Full-back"] == 1


def test_duplicate_group_disambiguated_by_trait():
    feats = _feats(["Forward", "Forward"])
    assignments = [0, 1]
    z = _zero_z(assignments)
    z.loc[0, "shot_share"] = 2.0     # cluster 0 stands out on shooting
    z.loc[1, "dribble_share"] = 2.0  # cluster 1 on dribbling
    labels, _, _ = label_clusters(feats, assignments, z)
    assert labels[0] == "Forward (shot-heavy)"
    assert labels[1] == "Forward (dribbling)"
    assert labels[0] != labels[1]


def test_choose_k_prefers_clean_separation():
    rng = np.random.default_rng(0)
    # Five well-separated blobs: silhouette should pick k close to 5.
    blobs = np.vstack([
        rng.normal(center, 0.15, size=(20, 4))
        for center in ([0, 0, 0, 0], [6, 0, 0, 0], [0, 6, 0, 0], [6, 6, 0, 0], [3, 3, 6, 0])
    ])
    k, scores = choose_k(blobs, k_range=range(3, 8))
    assert set(scores.keys()) == set(range(3, 8))
    assert k == 5
