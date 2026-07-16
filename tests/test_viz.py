"""Tests for the pitch renderer and freeze-frame grouping."""

import matplotlib

matplotlib.use("Agg")

import numpy as np

from pitchsense.pitch import PITCH_LENGTH, PITCH_WIDTH, draw_pitch
from pitchsense.viz import split_freeze_frame


def test_draw_pitch_sets_equal_aspect_and_limits():
    ax = draw_pitch()
    assert ax.get_aspect() == 1.0
    xlim = ax.get_xlim()
    ylim = ax.get_ylim()
    assert xlim[0] <= 0 and xlim[1] >= PITCH_LENGTH
    assert ylim[0] <= 0 and ylim[1] >= PITCH_WIDTH


def test_draw_pitch_adds_markings():
    ax = draw_pitch()
    # Outline, two boxes, two six-yard boxes, two goals -> several patches.
    assert len(ax.patches) >= 7


def test_split_freeze_frame_groups_players():
    ff = [
        {"teammate": True, "location": [90.0, 40.0]},
        {"teammate": False, "location": [110.0, 40.0], "position": {"name": "Center Back"}},
        {"teammate": False, "location": [119.0, 40.0], "position": {"name": "Goalkeeper"}},
    ]
    groups = split_freeze_frame(ff)
    assert groups["teammates"] == [(90.0, 40.0)]
    assert groups["opponents"] == [(110.0, 40.0)]
    assert groups["keeper"] == [(119.0, 40.0)]


def test_split_freeze_frame_handles_missing_and_arrays():
    assert split_freeze_frame(None) == {"teammates": [], "opponents": [], "keeper": []}
    ff = np.array([{"teammate": True, "location": np.array([50.0, 30.0])}], dtype=object)
    groups = split_freeze_frame(ff)
    assert groups["teammates"] == [(50.0, 30.0)]


def test_split_freeze_frame_skips_players_without_location():
    ff = [{"teammate": False, "location": None}, {"teammate": True}]
    groups = split_freeze_frame(ff)
    assert groups == {"teammates": [], "opponents": [], "keeper": []}
