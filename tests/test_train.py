"""Unit tests for the cross-validation helpers (no data, no model fit)."""

import numpy as np
import pytest

from pitchsense.train import CV_SCORING, build_searches, summarise_cv


def test_summarise_cv_means_std_and_sign_flip():
    cv_results = {
        "test_roc_auc": np.array([0.70, 0.80]),
        "test_log_loss": np.array([-0.30, -0.40]),   # sklearn neg scorer
        "test_brier": np.array([-0.06, -0.08]),       # sklearn neg scorer
    }
    out = summarise_cv(cv_results)
    assert out["roc_auc"]["mean"] == pytest.approx(0.75)
    assert out["roc_auc"]["std"] == pytest.approx(0.05)
    # negated scorers are flipped back to natural lower-is-better values
    assert out["log_loss"]["mean"] == pytest.approx(0.35)
    assert out["brier"]["mean"] == pytest.approx(0.07)


def test_summarise_cv_covers_every_scorer():
    cv_results = {f"test_{name}": np.array([1.0, 1.0]) for name in CV_SCORING}
    out = summarise_cv(cv_results)
    assert set(out) == set(CV_SCORING)
    for stats in out.values():
        assert stats["std"] == 0.0


def test_build_searches_defines_both_models():
    searches = build_searches()
    assert set(searches) == {"logistic_regression", "xgboost"}
    for _estimator, space, kind in searches.values():
        assert kind in ("grid", "random")
        assert isinstance(space, dict) and space
    # the linear model tunes regularisation; the tree tunes depth
    assert "clf__C" in searches["logistic_regression"][1]
    assert "max_depth" in searches["xgboost"][1]


def test_international_folds_validate_only_on_international_rows():
    import pandas as pd

    from pitchsense.train import international_folds

    y_intl = pd.Series([0, 1] * 10)
    folds = international_folds(y_intl, n_extra=7, cv_folds=5)
    assert len(folds) == 5
    club = set(range(20, 27))
    validated = set()
    for train, val in folds:
        assert club <= set(train)            # club rows always train
        assert not (set(val) & club)         # and are never validated on
        assert not (set(val) & set(train))
        validated |= set(val)
    assert validated == set(range(20))       # every international row validated once


def test_with_extra_appends_club_rows_after_international():
    import pandas as pd

    from pitchsense.train import with_extra

    X = pd.DataFrame({"a": [1, 2]}, index=[10, 11])
    y = pd.Series([0, 1], index=[10, 11])
    X_all, y_all, n = with_extra(X, y, pd.DataFrame({"a": [3]}), pd.Series([1]))
    assert n == 1
    assert X_all["a"].tolist() == [1, 2, 3]
    assert list(X_all.index) == [0, 1, 2]
    assert with_extra(X, y)[2] == 0
