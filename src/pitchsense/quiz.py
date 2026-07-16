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
