"""PitchSense quiz — predict a shot's chance, then compare to the trained model.

Run with:  streamlit run streamlit_app.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

import joblib
import matplotlib.pyplot as plt
import numpy as np
import streamlit as st

from pitchsense.concepts import (
    concept_scores,
    concept_weights,
    pick_adaptive,
    shot_concepts,
    update_progress,
)
from pitchsense.data import load_shots
from pitchsense.features import FEATURE_COLUMNS, build_feature_frame
from pitchsense.quiz import brier_points, explain_shot
from pitchsense.train import PRIMARY_MODEL_PATH
from pitchsense.viz import plot_shot


@st.cache_data(show_spinner="Loading match data…")
def load_quiz_shots():
    feats = build_feature_frame(load_shots())
    feats = feats[feats["shot_freeze_frame"].notna()].reset_index(drop=True)
    return feats


@st.cache_data(show_spinner=False)
def concepts_per_shot(_shots):
    """Concept tags for every shot in the pool, aligned to its row index."""
    return [shot_concepts(_shots.iloc[i]) for i in range(len(_shots))]


@st.cache_resource
def load_model():
    return joblib.load(PRIMARY_MODEL_PATH)


def model_xg(model, shot) -> float:
    return float(model.predict_proba(shot[FEATURE_COLUMNS].to_frame().T)[:, 1][0])


def new_round(shot_tags):
    """Pick the next shot, biased toward the concepts the user is weakest at."""
    weights = concept_weights(st.session_state.concept_progress)
    st.session_state.shot_idx = pick_adaptive(
        shot_tags, weights, st.session_state.rng
    )
    st.session_state.revealed = False


def init_state(shot_tags):
    if "shot_idx" not in st.session_state:
        st.session_state.total_points = 0
        st.session_state.model_points = 0
        st.session_state.rounds = 0
        st.session_state.concept_progress = {}
        st.session_state.rng = np.random.default_rng()
        new_round(shot_tags)


st.set_page_config(page_title="PitchSense", page_icon="⚽", layout="wide")
st.title("⚽ PitchSense — Predict the Shot")
st.caption(
    "You're the shooter's coach. Look at the freeze-frame — the players as they "
    "were the instant the shot was struck — and estimate the chance it scores. "
    "Then see how a model trained on real World Cup shots rated it."
)

shots = load_quiz_shots()
model = load_model()
shot_tags = concepts_per_shot(shots)
init_state(shot_tags)

shot = shots.iloc[st.session_state.shot_idx]
current_tags = shot_tags[st.session_state.shot_idx]

board, pitch = st.columns([1, 3])

with board:
    st.subheader("Scoreboard")
    rounds = st.session_state.rounds
    if rounds:
        st.metric("Your average", f"{st.session_state.total_points / rounds:.0f} / 100")
        st.metric("Model average", f"{st.session_state.model_points / rounds:.0f} / 100")
        st.caption(f"Rounds played: {rounds}")
    else:
        st.write("Make your first guess to get on the board.")

    st.caption("This shot: " + ", ".join(current_tags))

    scores = concept_scores(st.session_state.concept_progress)
    if scores:
        st.subheader("Where you stand")
        st.caption("Your average points per concept — the quiz serves weaker ones more often.")
        for concept, score in sorted(scores.items(), key=lambda kv: kv[1]):
            st.progress(int(round(score)), text=f"{concept} — {score:.0f}/100")

with pitch:
    fig, ax = plt.subplots(figsize=(11, 7))
    plot_shot(shot, xg=(model_xg(model, shot) if st.session_state.revealed else None),
              ax=ax, reveal=st.session_state.revealed)
    st.pyplot(fig)
    plt.close(fig)

guess_pct = st.slider("Your estimate: chance this shot scores", 0, 100, 25,
                      disabled=st.session_state.revealed)
guess = guess_pct / 100

if not st.session_state.revealed:
    if st.button("Reveal outcome", type="primary"):
        mxg = model_xg(model, shot)
        actual = int(shot["is_goal"])
        earned = brier_points(guess, actual)
        st.session_state.total_points += earned
        st.session_state.model_points += brier_points(mxg, actual)
        st.session_state.rounds += 1
        update_progress(st.session_state.concept_progress, current_tags, earned)
        st.session_state.last_guess = guess
        st.session_state.revealed = True
        st.rerun()
else:
    mxg = model_xg(model, shot)
    actual = int(shot["is_goal"])
    guess = st.session_state.get("last_guess", guess)
    earned = brier_points(guess, actual)

    if actual == 1:
        st.success("It was a GOAL.")
    else:
        st.error("No goal.")

    c1, c2, c3 = st.columns(3)
    c1.metric("Your estimate", f"{guess:.0%}")
    c2.metric("Model xG", f"{mxg:.0%}")
    c3.metric("Points this round", earned)

    st.info(explain_shot(shot, mxg, guess))
    st.button("Next shot", type="primary", on_click=new_round, args=(shot_tags,))
