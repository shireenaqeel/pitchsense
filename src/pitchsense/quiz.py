"""Scoring and explanation logic for the predict-and-compare quiz.

Kept free of any UI or Streamlit imports so the logic can be unit tested. The
user estimates the chance a shot is scored; we score that estimate against the
actual outcome and explain how it compares to the model and to the situation.
"""

import numpy as np


def clamp01(value: float) -> float:
    return min(max(value, 0.0), 1.0)


def brier_points(guess: float, actual: int) -> int:
    """Score a probability guess against the 0/1 outcome, 0-100.

    Uses the Brier score (squared error) turned into points: a perfect guess of
    the outcome scores 100, guessing 0.5 scores 75, the worst possible scores 0.
    """
    guess = clamp01(guess)
    return int(round(100 * (1 - (guess - actual) ** 2)))


def model_gap(guess: float, model_xg: float) -> float:
    """Absolute difference between the user's estimate and the model's xG."""
    return abs(clamp01(guess) - clamp01(model_xg))


def verdict(guess: float, model_xg: float, tolerance: float = 0.1) -> str:
    """A short read on how the user's estimate compares to the model."""
    gap = model_gap(guess, model_xg)
    if gap <= tolerance:
        return "close to the model"
    return "higher than the model" if guess > model_xg else "lower than the model"


def explain_shot(shot, model_xg: float, guess: float) -> str:
    """Plain-language explanation of the chance, the model, and the outcome."""
    distance = float(shot["distance"])
    angle_deg = float(np.degrees(shot["angle"]))
    defenders = int(shot["defenders_in_cone"])

    parts = [
        f"The shot was {distance:.0f} yards from goal at a {angle_deg:.0f}° "
        "angle to the posts."
    ]
    if defenders == 0:
        parts.append("There were no defenders between the ball and the goal.")
    elif defenders == 1:
        parts.append("There was 1 defender in the shooting lane.")
    else:
        parts.append(f"There were {defenders} defenders in the shooting lane.")

    if int(shot.get("is_header", 0)):
        parts.append("It was a header, which typically lowers the chance.")
    if int(shot.get("under_pressure", 0)):
        parts.append("The shooter was under pressure.")

    parts.append(
        f"The model rated it {model_xg:.0%} and your estimate was {guess:.0%} "
        f"({verdict(guess, model_xg)})."
    )
    parts.append("It was actually a goal." if int(shot["is_goal"]) == 1 else "It did not go in.")
    return " ".join(parts)


# --------------------------------------------------------------------------- #
# Beginner mode: name the chance instead of picking a percentage
# --------------------------------------------------------------------------- #
# A 0-100 slider asks a newcomer for a precision they do not have yet. Beginner
# mode instead asks them to *name* the chance, the way a commentator would. The
# bands follow the served model's xG distribution over the quiz pool (roughly
# 48% / 32% / 13% / 6% / 1.5% of shots), and each carries a representative
# probability so the same Brier scoring still applies under the hood.
# (label, emoji, lower xG bound, representative probability, plain-language gloss)
CHANCE_BUCKETS = [
    ("Speculative", "🎲", 0.00, 0.03, "a hopeful effort — about 1 in 30 go in"),
    ("Half chance", "🤏", 0.05, 0.08, "a sight of goal, but most miss — about 1 in 12"),
    ("Good chance", "👍", 0.12, 0.18, "a real opening — roughly 1 in 5"),
    ("Big chance", "🔥", 0.25, 0.35, "should test the keeper — about 1 in 3"),
    ("Sitter", "😱", 0.50, 0.65, "you'd expect a goal — 2 in 3 or better"),
]
BUCKET_LABELS = [b[0] for b in CHANCE_BUCKETS]


def bucket_index(xg: float) -> int:
    """Index of the chance band an xG value falls into."""
    idx = 0
    for i, (_, _, lower, _, _) in enumerate(CHANCE_BUCKETS):
        if xg >= lower:
            idx = i
    return idx


def bucket_label(xg: float) -> str:
    """'Big chance' etc. for an xG value."""
    return BUCKET_LABELS[bucket_index(xg)]


def bucket_points(guess_label: str, model_xg: float) -> int:
    """Beginner points: did you read the chance the way the model did?

    Scoring a beginner against the 0/1 outcome is noisy — a correctly spotted
    long shot that happens to fly in would be punished. Against the model's band
    the feedback is consistent, which is what builds intuition: 100 for the same
    band, 50 for a neighbouring band, 0 otherwise.
    """
    gap = abs(BUCKET_LABELS.index(guess_label) - bucket_index(model_xg))
    return {0: 100, 1: 50}.get(gap, 0)


def out_of_100(xg: float) -> int:
    """xG as 'goals per 100 shots like this', never below 1 for display."""
    return max(1, int(round(clamp01(xg) * 100)))


def reaction(points: int) -> str:
    """A short, upbeat reaction to a round's points."""
    if points >= 90:
        return "🎯 Spot on!"
    if points >= 70:
        return "👌 Good read."
    if points >= 50:
        return "🤔 Close-ish."
    return "😬 Way off — have a look at why."


def gap_points(guess: float, model_xg: float) -> int:
    """How closely an exact estimate matched the model, on the same 0-100 scale."""
    gap = model_gap(guess, model_xg)
    for limit, points in ((0.05, 100), (0.10, 75), (0.20, 50)):
        if gap <= limit:
            return points
    return 0


def bucket_balance(xgs) -> np.ndarray:
    """Per-shot selection weights that soften the pile-up of long shots.

    Nearly half the pool is 'Speculative', so uniform sampling would make a
    beginner's session mostly hopeful 30-yard efforts. Weighting each shot by the
    inverse square root of its band's size serves big chances and sitters more
    often without letting the rare bands dominate.
    """
    bands = np.array([bucket_index(x) for x in xgs])
    counts = np.bincount(bands, minlength=len(CHANCE_BUCKETS)).astype(float)
    return 1.0 / np.sqrt(counts[bands])


def outcome_text(outcome: str) -> str:
    """Friendly wording for StatsBomb shot outcomes."""
    return {
        "Goal": "GOAL!",
        "Saved": "Saved by the keeper",
        "Saved Off T": "Saved, going wide",
        "Saved to Post": "Saved onto the post",
        "Off T": "Off target",
        "Wayward": "Way off target",
        "Blocked": "Blocked by a defender",
        "Post": "Hit the woodwork!",
    }.get(outcome, str(outcome))
