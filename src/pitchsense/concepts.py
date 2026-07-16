"""Concept tagging, per-concept progress, and adaptive shot selection.

Each shot is tagged with one or more football concepts derived from its
features (a header, a long-range effort, a one-on-one, ...). The quiz tracks how
well the user estimates each concept and biases which shot comes next toward the
concepts they are weakest at — the "adaptive practice" idea, kept as simple,
testable functions with no UI or model dependencies.
"""

import numpy as np

# Feature thresholds (StatsBomb yards / radians) that define each concept.
CLOSE_RANGE_YARDS = 8.0
LONG_RANGE_YARDS = 25.0
TIGHT_ANGLE_RAD = np.radians(25)
CROWDED_DEFENDERS = 3

# Master list, in the order the dashboard should show them.
ALL_CONCEPTS = [
    "Close range",
    "Long range",
    "Tight angle",
    "Header",
    "One-on-one",
    "Under pressure",
    "Crowded box",
    "From cross",
    "Through ball",
    "Standard chance",
]


def shot_concepts(shot) -> list:
    """Return the concept tags for a shot. Always at least one tag."""
    tags = []
    distance = float(shot["distance"])
    if distance <= CLOSE_RANGE_YARDS:
        tags.append("Close range")
    if distance >= LONG_RANGE_YARDS:
        tags.append("Long range")
    if float(shot["angle"]) <= TIGHT_ANGLE_RAD:
        tags.append("Tight angle")
    if int(shot.get("is_header", 0)):
        tags.append("Header")
    if int(shot.get("is_one_on_one", 0)):
        tags.append("One-on-one")
    if int(shot.get("under_pressure", 0)):
        tags.append("Under pressure")
    if int(shot["defenders_in_cone"]) >= CROWDED_DEFENDERS:
        tags.append("Crowded box")
    if int(shot.get("assist_cross", 0)):
        tags.append("From cross")
    if int(shot.get("assist_through_ball", 0)):
        tags.append("Through ball")
    if not tags:
        tags.append("Standard chance")
    return tags


def update_progress(progress: dict, concepts, points: int) -> dict:
    """Record a round's points against each of its concepts (mutates & returns)."""
    for concept in concepts:
        record = progress.setdefault(concept, {"attempts": 0, "points": 0})
        record["attempts"] += 1
        record["points"] += points
    return progress


def concept_scores(progress: dict) -> dict:
    """Average points (0-100) per attempted concept."""
    return {
        concept: record["points"] / record["attempts"]
        for concept, record in progress.items()
        if record["attempts"] > 0
    }


def concept_weights(progress: dict, all_concepts=ALL_CONCEPTS,
                    floor: float = 0.1, explore: float = 1.5) -> dict:
    """Selection weight per concept: higher for weaker or unseen concepts.

    Unseen concepts get an exploration weight so they surface early. Seen ones
    are weighted by how far the user's average is from a perfect 100, so a weak
    concept is served more often than a strong one.
    """
    weights = {}
    for concept in all_concepts:
        record = progress.get(concept)
        if not record or record["attempts"] == 0:
            weights[concept] = explore
        else:
            avg = record["points"] / record["attempts"] / 100.0
            weights[concept] = floor + (1.0 - avg)
    return weights


def shot_weight(concepts, weights: dict) -> float:
    """A shot is as needy as its neediest concept."""
    return max((weights.get(concept, 1.0) for concept in concepts), default=1.0)


def pick_adaptive(concepts_per_shot, weights: dict, rng) -> int:
    """Weighted-random index into the shot pool, biased toward weak concepts."""
    w = np.array([shot_weight(c, weights) for c in concepts_per_shot], dtype=float)
    total = w.sum()
    if total <= 0:
        return int(rng.integers(len(concepts_per_shot)))
    return int(rng.choice(len(concepts_per_shot), p=w / total))
