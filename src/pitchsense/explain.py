"""Explain *why* the model rated a chance the way it did, in football language.

Both served model families decompose exactly into per-feature log-odds
contributions relative to an average shot. For the standardised logistic
regression each feature adds ``coef * (value - mean) / std``; for XGBoost the
contributions are its exact TreeSHAP values (``pred_contribs``). Correlated
features are grouped into the handful of ideas a coach would name (distance,
angle, bodies in the way, the keeper, ...) and their contributions summed, so a
learner sees "the angle was tight" rather than seventeen raw numbers.

Kept free of any UI so it can be unit tested. For any other model
``factor_contributions`` returns an empty list and callers fall back to the
descriptive explanation.
"""

import math

import pandas as pd

from pitchsense.features import FEATURE_COLUMNS

# Football idea -> the model features that express it.
FACTOR_GROUPS = {
    "Distance": ["distance"],
    "Angle": ["angle"],
    "Bodies in the way": ["defenders_in_cone", "defenders_in_lane", "defenders_behind_ball"],
    "Space to shoot": ["nearest_defender_dist"],
    "Goalkeeper": ["keeper_dist_to_goal", "keeper_dist_to_ball", "keeper_in_cone"],
    "Header": ["is_header"],
    "Pressure": ["under_pressure"],
    "One-on-one": ["is_one_on_one"],
    "First time": ["is_first_time"],
    "The final ball": ["assist_cross", "assist_cutback", "assist_through_ball"],
    "Phase of play": ["from_open_play"],
}

FACTOR_EMOJI = {
    "Distance": "📏", "Angle": "📐", "Bodies in the way": "🧱", "Space to shoot": "🫸",
    "Goalkeeper": "🧤", "Header": "🗣️", "Pressure": "😤", "One-on-one": "🏃",
    "First time": "⚡", "The final ball": "🎁", "Phase of play": "🔁",
}

# Yes/no factors are only worth naming when the thing actually happened: "it
# wasn't a header" nudges every footed shot up a little, which is true but
# teaches nothing. Phase of play is too subtle to explain to a learner.
PRESENCE_ONLY = {"Header", "Pressure", "One-on-one", "First time", "The final ball"}
NEVER_SHOWN = {"Phase of play"}

# Contributions smaller than this (in log-odds) are not worth mentioning.
MIN_EFFECT = 0.08


def _linear_parts(model):
    """(coefs, means, stds) for a scale -> logistic pipeline, else None."""
    steps = getattr(model, "named_steps", {})
    clf, scale = steps.get("clf"), steps.get("scale")
    if clf is None or scale is None or not hasattr(clf, "coef_"):
        return None
    return clf.coef_[0], scale.mean_, scale.scale_


def _feature_contributions(model, shot):
    """{feature: log-odds contribution} for a linear or XGBoost model, else None."""
    parts = _linear_parts(model)
    if parts is not None:
        coefs, means, stds = parts
        return {name: coef * (float(shot[name]) - mean) / std
                for name, coef, mean, std in zip(FEATURE_COLUMNS, coefs, means, stds)}
    if hasattr(model, "get_booster"):
        import xgboost as xgb

        row = pd.DataFrame([[float(shot[f]) for f in FEATURE_COLUMNS]], columns=FEATURE_COLUMNS)
        contribs = model.get_booster().predict(xgb.DMatrix(row), pred_contribs=True)[0]
        return dict(zip(FEATURE_COLUMNS, map(float, contribs[:-1])))  # last entry is the bias
    return None


def factor_contributions(model, shot) -> list:
    """[(factor, log-odds contribution)] vs an average shot, largest effect first."""
    per_feature = _feature_contributions(model, shot)
    if per_feature is None:
        return []
    grouped = [(factor, sum(per_feature[f] for f in feats))
               for factor, feats in FACTOR_GROUPS.items()]
    return sorted(grouped, key=lambda kv: abs(kv[1]), reverse=True)


def describe_factor(factor: str, shot, helped: bool) -> str:
    """A plain-language sentence for one factor, grounded in this shot's numbers."""
    dist = float(shot["distance"])
    angle = math.degrees(float(shot["angle"]))
    blockers = int(shot["defenders_in_cone"])
    space = float(shot["nearest_defender_dist"])
    keeper_out = float(shot["keeper_dist_to_goal"])

    if factor == "Distance":
        return (f"{dist:.0f} yards out — closer than a typical shot, so less time for the keeper."
                if helped else f"{dist:.0f} yards out — from that far, most shots miss or get saved.")
    if factor == "Angle":
        return (f"A {angle:.0f}° window between the posts — plenty of goal to aim at."
                if helped else f"Only a {angle:.0f}° window between the posts — not much goal to aim at.")
    if factor == "Bodies in the way":
        if helped:
            return "Hardly anyone between the ball and the goal."
        return f"{blockers} defender{'s' if blockers != 1 else ''} in the shooting cone, ready to block."
    if factor == "Space to shoot":
        return (f"The nearest defender was {space:.0f} yards away — time to pick a spot."
                if helped else f"A defender was within {space:.0f} yard{'s' if round(space) != 1 else ''} — no time to set.")
    if factor == "Goalkeeper":
        return (f"The keeper was {keeper_out:.0f} yards off their line, leaving room to beat them."
                if helped else "The keeper was well set to cover this shot.")
    if factor == "Header":
        return ("Struck with the foot — more power and control than a header."
                if helped else "A header — much harder to place and power than a kick.")
    if factor == "Pressure":
        return ("No one was closing the shooter down."
                if helped else "A defender was closing the shooter down.")
    if factor == "One-on-one":
        return ("Through on goal, one-on-one with the keeper."
                if helped else "Not a one-on-one — defenders were still involved.")
    if factor == "First time":
        return ("Hit first time, before the defence could reset."
                if helped else "Hit first time — less control over the strike.")
    if factor == "The final ball":
        if int(shot.get("assist_through_ball", 0)):
            return "Set up by a through ball — those create clean chances."
        if int(shot.get("assist_cutback", 0)):
            return "Set up by a cutback — the ball comes back to an unmarked shooter."
        if int(shot.get("assist_cross", 0)):
            return ("Set up by a cross." if helped
                    else "Set up by a cross — the ball arrives fast and hard to control.")
        return ("No standout pass created it." if not helped
                else "The build-up worked in the shooter's favour.")
    if factor == "Phase of play":
        return ("Came from a set-piece pattern." if helped
                else "Came from regular open play.")
    return factor


def reasons(model, shot, n: int = 3) -> dict:
    """The strongest factors pushing the chance up and down.

    Returns ``{"helped": [(emoji, factor, sentence)], "hurt": [...]}`` with at
    most ``n`` of each, skipping negligible effects.
    """
    helped, hurt = [], []
    for factor, effect in factor_contributions(model, shot):
        if abs(effect) < MIN_EFFECT or factor in NEVER_SHOWN:
            continue
        if factor in PRESENCE_ONLY and not any(int(shot[f]) for f in FACTOR_GROUPS[factor]):
            continue
        bucket = helped if effect > 0 else hurt
        if len(bucket) < n:
            bucket.append((FACTOR_EMOJI[factor], factor, describe_factor(factor, shot, effect > 0)))
    return {"helped": helped, "hurt": hurt}
