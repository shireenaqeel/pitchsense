"""Smoke test: the whole Streamlit app renders every tab without an exception.

Streamlit draws the contents of every tab on each run, so one run covers the
lessons, the quiz, the sandbox and the explorers, in both modes. It reads the
committed caches and models, so it needs no network.
"""

from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

APP = str(Path(__file__).resolve().parents[1] / "streamlit_app.py")


@pytest.fixture
def app(monkeypatch):
    # Keep the smoke test on the local file store, whatever the environment says.
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    monkeypatch.delenv("SUPABASE_KEY", raising=False)
    return AppTest.from_file(APP, default_timeout=120)


@pytest.mark.parametrize("mode", ["Beginner", "Expert"])
def test_every_tab_renders(app, mode):
    app.run()
    app.sidebar.radio[0].set_value(mode).run()
    assert not app.exception, [e.value for e in app.exception]
    assert len(app.tabs) == 6


def test_leaderboard_uses_supabase_from_streamlit_secrets(app):
    # Streamlit Community Cloud passes settings as secrets. With them set, the
    # board goes to Supabase; this address can't resolve, so the app must show
    # its "can't be reached" note instead of crashing.
    import streamlit as st

    st.cache_resource.clear()
    app.secrets["SUPABASE_URL"] = "https://pitchsense-test.invalid"
    app.secrets["SUPABASE_KEY"] = "sb_publishable_test"
    app.run()
    app.sidebar.radio[0].set_value("Expert").run()
    st.cache_resource.clear()
    assert not app.exception, [e.value for e in app.exception]
    assert any("can't be reached" in c.value for c in app.caption)
