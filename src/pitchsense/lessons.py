"""Bite-sized lessons: learn one idea, test it in the sandbox, then practise it.

Each lesson teaches a single thing that makes a chance better or worse. It has a
short explanation, a "which is the better chance?" comparison of two sandbox
scenarios (the learner commits to an answer before the model reveals both xG
values), and then a short practice set of real shots tagged with the lesson's
concepts. Learn -> predict -> check -> practise, in a couple of minutes.

Pure data plus small helpers, with no UI, so it can be unit tested.
"""

from dataclasses import dataclass, replace

from pitchsense.concepts import ALL_CONCEPTS
from pitchsense.sandbox import PRESETS, Scenario

PRACTICE_ROUNDS = 3


@dataclass(frozen=True)
class Lesson:
    id: str
    emoji: str
    title: str
    hook: str             # one line shown on the lesson card
    body: str             # the explanation, in plain language (markdown)
    takeaway: str         # the single sentence to remember
    compare: tuple        # ((label, Scenario), (label, Scenario)) — spot the better chance
    concepts: tuple = ()  # practice shots must carry one of these tags; () = any shot
    expert_note: str = ""  # extra depth shown in Expert mode


_BOX = PRESETS["Edge of the box"]

LESSONS = [
    Lesson(
        id="xg", emoji="⚽", title="What is xG?",
        hook="Every shot has a price tag. Learn to read it.",
        body=(
            "**Expected goals (xG)** is the chance a shot goes in, judged *before* "
            "the ball is struck. It's worked out from thousands of real shots: of "
            "all the shots taken from a similar spot, in a similar situation, how "
            "many became goals?\n\n"
            "An xG of **0.30** means *about 30 of every 100 shots like this go in*. "
            "It doesn't care who took it or whether it went in. It only rates how "
            "good the chance was.\n\n"
            "That's why a team can lose a match while 'winning the xG': they made "
            "better chances and didn't take them."
        ),
        takeaway="xG rates the chance, not the finish: goals per 100 shots like this.",
        compare=(("A — penalty-spot tap-in", PRESETS["Penalty-spot tap-in"]),
                 ("B — long-range screamer", PRESETS["Long-range screamer"])),
        expert_note=(
            "PitchSense's model is gradient-boosted trees (XGBoost) over 17 features "
            "from the shot and its freeze-frame, trained on ~7,500 shots from six "
            "international tournaments plus ~37,500 from four 2015/16 club leagues "
            "(ROC AUC 0.80 on tournaments it never saw, in line with commercial "
            "pre-shot xG). Penalties are excluded: at ~0.76 xG they'd distort it."
        ),
    ),
    Lesson(
        id="distance", emoji="📏", title="Get closer",
        hook="The single biggest factor in any chance.",
        body=(
            "The closer you are, the less time the keeper has to react and the "
            "less room the ball has to drift wide. Close range is by far the biggest "
            "thing that makes a chance good.\n\n"
            "Most shots from outside the penalty box (18+ yards) are long shots. "
            "They're exciting when they fly in, but that's rare, which is why "
            "coaches tell players to work the ball closer."
        ),
        takeaway="Distance is king: every step closer is worth a lot.",
        compare=(("A — edge of the box", _BOX),
                 ("B — same, 7 yards closer", replace(_BOX, x=108))),
        concepts=("Close range", "Long range"),
        expert_note=(
            "Angle and distance carry the two largest standardised coefficients in "
            "the served model. They're correlated (closer usually means a wider "
            "angle), so the model splits the credit between them."
        ),
    ),
    Lesson(
        id="angle", emoji="📐", title="Mind the angle",
        hook="Close isn't enough if you can barely see the goal.",
        body=(
            "Draw a line from the ball to each goalpost. The gap between those "
            "lines is the **angle**: how much of the goal you can actually aim at.\n\n"
            "From the middle of the pitch the whole goal is open. Out by the "
            "byline, even a yard away, the goal shrinks to a sliver, and the keeper "
            "can cover most of it just by standing at the near post."
        ),
        takeaway="Central beats wide: a narrow angle can make a close shot a poor one.",
        compare=(("A — penalty spot, central", PRESETS["Penalty-spot tap-in"]),
                 ("B — closer, but by the byline", replace(PRESETS["Tight angle by the byline"],
                                                           blockers=0, marker="Free"))),
        concepts=("Tight angle",),
        expert_note="The feature is the angle the goal mouth subtends at the shot, in radians.",
    ),
    Lesson(
        id="blockers", emoji="🧱", title="Bodies in the way",
        hook="Every defender in the cone is a chance to block it.",
        body=(
            "Picture a triangle from the ball to both posts: the **shooting cone**. "
            "Every defender standing in it can block the shot, and every blocker "
            "makes the keeper's job easier.\n\n"
            "Watch the yellow cone on the pitch after each reveal. A shot through a "
            "crowded cone is a low-percentage effort, even close up."
        ),
        takeaway="Count the bodies in the cone: an empty cone is a big chance.",
        compare=(("A — edge of the box, 2 defenders in the way", _BOX),
                 ("B — same spot, clear sight of goal", replace(_BOX, blockers=0))),
        concepts=("Crowded box",),
        expert_note=(
            "Three freeze-frame features describe this: defenders in the cone, in the "
            "direct lane to goal centre, and goal-side of the ball. They were the "
            "first freeze-frame batch that lifted CV AUC from 0.778 to 0.788."
        ),
    ),
    Lesson(
        id="header", emoji="🗣️", title="Heads or feet?",
        hook="Why a header from 8 yards is worse than a kick from 12.",
        body=(
            "Heading a ball is hard. You can't generate much power, it's tricky to "
            "aim, and the ball usually arrives fast from a cross with defenders "
            "jumping alongside you.\n\n"
            "So from the same spot, a header is a much worse chance than a shot "
            "with the foot. Headers only become big chances when they're very "
            "close and unchallenged."
        ),
        takeaway="Headers are hard: knock a big chunk off the chance.",
        compare=(("A — header from a cross", PRESETS["Header from a cross"]),
                 ("B — same spot, on the foot", replace(PRESETS["Header from a cross"],
                                                        header=False))),
        concepts=("Header",),
    ),
    Lesson(
        id="one_on_one", emoji="🏃", title="Through on goal",
        hook="Just you and the keeper. Should you score?",
        body=(
            "A **one-on-one** is when only the goalkeeper stands between the "
            "attacker and the goal. They're big chances, but not as big as fans "
            "think: the keeper rushing out shrinks the angle, and the pressure is on "
            "the shooter.\n\n"
            "They usually come from a **through ball**, a pass played into the "
            "space behind the defence for the attacker to run onto."
        ),
        takeaway="One-on-ones are big chances, but roughly a coin-flip, not a certainty.",
        compare=(("A — through on goal", PRESETS["Through on goal"]),
                 ("B — same spot, defenders back", replace(PRESETS["Through on goal"],
                                                           blockers=2, marker="Close",
                                                           keeper="On the line",
                                                           one_on_one=False))),
        concepts=("One-on-one", "Through ball"),
    ),
    Lesson(
        id="pressure", emoji="😤", title="Feel the pressure",
        hook="A defender breathing down your neck changes everything.",
        body=(
            "When a defender is closing the shooter down, there's no time to set "
            "your feet, look up, or pick a corner. Shots **under pressure** are "
            "snatched, and more of them miss.\n\n"
            "The flip side: space. A shooter with five yards around them has time to "
            "pick their spot."
        ),
        takeaway="Time and space make chances; pressure takes them away.",
        compare=(("A — edge of the box, defender on you", replace(_BOX, marker="Right on you",
                                                                  under_pressure=True)),
                 ("B — same spot, in space", replace(_BOX, marker="Some space"))),
        concepts=("Under pressure",),
    ),
    Lesson(
        id="final_ball", emoji="🎁", title="The final ball",
        hook="How the ball arrives decides how good the chance is.",
        body=(
            "The pass before the shot matters. A **cross** in the air is hard to "
            "control and often met with a header. A **cutback**, pulled back from "
            "the byline along the ground, finds a shooter facing goal while "
            "defenders are running the wrong way. A **through ball** puts the "
            "attacker in behind.\n\n"
            "That's why modern teams love cutbacks and work so hard to get in behind."
        ),
        takeaway="Cutbacks and through balls make cleaner chances than crosses.",
        compare=(("A — header from a cross", PRESETS["Header from a cross"]),
                 ("B — cutback to the penalty spot", PRESETS["Cutback to the penalty spot"])),
        concepts=("From cross", "Through ball"),
    ),
]

LESSONS_BY_ID = {lesson.id: lesson for lesson in LESSONS}


def practice_pool(concepts_per_shot, lesson: Lesson) -> list:
    """Indices of shots that exercise the lesson's concepts (all shots if none)."""
    if not lesson.concepts:
        return list(range(len(concepts_per_shot)))
    wanted = set(lesson.concepts)
    return [i for i, tags in enumerate(concepts_per_shot) if wanted & set(tags)]


def concept_goal_rate(shots, concepts_per_shot, concept: str) -> tuple:
    """(shots carrying the concept, share of them that were goals)."""
    hits = [i for i, tags in enumerate(concepts_per_shot) if concept in tags]
    if not hits:
        return 0, 0.0
    return len(hits), float(shots["is_goal"].iloc[hits].mean())


def better_option(xg_a: float, xg_b: float) -> str:
    """'A' or 'B', whichever scenario the model rates higher."""
    return "A" if xg_a >= xg_b else "B"


# Every concept a lesson practises must be a real concept tag.
assert all(c in ALL_CONCEPTS for lesson in LESSONS for c in lesson.concepts)
