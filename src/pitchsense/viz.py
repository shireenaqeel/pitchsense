"""Render a single shot and its freeze-frame on a pitch.

The freeze-frame is StatsBomb's snapshot of every tracked player at the moment
the shot was struck. Plotting it shows the situation the shooter faced, and we
annotate it with the model's expected-goals value for that shot.
"""

from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # render to file without a display
import matplotlib.pyplot as plt
import numpy as np

from pitchsense.pitch import draw_pitch

DOCS_DIR = Path(__file__).resolve().parents[2] / "docs"

TEAMMATE_COLOR = "#2c7fb8"
OPPONENT_COLOR = "#d95f0e"
KEEPER_COLOR = "#111111"
SHOOTER_COLOR = "#ffffff"
BALL_COLOR = "#ffd500"


def _is_keeper(player) -> bool:
    pos = player.get("position")
    if isinstance(pos, dict):
        pos = pos.get("name", "")
    return isinstance(pos, str) and "Goalkeeper" in pos


def split_freeze_frame(freeze_frame):
    """Group freeze-frame players into teammates, outfield opponents, keeper.

    Returns a dict of lists of (x, y) points. Missing or malformed frames yield
    empty groups so callers don't need to special-case them.
    """
    groups = {"teammates": [], "opponents": [], "keeper": []}
    if not isinstance(freeze_frame, (list, np.ndarray)):
        return groups
    for player in freeze_frame:
        loc = player.get("location")
        if loc is None or len(loc) < 2:
            continue
        point = (float(loc[0]), float(loc[1]))
        if player.get("teammate", False):
            groups["teammates"].append(point)
        elif _is_keeper(player):
            groups["keeper"].append(point)
        else:
            groups["opponents"].append(point)
    return groups


def _scatter(ax, points, color, label, size=140, edge="#222222"):
    if not points:
        return
    xs, ys = zip(*points)
    ax.scatter(xs, ys, c=color, s=size, edgecolors=edge, linewidths=1, zorder=4, label=label)


def plot_shot(shot, xg=None, ax=None, save_path: Path | None = None, reveal: bool = True):
    """Plot a single shot row (a pandas Series) with its freeze-frame.

    When ``reveal`` is False the outcome is hidden: the ball path and the
    outcome/xG in the title are omitted so the shot can be used as a quiz prompt.
    """
    if ax is None:
        _, ax = plt.subplots(figsize=(12, 8))
    draw_pitch(ax)

    start = shot["location"]
    end = shot.get("shot_end_location")
    groups = split_freeze_frame(shot.get("shot_freeze_frame"))

    _scatter(ax, groups["teammates"], TEAMMATE_COLOR, "Teammates")
    _scatter(ax, groups["opponents"], OPPONENT_COLOR, "Defenders")
    _scatter(ax, groups["keeper"], KEEPER_COLOR, "Goalkeeper", size=170)

    # Ball path from the shot to where it ended up, drawn above the players so
    # the trajectory stays readable through a crowded box. Hidden until revealed
    # so it doesn't give away whether the shot found the net.
    if reveal and end is not None and len(end) >= 2:
        ax.annotate(
            "",
            xy=(end[0], end[1]),
            xytext=(start[0], start[1]),
            arrowprops=dict(arrowstyle="-|>", color=BALL_COLOR, lw=3,
                            shrinkA=8, shrinkB=2),
            zorder=6,
        )
    ax.scatter([start[0]], [start[1]], c=SHOOTER_COLOR, s=200, edgecolors="#000000",
               linewidths=1.5, zorder=7, label="Shot")

    if reveal:
        outcome = shot.get("shot_outcome", "")
        title = f"{shot.get('player', 'Shot')} — {outcome}"
        if xg is not None:
            title += f"  |  model xG: {xg:.2f}"
    else:
        title = "Where does this shot rank? Estimate the chance it scores."
    ax.set_title(title, color="#222222", fontsize=13)
    ax.legend(loc="lower left", framealpha=0.9)

    if save_path is not None:
        save_path.parent.mkdir(parents=True, exist_ok=True)
        ax.figure.savefig(save_path, bbox_inches="tight", dpi=130)
    return ax


def render_example(save_path: Path | None = None) -> Path:
    """Load data, score a notable goal with the model, and save its plot."""
    import joblib

    from pitchsense.data import load_shots
    from pitchsense.features import FEATURE_COLUMNS, build_feature_frame
    from pitchsense.train import PRIMARY_MODEL_PATH

    if save_path is None:
        save_path = DOCS_DIR / "example_shot.png"

    shots = load_shots()
    feats = build_feature_frame(shots)
    # Pick a goal from open play with players in the freeze-frame for a rich plot.
    goals = feats[(feats["is_goal"] == 1) & (feats["shot_freeze_frame"].notna())]
    goals = goals.sort_values("defenders_in_cone", ascending=False)
    shot = goals.iloc[0]

    xg = None
    if PRIMARY_MODEL_PATH.exists():
        model = joblib.load(PRIMARY_MODEL_PATH)
        xg = float(model.predict_proba(shot[FEATURE_COLUMNS].to_frame().T)[:, 1][0])

    plot_shot(shot, xg=xg, save_path=save_path)
    return save_path


if __name__ == "__main__":
    path = render_example()
    print(f"Saved shot visualization to {path}")
