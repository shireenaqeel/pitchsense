"""Animate a possession as a moving ball with a growing trail, saved as a GIF."""

from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # render frames without a display
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation, PillowWriter

from pitchsense.pitch import draw_pitch
from pitchsense.sequences import build_waypoints, interpolate_track

DOCS_DIR = Path(__file__).resolve().parents[2] / "docs"
BALL_COLOR = "#ffd500"


def animate_sequence(frames, save_path: Path, fps: int = 20, hold_frames: int = 20) -> Path:
    """Render interpolated ball frames to a GIF at ``save_path``.

    ``hold_frames`` extra copies of the final frame keep the animation paused on
    the finish so the outcome is readable before it loops.
    """
    frames = list(frames) + [frames[-1]] * hold_frames if frames else []

    fig, ax = plt.subplots(figsize=(12, 8))
    draw_pitch(ax)
    (trail,) = ax.plot([], [], color=BALL_COLOR, lw=2.5, alpha=0.8, zorder=5)
    ball = ax.scatter([], [], c="white", s=150, edgecolors="black", linewidths=1.5, zorder=6)
    title = ax.set_title("", fontsize=13, color="#222222")

    def update(i):
        seg = frames[: i + 1]
        trail.set_data([p["x"] for p in seg], [p["y"] for p in seg])
        current = frames[i]
        ball.set_offsets([[current["x"], current["y"]]])
        player = current["player"] or ""
        title.set_text(f"{current['action']} — {player}")
        return trail, ball, title

    anim = FuncAnimation(fig, update, frames=len(frames), interval=1000 / fps, blit=False)
    save_path.parent.mkdir(parents=True, exist_ok=True)
    anim.save(save_path, writer=PillowWriter(fps=fps))
    plt.close(fig)
    return save_path


def render_example_sequence(save_path: Path | None = None) -> Path:
    """Fetch a goal build-up, interpolate it, and save the animated replay."""
    from statsbombpy import sb

    from pitchsense.data import COMPETITION_ID, SEASON_ID
    from pitchsense.sequences import find_goal_possession, possession_events

    if save_path is None:
        save_path = DOCS_DIR / "example_sequence.gif"

    matches = sb.matches(competition_id=COMPETITION_ID, season_id=SEASON_ID)
    events = sb.events(match_id=matches["match_id"].iloc[0])
    possession = find_goal_possession(events)
    chain = possession_events(events, possession)

    waypoints = build_waypoints(chain)
    frames = interpolate_track(waypoints, frames_per_segment=14)
    animate_sequence(frames, save_path)
    return save_path


if __name__ == "__main__":
    path = render_example_sequence()
    print(f"Saved animated replay to {path}")
