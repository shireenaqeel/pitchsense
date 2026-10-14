"""Tests for model-based explanations and the lesson content."""

import numpy as np
import pandas as pd
import pytest
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from pitchsense.explain import FACTOR_GROUPS, factor_contributions, reasons
from pitchsense.features import FEATURE_COLUMNS
from pitchsense.lessons import LESSONS, better_option, concept_goal_rate, practice_pool
from pitchsense.sandbox import scenario_features


@pytest.fixture(scope="module")
def model():
    """A small linear xG model fitted on synthetic scenarios: closer = more goals."""
    rng = np.random.default_rng(0)
    from pitchsense.sandbox import Scenario
    scen = [Scenario(x=float(x), y=float(y), blockers=int(b), header=bool(h))
            for x, y, b, h in zip(rng.uniform(85, 117, 300), rng.uniform(25, 55, 300),
                                  rng.integers(0, 4, 300), rng.integers(0, 2, 300))]
    X = scenario_features(scen)[FEATURE_COLUMNS]
    y = (X["distance"] < 14).astype(int).to_numpy().copy()
    y[:4] = [0, 1, 0, 1]  # make sure both classes exist
    return Pipeline([("scale", StandardScaler()), ("clf", LogisticRegression())]).fit(X, y)


def test_every_feature_belongs_to_exactly_one_factor():
    grouped = [f for feats in FACTOR_GROUPS.values() for f in feats]
    assert sorted(grouped) == sorted(FEATURE_COLUMNS)


def test_contributions_sum_to_the_log_odds_gap(model):
    from pitchsense.sandbox import Scenario
    shot = scenario_features(Scenario(x=110, y=40)).iloc[0]
    total = sum(v for _, v in factor_contributions(model, shot))
    logit = model.decision_function(shot[FEATURE_COLUMNS].to_frame().T)[0]
    assert total == pytest.approx(logit - model["clf"].intercept_[0])


def test_close_shot_credits_distance(model):
    from pitchsense.sandbox import Scenario
    shot = scenario_features(Scenario(x=112, y=40, blockers=0)).iloc[0]
    assert "Distance" in [factor for _, factor, _ in reasons(model, shot)["helped"]]


def test_absent_binary_factors_are_not_mentioned(model):
    from pitchsense.sandbox import Scenario
    shot = scenario_features(Scenario(x=100, y=40, header=False)).iloc[0]
    named = [f for side in reasons(model, shot).values() for _, f, _ in side]
    assert "Header" not in named


def test_non_linear_model_returns_no_contributions():
    assert factor_contributions(object(), pd.Series(dtype=float)) == []


def test_lessons_have_unique_ids_and_two_way_comparisons():
    assert len({l.id for l in LESSONS}) == len(LESSONS)
    assert all(len(l.compare) == 2 for l in LESSONS)


def test_practice_pool_filters_by_concept():
    tags = [["Header"], ["Long range"], ["Header", "From cross"]]
    header = next(l for l in LESSONS if l.id == "header")
    intro = next(l for l in LESSONS if not l.concepts)
    assert practice_pool(tags, header) == [0, 2]
    assert practice_pool(tags, intro) == [0, 1, 2]


def test_concept_goal_rate():
    shots = pd.DataFrame({"is_goal": [1, 0, 0, 1]})
    tags = [["Header"], ["Header"], ["Long range"], ["Long range"]]
    assert concept_goal_rate(shots, tags, "Header") == (2, 0.5)
    assert concept_goal_rate(shots, tags, "One-on-one") == (0, 0.0)


def test_better_option():
    assert better_option(0.3, 0.1) == "A"
    assert better_option(0.1, 0.3) == "B"


def test_xgboost_contributions_sum_to_the_log_odds_gap():
    from xgboost import XGBClassifier

    from pitchsense.sandbox import Scenario
    rng = np.random.default_rng(1)
    scen = [Scenario(x=float(x), y=float(y), blockers=int(b))
            for x, y, b in zip(rng.uniform(85, 117, 300), rng.uniform(25, 55, 300),
                               rng.integers(0, 4, 300))]
    X = scenario_features(scen)[FEATURE_COLUMNS]
    y = (X["distance"] < 14).astype(int)
    xgb = XGBClassifier(n_estimators=20, max_depth=2).fit(X, y)

    shot = scenario_features(Scenario(x=110, y=40)).iloc[0]
    parts = factor_contributions(xgb, shot)
    assert parts, "XGBoost should be explained, not fall back to nothing"
    row = shot[FEATURE_COLUMNS].to_frame().T.astype(float)
    margin = xgb.predict(row, output_margin=True)[0]
    bias = xgb.get_booster().predict(
        __import__("xgboost").DMatrix(row), pred_contribs=True)[0][-1]
    assert sum(v for _, v in parts) == pytest.approx(margin - bias, abs=1e-4)
    assert dict(parts)["Distance"] > 0      # a close shot: distance pushed it up
