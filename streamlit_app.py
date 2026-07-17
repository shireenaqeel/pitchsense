"""PitchSense — predict shots, and explore the tactical and player-role models.

Run with:  streamlit run streamlit_app.py

Three tabs: the predict-and-compare shot quiz, an explorer for the possession
tactical-pattern classifier, and an explorer for the player-role clustering. The
two explorer tabs degrade gracefully with a hint to train the model if it has not
been built yet.
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

import joblib
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
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
from pitchsense.leaderboard import MIN_ROUNDS, add_score, load_scores, make_entry, top
from pitchsense.quiz import brier_points, explain_shot
from pitchsense.roles import (
    METRICS_PATH as ROLES_METRICS_PATH,
    MODEL_PATH as ROLES_MODEL_PATH,
    PLAYERS_CACHE,
    ROLE_MAP_PATH,
    assign_roles,
    load_roles,
)
from pitchsense.tactics import (
    METRICS_PATH as TACTICS_METRICS_PATH,
    MODEL_PATH as TACTICS_MODEL_PATH,
    load_classifier,
    overall_means,
    predict_pattern,
)
from pitchsense.train import PRIMARY_MODEL_PATH
from pitchsense.viz import plot_shot


# --------------------------------------------------------------------------- #
# Shared loaders
# --------------------------------------------------------------------------- #
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


@st.cache_resource
def load_tactics_bundle():
    return load_classifier()


@st.cache_resource
def load_roles_bundle():
    return load_roles()


@st.cache_data(show_spinner=False)
def load_players_frame():
    return pd.read_parquet(PLAYERS_CACHE)


def model_xg(model, shot) -> float:
    return float(model.predict_proba(shot[FEATURE_COLUMNS].to_frame().T)[:, 1][0])


# --------------------------------------------------------------------------- #
# Quiz tab
# --------------------------------------------------------------------------- #
def new_round(shot_tags):
    """Pick the next shot, biased toward the concepts the user is weakest at."""
    weights = concept_weights(st.session_state.concept_progress)
    st.session_state.shot_idx = pick_adaptive(shot_tags, weights, st.session_state.rng)
    st.session_state.revealed = False


def init_state(shot_tags):
    if "shot_idx" not in st.session_state:
        st.session_state.total_points = 0
        st.session_state.model_points = 0
        st.session_state.rounds = 0
        st.session_state.concept_progress = {}
        st.session_state.saved_score = False
        st.session_state.rng = np.random.default_rng()
        new_round(shot_tags)


def render_leaderboard(rounds: int):
    """Show the top scores and, once qualified, a form to save this session."""
    st.subheader("🏆 Leaderboard")
    leaders = top(load_scores(), n=10)
    if leaders:
        st.dataframe(
            [
                {"#": i + 1, "Player": s["name"], "Avg": f"{s['avg_points']:.0f}",
                 "vs model": f"{s['vs_model']:+.0f}", "Rounds": s["rounds"]}
                for i, s in enumerate(leaders)
            ],
            hide_index=True, width="stretch",
        )
    else:
        st.caption(f"No qualifying scores yet — play {MIN_ROUNDS}+ rounds and save to start it.")

    if st.session_state.get("saved_score"):
        st.caption("Your score is saved ✅")
    elif rounds >= MIN_ROUNDS:
        with st.form("save_score"):
            name = st.text_input("Name for the leaderboard", max_chars=20)
            if st.form_submit_button("Save my score"):
                add_score(make_entry(
                    name, st.session_state.total_points,
                    st.session_state.model_points, rounds,
                ))
                st.session_state.saved_score = True
                st.rerun()
    else:
        st.caption(f"Play {MIN_ROUNDS - rounds} more round(s) to save a score.")


def render_quiz():
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

        render_leaderboard(rounds)

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


# --------------------------------------------------------------------------- #
# Tactical patterns tab
# --------------------------------------------------------------------------- #
def render_tactics():
    st.subheader("Tactical patterns")
    st.caption(
        "Every possession is grouped by *how* the ball was moved — patiently worked, "
        "driven directly, or won high and used fast. This is unsupervised k-means over "
        "possession shape-and-tempo features; the labels interpret the clusters."
    )
    if not (TACTICS_MODEL_PATH.exists() and TACTICS_METRICS_PATH.exists()):
        st.info("Train the classifier first, then reload:  `python -m pitchsense.tactics`")
        return

    metrics = json.loads(TACTICS_METRICS_PATH.read_text(encoding="utf-8"))
    st.dataframe(
        [
            {"Pattern": c["label"], "Possessions": c["size"],
             "Passes": round(c["means"]["n_passes"], 1),
             "Duration (s)": round(c["means"]["duration"], 1),
             "Upfield (y)": round(c["means"]["net_forward"], 1),
             "Directness": round(c["means"]["directness"], 2),
             "Ends in shot": f"{c['means']['ends_in_shot'] * 100:.0f}%"}
            for c in metrics["clusters"]
        ],
        hide_index=True, width="stretch",
    )
    st.caption(
        f"{metrics['n_possessions']:,} possessions · k={metrics['n_clusters']} · "
        f"silhouette {metrics['silhouette']:.2f}"
    )

    st.markdown("**Classify a possession**")
    st.caption("Adjust a few numbers and watch the model label the move; the other "
               "features stay at the dataset average.")
    means = overall_means()
    bundle = load_tactics_bundle()

    c1, c2 = st.columns(2)
    passes = c1.slider("Passes", 1, 30, int(round(means["n_passes"])))
    duration = c2.slider("Duration (seconds)", 1, 90, int(round(means["duration"])))
    net_forward = c1.slider("Net upfield yards", -40, 110, int(round(means["net_forward"])))
    speed = c2.slider("Upfield speed (yards/sec)", 0.0, 12.0,
                      float(round(means["forward_speed"], 1)), step=0.5)

    feats = {**means, "n_passes": passes, "duration": duration,
             "net_forward": net_forward, "forward_speed": speed}
    st.success(f"The model reads this as: **{predict_pattern(bundle, feats)}**")


# --------------------------------------------------------------------------- #
# Player roles tab
# --------------------------------------------------------------------------- #
def render_roles():
    st.subheader("Player roles")
    st.caption(
        "Players clustered by *how they play* — where they operate, how much they roam, "
        "and the mix of passing, carrying, dribbling, shooting and defending — not the "
        "position they are listed at. k-means over behavioural features, projected with PCA."
    )
    if not (ROLES_MODEL_PATH.exists() and ROLES_METRICS_PATH.exists()):
        st.info("Train the clusterer first, then reload:  `python -m pitchsense.roles`")
        return

    if ROLE_MAP_PATH.exists():
        st.image(str(ROLE_MAP_PATH),
                 caption="Players projected to two PCA dimensions, coloured by role cluster.")

    metrics = json.loads(ROLES_METRICS_PATH.read_text(encoding="utf-8"))
    st.dataframe(
        [
            {"Role": c["label"], "Players": c["size"], "Purity": f"{c['purity'] * 100:.0f}%",
             "Avg x": round(c["means"]["avg_x"], 1),
             "Width": round(c["means"]["lateral"], 1),
             "Pass share": round(c["means"]["pass_share"], 2),
             "Defensive": round(c["means"]["defensive_share"], 2),
             "Dribble": round(c["means"]["dribble_share"], 3)}
            for c in metrics["clusters"]
        ],
        hide_index=True, width="stretch",
    )
    st.caption(
        f"{metrics['n_players']} players · k={metrics['n_clusters']} · "
        f"silhouette {metrics['silhouette']:.2f} · purity = share of the cluster "
        "actually listed at the label position"
    )

    if not PLAYERS_CACHE.exists():
        st.caption("Player lookup needs the cached player data — run "
                   "`python -m pitchsense.roles` once to build it.")
        return

    st.markdown("**Look up a player**")
    st.caption("See the role the model puts a player in, and how it compares to the "
               "position they were listed at.")
    data = load_players_frame()
    bundle = load_roles_bundle()
    roles = assign_roles(bundle, data)

    names = sorted(data["player"].tolist())
    # Open on a recognisable name if present (full StatsBomb names vary), else first.
    default = next((i for i, n in enumerate(names) if "Messi" in n or "Ronaldo" in n), 0)
    pick = st.selectbox("Player", names, index=default)
    idx = data.index[data["player"] == pick][0]
    row = data.loc[idx]

    c1, c2 = st.columns(2)
    c1.metric("Detected role", roles.loc[idx])
    c2.metric("Listed position", row["position"])
    st.caption(
        f"avg x {row['avg_x']:.0f} · width {row['lateral']:.0f} · "
        f"pass share {row['pass_share']:.2f} · dribble {row['dribble_share']:.3f} · "
        f"shots {row['shot_share']:.3f} · defensive {row['defensive_share']:.2f}"
    )


# --------------------------------------------------------------------------- #
# Layout
# --------------------------------------------------------------------------- #
st.set_page_config(page_title="PitchSense", page_icon="⚽", layout="wide")
st.title("⚽ PitchSense")

tab_quiz, tab_tactics, tab_roles = st.tabs(
    ["🎯 Predict the shot", "🧭 Tactical patterns", "🧑‍🤝‍🧑 Player roles"]
)
with tab_quiz:
    render_quiz()
with tab_tactics:
    render_tactics()
with tab_roles:
    render_roles()
