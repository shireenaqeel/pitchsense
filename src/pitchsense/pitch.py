"""Draw a football pitch in StatsBomb coordinates with matplotlib.

StatsBomb pitches are 120x80 yards. The attacking goal is at x=120. All the
markings below are in those units so shot and freeze-frame locations can be
plotted directly on top without any transform.
"""

import matplotlib.pyplot as plt
from matplotlib.patches import Arc, Circle, Rectangle

PITCH_LENGTH = 120.0
PITCH_WIDTH = 80.0
LINE_COLOR = "#c8c8c8"
PITCH_COLOR = "#3a7d44"


def draw_pitch(ax=None, pitch_color: str = PITCH_COLOR, line_color: str = LINE_COLOR):
    """Draw pitch markings onto ``ax`` (created if not given) and return it."""
    if ax is None:
        _, ax = plt.subplots(figsize=(12, 8))

    ax.set_facecolor(pitch_color)
    ax.set_xlim(-3, PITCH_LENGTH + 3)
    ax.set_ylim(-3, PITCH_WIDTH + 3)
    ax.set_aspect("equal")
    ax.axis("off")

    line = {"color": line_color, "lw": 2, "zorder": 1}

    # Outline and halfway line.
    ax.add_patch(Rectangle((0, 0), PITCH_LENGTH, PITCH_WIDTH, fill=False, **line))
    ax.plot([60, 60], [0, PITCH_WIDTH], **line)
    ax.add_patch(Circle((60, 40), 10, fill=False, **line))
    ax.add_patch(Circle((60, 40), 0.4, color=line_color, zorder=1))

    # Penalty and six-yard boxes, penalty spots, both ends.
    for spot_x, box_x, six_x, arc_x, arc_theta in (
        (12, 0, 0, 12, (-53, 53)),
        (108, 102, 114, 108, (127, 233)),
    ):
        ax.add_patch(Rectangle((box_x, 18), 18, 44, fill=False, **line))
        ax.add_patch(Rectangle((six_x, 30), 6, 20, fill=False, **line))
        ax.add_patch(Circle((spot_x, 40), 0.4, color=line_color, zorder=1))
        ax.add_patch(Arc((arc_x, 40), 20, 20, theta1=arc_theta[0], theta2=arc_theta[1], **line))

    # Goals.
    for goal_x, width in ((0, -2), (PITCH_LENGTH, 2)):
        ax.add_patch(Rectangle((goal_x, 36), width, 8, fill=False, **line))

    return ax
