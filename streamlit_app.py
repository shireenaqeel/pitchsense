"""PitchSense — learn to read football through real shots and a model trained on them.

Run with:  streamlit run streamlit_app.py

Tabs: bite-sized lessons (learn an idea, spot the better chance, practise it on
real shots), the free-play shot quiz, a 'be the striker' sandbox where the real
model rates a chance you build, explorers for the tactical-pattern and
player-role models, and an 'under the hood' page with the modelling details.

A Beginner / Expert toggle in the sidebar changes how you answer (name the chance
vs. an exact percentage), how you are scored, and how much technical detail is
shown. The explorer tabs degrade gracefully with a hint to train the model if it
has not been built yet.
"""

import json
import logging
import os
import sys
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

# Our own log lines go to stdout next to Streamlit's, which logs uncaught app
# exceptions with their traceback; Streamlit Cloud's log panel shows both.
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("pitchsense.app")

import joblib
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import streamlit as st
from matplotlib import colormaps
from matplotlib.cm import ScalarMappable
from matplotlib.colors import Normalize

from pitchsense.concepts import (
    concept_scores,
    concept_weights,
    pick_adaptive,
    shot_concepts,
    update_progress,
)
from pitchsense.data import load_shots
from pitchsense.explain import reasons
from pitchsense.features import (
    FEATURE_COLUMNS,
    build_feature_frame,
    placement_from_center,
    placement_height,
)
from pitchsense.leaderboard import (
    MIN_ROUNDS,
    LeaderboardError,
    board,
    get_store,
    make_entry,
    save,
    top,
)
from pitchsense.lessons import (
    LESSONS,
    LESSONS_BY_ID,
    PRACTICE_ROUNDS,
    better_option,
    concept_goal_rate,
    practice_pool,
)
from pitchsense.matches import (
    load_matches,
    load_name_map,
    match_subtitle,
    shot_headline,
)
from pitchsense.pitch import draw_pitch
from pitchsense.postshot import (
    ON_TARGET_OUTCOMES,
    POSTSHOT_FEATURES,
)
from pitchsense.postshot import (
    PRIMARY_MODEL_PATH as PSXG_MODEL_PATH,
)
from pitchsense.quiz import (
    CHANCE_BUCKETS,
    brier_points,
    bucket_balance,
    bucket_index,
    bucket_label,
    bucket_points,
    explain_shot,
    gap_points,
    out_of_100,
    outcome_text,
    reaction,
)
from pitchsense.ratings import (
    METRICS_PATH as RATINGS_METRICS_PATH,
)
from pitchsense.ratings import (
    RATINGS_CACHE,
    load_ratings,
)
from pitchsense.roles import (
    METRICS_PATH as ROLES_METRICS_PATH,
)
from pitchsense.roles import (
    MODEL_PATH as ROLES_MODEL_PATH,
)
from pitchsense.roles import (
    PLAYERS_CACHE,
    ROLE_MAP_PATH,
    assign_roles,
    load_roles,
)
from pitchsense.sandbox import (
    ASSIST_TYPES,
    KEEPER_POSITIONS,
    MARKER_GAPS,
    PRESETS,
    Scenario,
    scenario_features,
    xg_map,
)
from pitchsense.tactics import (
    METRICS_PATH as TACTICS_METRICS_PATH,
)
from pitchsense.tactics import (
    MODEL_PATH as TACTICS_MODEL_PATH,
)
from pitchsense.tactics import (
    load_classifier,
    overall_means,
    predict_pattern,
)
from pitchsense.train import PRIMARY_MODEL_PATH
from pitchsense.viz import plot_shot

ROOT = Path(__file__).resolve().parent
MODELS_DIR = ROOT / "models"
REPLAY_GIF = ROOT / "docs" / "example_sequence.gif"
# The browser game in game/, published to GitHub Pages by .github/workflows/game.yml.
GAME_URL = "https://shireenaqeel.github.io/pitchsense/"
BUCKET_EMOJI = {b[0]: b[1] for b in CHANCE_BUCKETS}
HEAT_CMAP = colormaps["YlOrRd"]


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


@st.cache_data(show_spinner=False)
def pool_xg(_model, _shots):
    """The model's xG for every shot in the quiz pool."""
    return _model.predict_proba(_shots[FEATURE_COLUMNS])[:, 1]


@st.cache_data(show_spinner=False)
def bucket_stats(_xgs, _goals):
    """Per chance band: (shots in it, share that were actually goals)."""
    bands = np.array([bucket_index(x) for x in _xgs])
    goals = np.asarray(_goals)
    return {label: (int((bands == i).sum()), float(goals[bands == i].mean()) if (bands == i).any() else 0.0)
            for i, (label, *_rest) in enumerate(CHANCE_BUCKETS)}


@st.cache_resource
def load_psxg_model():
    """The post-shot xG model, or None if it has not been trained yet."""
    return joblib.load(PSXG_MODEL_PATH) if PSXG_MODEL_PATH.exists() else None


@st.cache_resource
def load_story():
    """Match context and player display names (empty if the cache is missing)."""
    return load_matches(), load_name_map()


@st.cache_resource
def load_tactics_bundle():
    return load_classifier()


@st.cache_resource
def load_roles_bundle():
    return load_roles()


@st.cache_data(show_spinner=False)
def load_players_frame():
    return pd.read_parquet(PLAYERS_CACHE)


@st.cache_data(show_spinner=False)
def load_ratings_frame():
    return load_ratings().set_index("player")


def _pct_text(value) -> str:
    return "—" if pd.isna(value) else f"{value:.0f}"


def render_player_ratings(player: str):
    """Effectiveness and discipline percentiles for one player, against role peers."""
    if not RATINGS_CACHE.exists():
        st.caption("Effectiveness and discipline scores: run `python -m pitchsense.ratings`.")
        return
    ratings = load_ratings_frame()
    if player not in ratings.index:
        return
    r = ratings.loc[player]
    c1, c2, c3 = st.columns(3)
    c1.metric("Effectiveness", _pct_text(r["effectiveness"]),
              help="Percentile vs. players in the same role: pass completion, dribble "
                   "success, tackles won, and finishing (goals above xG per shot).")
    c2.metric("Discipline", _pct_text(r["discipline"]),
              help="Higher is cleaner: fewer fouls and cards per 100 actions than "
                   "role peers.")
    c3.metric("Fouls drawn / 100 actions", f"{r['fouls_won_per100']:.1f}",
              help="How often the player is fouled. Shown for context; not part of "
                   "either score.")
    if is_beginner():
        st.caption(f"Scores are out of 100, compared with other {r['role']}s: 50 is "
                   "typical, 90 means better than 9 in 10 of them.")
        return
    parts = [f"pass {r['pass_completion']:.0%} (p{_pct_text(r['pass_completion_pct'])})"]
    for stat, label in (("dribble_success", "dribble"), ("tackle_win", "tackles")):
        if not pd.isna(r[stat]):
            parts.append(f"{label} {r[stat]:.0%} (p{_pct_text(r[f'{stat}_pct'])})")
    if not pd.isna(r["finishing"]):
        parts.append(f"finishing {r['finishing']:+.3f} G−xG/shot over "
                     f"{int(r['n_np_shots'])} shots (p{_pct_text(r['finishing_pct'])})")
    parts.append(f"fouls {r['fouls_per100']:.2f}/100 · cards {int(r['card_points'])} pts")
    st.caption(" · ".join(parts) + f" — percentiles vs. {r['role']}s")


def model_psxg(psxg_model, shot) -> float:
    """Post-shot xG for a shot, from its pre-shot features plus where it finished."""
    values = [shot[f] for f in FEATURE_COLUMNS]
    values.append(placement_from_center(shot["shot_end_location"]))
    values.append(placement_height(shot["shot_end_location"]))
    row = pd.DataFrame([values], columns=POSTSHOT_FEATURES)
    return float(psxg_model.predict_proba(row)[:, 1][0])


@dataclass
class Ctx:
    """Everything a quiz round needs, loaded once per run."""
    shots: pd.DataFrame
    tags: list
    xgs: np.ndarray
    balance: np.ndarray
    model: object
    matches: dict
    names: dict


def load_ctx() -> Ctx:
    shots = load_quiz_shots()
    model = load_model()
    xgs = pool_xg(model, shots)
    matches, names = load_story()
    return Ctx(shots, concepts_per_shot(shots), xgs, bucket_balance(xgs), model, matches, names)


def is_beginner() -> bool:
    return st.session_state.get("mode", "Beginner") == "Beginner"


def show_plot(fig):
    st.pyplot(fig)
    plt.close(fig)


# --------------------------------------------------------------------------- #
# A quiz "game": one sequence of shots with its own score, reusable by the free
# quiz and by each lesson's practice set. Concept progress is shared, so every
# answer anywhere feeds the adaptive selection.
# --------------------------------------------------------------------------- #
def game(key: str) -> dict:
    return st.session_state.games[key]


def next_shot(key: str, pool: list, ctx: Ctx):
    """Pick the game's next shot from ``pool``, adaptive to weak concepts."""
    g = game(key)
    weights = concept_weights(st.session_state.concept_progress)
    boost = ctx.balance[pool] if is_beginner() else None
    seen = set(g["seen"])
    exclude = [i for i, idx in enumerate(pool) if idx in seen]
    pos = pick_adaptive([ctx.tags[i] for i in pool], weights, st.session_state.rng,
                        boost=boost, exclude=exclude)
    g["idx"] = pool[pos]
    g["seen"].append(g["idx"])
    g["revealed"] = False


def ensure_game(key: str, pool: list, ctx: Ctx):
    if key not in st.session_state.games:
        st.session_state.games[key] = {"rounds": 0, "points": 0, "model_points": 0,
                                       "seen": [], "saved": False}
        next_shot(key, pool, ctx)


def submit(key: str, ctx: Ctx, guess: float, label: str | None):
    """Score a guess. ``label`` is the named band in Beginner mode, else None."""
    g = game(key)
    idx = g["idx"]
    mxg = float(ctx.xgs[idx])
    actual = int(ctx.shots.iloc[idx]["is_goal"])
    if label is not None:
        earned = bucket_points(label, mxg)
    else:
        earned = brier_points(guess, actual)
        g["model_points"] += brier_points(mxg, actual)
    g.update(revealed=True, guess=guess, label=label, earned=earned)
    g["points"] += earned
    g["rounds"] += 1
    update_progress(st.session_state.concept_progress, ctx.tags[idx], earned)
    st.session_state.shots_read += 1


def render_story(shot, ctx: Ctx, revealed: bool):
    match = ctx.matches.get(int(shot["match_id"]))
    st.markdown(f"#### {shot_headline(shot, match, ctx.names.get(shot['player']))}")
    subtitle = match_subtitle(match, include_score=revealed)
    if subtitle:
        st.caption(subtitle)


def render_pitch(shot, revealed: bool):
    fig, ax = plt.subplots(figsize=(7, 6.5))
    plot_shot(shot, ax=ax, reveal=revealed, half=True, cone=revealed, title="")
    ax.legend(loc="lower left", framealpha=0.9, fontsize=8, markerscale=0.6)
    show_plot(fig)


def render_guess_input(key: str, ctx: Ctx):
    if is_beginner():
        st.markdown("**How good is this chance?** Look at the distance, the angle, "
                    "and who's in the way.")
        for label, emoji, _, prob, gloss in CHANCE_BUCKETS:
            st.button(f"{emoji} {label} — {gloss}", key=f"{key}:{label}",
                      width="stretch", on_click=submit, args=(key, ctx, prob, label))
    else:
        # Read from the slider's return value rather than in an on_click callback:
        # a callback runs before the script, when an interrupted earlier run may
        # have dropped the slider's state.
        estimate = st.slider("Your estimate: chance this shot scores (%)", 0, 100, 15,
                             key=f"{key}:slider")
        if st.button("Lock it in", type="primary", key=f"{key}:lock"):
            submit(key, ctx, estimate / 100, None)
            st.rerun()


def render_reveal(key: str, ctx: Ctx, shot):
    g = game(key)
    mxg = float(ctx.xgs[g["idx"]])
    actual = int(shot["is_goal"])
    model_band = bucket_label(mxg)

    (st.success if actual else st.error)(
        f"{'⚽' if actual else '❌'} **{outcome_text(shot['shot_outcome'])}**"
    )

    if g["label"] is not None:
        st.markdown(f"#### {reaction(g['earned'])}  +{g['earned']} pts")
        st.markdown(
            f"You called it **{BUCKET_EMOJI[g['label']]} {g['label']}**. The model says "
            f"**{BUCKET_EMOJI[model_band]} {model_band}**: about **{out_of_100(mxg)} in 100** "
            "shots like this go in."
        )
    else:
        st.markdown(f"#### {reaction(gap_points(g['guess'], mxg))}")
        c1, c2, c3 = st.columns(3)
        c1.metric("Your estimate", f"{g['guess']:.0%}")
        c2.metric("Model xG", f"{mxg:.0%}", help=f"{model_band}")
        c3.metric("Points this round", g["earned"],
                  help="Brier score against the actual outcome, 0-100.")

    why = reasons(ctx.model, shot)
    if why["helped"] or why["hurt"]:
        st.markdown("**Why the model rated it that way**")
        for heading, items in (("Made it easier", why["helped"]), ("Made it harder", why["hurt"])):
            if items:
                st.caption(heading)
                st.markdown("\n".join(f"- {emoji} {text}" for emoji, _, text in items))
    else:
        st.info(explain_shot(shot, mxg, g["guess"]))

    n, rate = bucket_stats(ctx.xgs, ctx.shots["is_goal"])[model_band]
    st.caption(f"📊 Reality check: of the {n:,} shots in our data the model calls a "
               f"*{model_band}*, {rate:.0%} actually went in.")
    render_finish_quality(shot, mxg)
    st.caption("Concepts in this shot: " + ", ".join(ctx.tags[g["idx"]]))


def render_finish_quality(shot, mxg: float):
    """Show post-shot xG (the finish) beside pre-shot xG (the chance).

    Post-shot xG is only defined for shots on target, and only if the model has
    been trained; otherwise this shows nothing.
    """
    psxg_model = load_psxg_model()
    if psxg_model is None or shot["shot_outcome"] not in ON_TARGET_OUTCOMES:
        return
    psxg = model_psxg(psxg_model, shot)
    if is_beginner():
        verb = "turned" if psxg > mxg else "left"
        st.caption(f"🎯 **The finish:** where the ball was placed {verb} a "
                   f"{out_of_100(mxg)}-in-100 chance into a {out_of_100(psxg)}-in-100 shot.")
        return
    p1, p2 = st.columns(2)
    p1.metric("Pre-shot xG — the chance", f"{mxg:.0%}")
    p2.metric("Post-shot xG — the finish", f"{psxg:.0%}")
    verdict = ("Struck better than an average shot from there: the placement made it "
               "more likely to score than the chance alone." if psxg > mxg else
               "The finish did not add to the chance: an average shot from there would "
               "have been at least as dangerous.")
    st.caption("Pre-shot xG rates the chance before the ball was struck; post-shot xG "
               "rates how likely it was to score given where it finished. " + verdict)


def render_round(key: str, pool: list, ctx: Ctx, limit: int | None = None) -> bool:
    """Render the game's current shot. Returns True once ``limit`` rounds are done."""
    ensure_game(key, pool, ctx)
    g = game(key)
    shot = ctx.shots.iloc[g["idx"]]
    revealed = g["revealed"]

    render_story(shot, ctx, revealed)
    pitch, panel = st.columns([5, 4], gap="medium")
    with pitch:
        render_pitch(shot, revealed)
    with panel:
        if not revealed:
            render_guess_input(key, ctx)
            return False
        render_reveal(key, ctx, shot)
        finished = limit is not None and g["rounds"] >= limit
        if not finished:
            st.button("Next shot ➡️", type="primary", key=f"{key}:next",
                      on_click=next_shot, args=(key, pool, ctx))
    return finished


# --------------------------------------------------------------------------- #
# 🎓 Learn
# --------------------------------------------------------------------------- #
def scenario_xg(model, scenario: Scenario) -> float:
    return float(model.predict_proba(scenario_features(scenario)[FEATURE_COLUMNS])[:, 1][0])


def scenario_figure(scenario: Scenario, title: str, cone: bool = True):
    shot = scenario_features(scenario).iloc[0]
    fig, ax = plt.subplots(figsize=(6, 6))
    plot_shot(shot, ax=ax, reveal=False, half=True, cone=cone, title=title)
    ax.set_xlim(78, 123)
    ax.get_legend().remove()
    return fig


def answer_compare(lesson_id: str, choice: str):
    st.session_state.compare_answers[lesson_id] = choice


def open_lesson(lesson_id: str):
    st.session_state.lesson_id = lesson_id


def render_learn(ctx: Ctx):
    done = st.session_state.lessons_done
    menu, body = st.columns([1, 3], gap="large")

    with menu:
        st.markdown("**Lessons**")
        st.caption(f"{len(done)} of {len(LESSONS)} complete")
        for i, lesson in enumerate(LESSONS, start=1):
            tick = "✅" if lesson.id in done else lesson.emoji
            current = lesson.id == st.session_state.lesson_id
            st.button(f"{tick} {i}. {lesson.title}", key=f"lesson-btn:{lesson.id}",
                      type="primary" if current else "secondary", width="stretch",
                      on_click=open_lesson, args=(lesson.id,))

    lesson = LESSONS_BY_ID[st.session_state.lesson_id]
    with body:
        st.subheader(f"{lesson.emoji} {lesson.title}")
        st.caption(lesson.hook)
        st.markdown(lesson.body)
        if lesson.expert_note and not is_beginner():
            st.caption("🔧 " + lesson.expert_note)

        overall = ctx.shots["is_goal"].mean()
        facts = [f"{c}: {n:,} shots, **{r:.0%}** scored"
                 for c in lesson.concepts
                 for n, r in [concept_goal_rate(ctx.shots, ctx.tags, c)] if n]
        if facts:
            st.caption(f"📊 In the data, {overall:.0%} of all {len(ctx.shots):,} shots "
                       "scored. " + " · ".join(facts))

        # Step 2: spot the better chance.
        st.divider()
        st.markdown("##### 1️⃣ Spot the better chance")
        (label_a, scen_a), (label_b, scen_b) = lesson.compare
        xg_a, xg_b = scenario_xg(ctx.model, scen_a), scenario_xg(ctx.model, scen_b)
        answer = st.session_state.compare_answers.get(lesson.id)
        col_a, col_b = st.columns(2)
        for col, label, scen, xg, letter in ((col_a, label_a, scen_a, xg_a, "A"),
                                             (col_b, label_b, scen_b, xg_b, "B")):
            with col:
                show_plot(scenario_figure(scen, label))
                if answer:
                    st.metric(f"Model xG ({letter})", f"{xg:.2f}",
                              help=f"About {out_of_100(xg)} in 100 shots like this go in.")
                else:
                    st.button(f"{letter} is the better chance", key=f"cmp:{lesson.id}:{letter}",
                              width="stretch", on_click=answer_compare, args=(lesson.id, letter))
        if not answer:
            return
        if answer == better_option(xg_a, xg_b):
            st.success(f"✅ Right! {lesson.takeaway}")
        else:
            st.warning(f"Not quite. The model rates {better_option(xg_a, xg_b)} higher. "
                       f"{lesson.takeaway}")
        st.caption("Want to play with it? Build these in the 🧪 **Be the striker** tab.")

        # Step 3: practise on real shots.
        st.divider()
        key = f"lesson:{lesson.id}"
        rounds = st.session_state.games.get(key, {}).get("rounds", 0)
        st.markdown(f"##### 2️⃣ Practise on real shots · {min(rounds, PRACTICE_ROUNDS)}"
                    f" of {PRACTICE_ROUNDS}")
        pool = practice_pool(ctx.tags, lesson)
        if render_round(key, pool, ctx, limit=PRACTICE_ROUNDS):
            finish_lesson(lesson, key)


def finish_lesson(lesson, key: str):
    g = game(key)
    avg = g["points"] / max(g["rounds"], 1)
    first_time = lesson.id not in st.session_state.lessons_done
    st.session_state.lessons_done[lesson.id] = avg
    if first_time:
        st.balloons()
    st.success(f"🎓 Lesson complete! You averaged **{avg:.0f}/100** on the practice shots.\n\n"
               f"**Remember:** {lesson.takeaway}")
    ids = [l.id for l in LESSONS]
    nxt = ids[ids.index(lesson.id) + 1] if lesson.id != ids[-1] else None
    c1, c2 = st.columns(2)
    if nxt:
        c1.button(f"Next lesson: {LESSONS_BY_ID[nxt].title} ➡️", type="primary",
                  on_click=open_lesson, args=(nxt,))
    else:
        c1.markdown("🏁 That's every lesson. Put it all together in the 🎯 **Shot quiz**.")
    c2.button("Practise this again 🔁", on_click=st.session_state.games.pop, args=(key, None))


# --------------------------------------------------------------------------- #
# 🎯 Shot quiz (free play)
# --------------------------------------------------------------------------- #
@st.cache_resource
def leaderboard_store():
    """Supabase on the deployed app, a local JSON file otherwise.

    The settings come from the environment, or from Streamlit's secrets, which
    is where Streamlit Community Cloud keeps them.
    """
    env = dict(os.environ)
    try:
        env.update({k: str(st.secrets[k]) for k in ("SUPABASE_URL", "SUPABASE_KEY") if k in st.secrets})
    except FileNotFoundError:  # no secrets file: a local run
        pass
    store = get_store(env)
    log.info("Leaderboard store: %s", store.name)
    return store


def render_leaderboard(g: dict):
    """Show the top scores and, once qualified, a form to save this session."""
    st.subheader("🏆 Leaderboard")
    store = leaderboard_store()
    scores = board(store)
    leaders = top(scores or [], n=10)
    if scores is None:
        st.caption("The leaderboard can't be reached right now. Your game still counts, so try saving in a bit.")
    elif leaders:
        st.dataframe(
            [
                {"#": i + 1, "Player": s["name"], "Avg": f"{s['avg_points']:.0f}",
                 "vs model": f"{s['vs_model']:+.0f}", "Rounds": s["rounds"]}
                for i, s in enumerate(leaders)
            ],
            hide_index=True, width="stretch",
        )
    else:
        st.caption(f"No qualifying scores yet. Play {MIN_ROUNDS}+ rounds and save to start it.")

    if g.get("saved"):
        st.caption("Your score is saved ✅")
    elif g["rounds"] >= MIN_ROUNDS:
        with st.form("save_score"):
            name = st.text_input("Name for the leaderboard", max_chars=20)
            if st.form_submit_button("Save my score"):
                try:
                    save(store, make_entry(name, g["points"], g["model_points"], g["rounds"]))
                except LeaderboardError as err:
                    st.warning(str(err))
                else:
                    g["saved"] = True
                    st.rerun()
    else:
        st.caption(f"Play {MIN_ROUNDS - g['rounds']} more round(s) to save a score.")


def render_quiz(ctx: Ctx):
    # Beginner and Expert answers are scored differently, so each keeps its own game.
    key = "quiz:beginner" if is_beginner() else "quiz:expert"
    pool = list(range(len(ctx.shots)))
    ensure_game(key, pool, ctx)
    g = game(key)

    board, play = st.columns([1, 3], gap="large")
    with play:
        render_round(key, pool, ctx)

    with board:
        st.subheader("Scoreboard")
        if g["rounds"]:
            st.metric("Your average", f"{g['points'] / g['rounds']:.0f} / 100")
            if not is_beginner():
                st.metric("Model average", f"{g['model_points'] / g['rounds']:.0f} / 100",
                          help="The model's own Brier points on the same shots.")
            st.caption(f"Shots played: {g['rounds']}")
        else:
            st.write("Make your first call to get on the board.")
        st.caption("Beginner: 100 for naming the same chance as the model, 50 for one "
                   "band off." if is_beginner() else
                   "Expert: Brier points against what actually happened.")

        scores = concept_scores(st.session_state.concept_progress)
        if scores:
            st.subheader("Where you stand")
            st.caption("Your average per concept. The quiz serves weaker ones more often.")
            for concept, score in sorted(scores.items(), key=lambda kv: kv[1]):
                st.progress(int(round(score)), text=f"{concept}: {score:.0f}/100")

        if not is_beginner():
            render_leaderboard(g)


# --------------------------------------------------------------------------- #
# 🧪 Be the striker (sandbox)
# --------------------------------------------------------------------------- #
SANDBOX_DEFAULTS = {"sb_dist": 15, "sb_offset": 0, "sb_blockers": 1, "sb_marker": "Close",
                    "sb_keeper": "On the line", "sb_header": False, "sb_first_time": False,
                    "sb_one_on_one": False, "sb_pressure": False, "sb_assist": "None"}


def apply_preset(name: str):
    if name not in PRESETS:
        return
    s = PRESETS[name]
    st.session_state.update(
        sb_dist=int(round(120 - s.x)), sb_offset=int(round(s.y - 40)), sb_blockers=s.blockers,
        sb_marker=s.marker, sb_keeper=s.keeper, sb_header=s.header,
        sb_first_time=s.first_time, sb_one_on_one=s.one_on_one,
        sb_pressure=s.under_pressure, sb_assist=s.assist,
    )


@st.cache_data(show_spinner="Painting the xG map…")
def cached_xg_map(_model, scenario: Scenario):
    return xg_map(_model, scenario, FEATURE_COLUMNS)


def render_sandbox(ctx: Ctx):
    st.caption("Build a chance and watch the real model rate it. Change **one thing at a "
               "time** to see what really matters.")
    for k, v in SANDBOX_DEFAULTS.items():
        st.session_state.setdefault(k, v)

    controls, view = st.columns([1, 2], gap="large")
    with controls:
        # Applied in the script body, not an on_change callback: callbacks run before
        # the script, when an interrupted earlier run may have dropped the widget's
        # state. Here the selected value is always available, and the sliders below
        # have not been created yet, so their state can still be set.
        preset = st.selectbox("Start from a classic situation", ["Custom"] + list(PRESETS),
                              key="sb_preset")
        if preset != st.session_state.get("sb_applied_preset"):
            st.session_state.sb_applied_preset = preset
            apply_preset(preset)
        st.slider("Yards from the goal line", 1, 36, key="sb_dist")
        st.slider("Left ← centre → right (yards)", -26, 26, key="sb_offset")
        st.slider("Defenders in the way", 0, 5, key="sb_blockers")
        st.select_slider("Nearest defender", list(MARKER_GAPS), key="sb_marker")
        st.radio("Goalkeeper", KEEPER_POSITIONS, key="sb_keeper", horizontal=True)
        st.radio("The pass before", ASSIST_TYPES, key="sb_assist", horizontal=True)
        a, b = st.columns(2)
        a.toggle("Header", key="sb_header")
        b.toggle("First time", key="sb_first_time")
        a.toggle("One-on-one", key="sb_one_on_one")
        b.toggle("Under pressure", key="sb_pressure")

    ss = st.session_state
    scenario = Scenario(
        x=120.0 - ss.sb_dist, y=40.0 + ss.sb_offset, blockers=ss.sb_blockers,
        marker=ss.sb_marker, keeper=ss.sb_keeper, header=ss.sb_header,
        first_time=ss.sb_first_time, one_on_one=ss.sb_one_on_one,
        under_pressure=ss.sb_pressure, assist=ss.sb_assist,
    )
    shot = scenario_features(scenario).iloc[0]
    xg = scenario_xg(ctx.model, scenario)
    band = bucket_label(xg)

    with view:
        m1, m2 = st.columns([1, 2])
        m1.metric("Model xG", f"{xg:.2f}")
        m2.markdown(f"### {BUCKET_EMOJI[band]} {band}\nAbout **{out_of_100(xg)} in 100** "
                    "shots like this go in.")
        hits = out_of_100(xg)
        st.markdown("<div style='font-size:15px;line-height:1.15;letter-spacing:1px'>"
                    + "<br>".join("".join("⚽" if r * 10 + c < hits else "⚪" for c in range(10))
                                  for r in range(10)) + "</div>",
                    unsafe_allow_html=True)

        show_map = st.toggle("🗺️ Show the xG map: how the chance changes as you move",
                             key="sb_map")
        fig, ax = plt.subplots(figsize=(8, 7))
        if show_map:
            xs, ys, grid = cached_xg_map(ctx.model, scenario)
            draw_pitch(ax)
            half = (xs[1] - xs[0]) / 2
            # Fade low-xG ground to transparent so the grass shows through and
            # only the dangerous zones glow.
            norm = Normalize(vmin=0, vmax=max(0.5, float(grid.max())))
            rgba = HEAT_CMAP(norm(grid))
            rgba[..., 3] = np.clip(grid / 0.25, 0.0, 0.9)
            ax.imshow(rgba, origin="lower", zorder=0.5, interpolation="bilinear",
                      extent=(xs[0] - half, xs[-1] + half, ys[0] - half, ys[-1] + half))
            ax.scatter([shot["x"]], [shot["y"]], c="white", s=200, edgecolors="black",
                       zorder=7)
            ax.set_xlim(78, 123)
            ax.set_ylim(ys[0] - half, ys[-1] + half)
            fig.colorbar(ScalarMappable(norm=norm, cmap=HEAT_CMAP), ax=ax, fraction=0.03,
                         label="xG from that spot")
            ax.set_title("Hotter = better place to shoot from (defenders move with you)",
                         fontsize=12)
        else:
            plot_shot(shot, ax=ax, reveal=False, half=True, cone=True,
                      title="The yellow cone is what you can aim at; anyone in it can block")
        show_plot(fig)

        why = reasons(ctx.model, shot)
        good, bad = st.columns(2)
        with good:
            st.caption("Making it easier")
            for emoji, _, text in why["helped"] or [("➖", "", "Nothing stands out.")]:
                st.markdown(f"{emoji} {text}")
        with bad:
            st.caption("Making it harder")
            for emoji, _, text in why["hurt"] or [("➖", "", "Nothing stands out.")]:
                st.markdown(f"{emoji} {text}")


# --------------------------------------------------------------------------- #
# 🧭 How teams attack (tactical patterns)
# --------------------------------------------------------------------------- #
PATTERN_STORY = {
    "Counter-attack / direct": ("⚡", "Win it, then go straight for goal before the "
                                "defence can get back. Few passes, lots of yards, fast."),
    "Patient build-up": ("🧩", "Keep the ball, pass it around, and wait for a gap to "
                         "open. Slow, but it creates the most shots."),
    "Quick regain / transition": ("🔄", "Win the ball high up the pitch and use it "
                                  "quickly, with goal already close."),
}


def render_tactics():
    st.subheader("How teams attack")
    st.caption("Every possession in the data was grouped by *how* the ball was moved. "
               "Nobody labelled them: the model found these three styles on its own.")
    if not (TACTICS_MODEL_PATH.exists() and TACTICS_METRICS_PATH.exists()):
        st.info("Train the classifier first, then reload:  `python -m pitchsense.tactics`")
        return

    metrics = json.loads(TACTICS_METRICS_PATH.read_text(encoding="utf-8"))
    cols = st.columns(len(metrics["clusters"]))
    for col, c in zip(cols, metrics["clusters"]):
        emoji, story = PATTERN_STORY.get(c["label"], ("⚽", ""))
        m = c["means"]
        with col:
            st.markdown(f"#### {emoji} {c['label']}")
            st.write(story)
            st.caption(f"Typically {m['n_passes']:.0f} passes in {m['duration']:.0f}s, "
                       f"{m['net_forward']:.0f} yards upfield · "
                       f"{m['ends_in_shot'] * 100:.0f}% end in a shot")

    if REPLAY_GIF.exists():
        left, _ = st.columns([2, 1])
        left.image(str(REPLAY_GIF),
                   caption="A real goal build-up, replayed. The model reads it as a counter-attack.")

    st.markdown("**Design a move: what would the model call it?**")
    st.caption("Change a few numbers; everything else stays at the dataset average.")
    means = overall_means()
    bundle = load_tactics_bundle()
    c1, c2 = st.columns(2)
    passes = c1.slider("Passes", 1, 30, int(round(means["n_passes"])))
    duration = c2.slider("Duration (seconds)", 1, 90, int(round(means["duration"])))
    net_forward = c1.slider("Yards gained upfield", -40, 110, int(round(means["net_forward"])))
    speed = c2.slider("Upfield speed (yards/sec)", 0.0, 12.0,
                      float(round(means["forward_speed"], 1)), step=0.5)
    feats = {**means, "n_passes": passes, "duration": duration,
             "net_forward": net_forward, "forward_speed": speed}
    pattern = predict_pattern(bundle, feats)
    st.success(f"The model reads this as: **{PATTERN_STORY.get(pattern, ('⚽',))[0]} {pattern}**")

    with st.expander("🔧 Under the hood", expanded=not is_beginner()):
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
            f"Unsupervised k-means over possession shape-and-tempo features · "
            f"{metrics['n_possessions']:,} possessions · k={metrics['n_clusters']} · "
            f"silhouette {metrics['silhouette']:.2f}. The labels interpret the clusters; "
            "they were not taught."
        )


# --------------------------------------------------------------------------- #
# 🧑‍🤝‍🧑 Player roles
# --------------------------------------------------------------------------- #
def render_roles():
    st.subheader("Do players really play their position?")
    st.caption(
        "The model ignored the position on the team sheet and grouped players by *how "
        "they actually play*: where they spend time, how much they roam, and how often "
        "they pass, dribble, shoot or defend."
    )
    if not (ROLES_MODEL_PATH.exists() and ROLES_METRICS_PATH.exists()):
        st.info("Train the clusterer first, then reload:  `python -m pitchsense.roles`")
        return

    metrics = json.loads(ROLES_METRICS_PATH.read_text(encoding="utf-8"))
    if PLAYERS_CACHE.exists():
        data = load_players_frame()
        bundle = load_roles_bundle()
        roles = assign_roles(bundle, data)
        names = load_story()[1]
        display = {full: names.get(full, full) for full in data["player"]}
        options = sorted(data["player"].tolist(), key=lambda n: display[n])
        default = next((i for i, n in enumerate(options) if display[n] == "Lionel Messi"), 0)
        pick = st.selectbox("Look up a player", options, index=default,
                            format_func=lambda n: display[n])
        idx = data.index[data["player"] == pick][0]
        row = data.loc[idx]
        detected, listed = roles.loc[idx], row["position"]
        c1, c2 = st.columns(2)
        c1.metric("Plays like a…", detected)
        c2.metric("Team sheet says", listed)
        render_player_ratings(pick)
        if is_beginner():
            st.caption(f"Average position {row['avg_x']:.0f} yards up the pitch · "
                       f"{row['pass_share']:.0%} of their actions are passes")
        else:
            st.caption(
                f"avg x {row['avg_x']:.0f} · width {row['lateral']:.0f} · "
                f"pass share {row['pass_share']:.2f} · dribble {row['dribble_share']:.3f} · "
                f"shots {row['shot_share']:.3f} · defensive {row['defensive_share']:.2f}"
            )
        st.caption("💡 Try a deep midfielder like Sergio Busquets or Toni Kroos: they land "
                   "with the centre-backs, because that's how they play.")
    else:
        st.caption("Player lookup needs the cached player data. Run "
                   "`python -m pitchsense.roles` once to build it.")

    with st.expander("🔧 Under the hood", expanded=not is_beginner()):
        if ROLE_MAP_PATH.exists():
            st.image(str(ROLE_MAP_PATH),
                     caption="Players projected to two PCA dimensions, coloured by role cluster.")
        st.dataframe(
            [
                {"Role": c["label"], "Players": c["size"],
                 "Purity": f"{c['purity'] * 100:.0f}%",
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
            f"k-means over standardised behavioural features · {metrics['n_players']} "
            f"players · k={metrics['n_clusters']} · silhouette {metrics['silhouette']:.2f} · "
            "purity = share of the cluster actually listed at the label position"
        )
        if RATINGS_METRICS_PATH.exists():
            rm = json.loads(RATINGS_METRICS_PATH.read_text(encoding="utf-8"))
            st.markdown("**Effectiveness & discipline** — role medians")
            st.dataframe(
                [
                    {"Role": r["role"], "Players": r["players"],
                     "Pass %": f"{r['medians']['pass_completion']:.0%}",
                     "Dribble %": "—" if r["medians"]["dribble_success"] is None
                     else f"{r['medians']['dribble_success']:.0%}",
                     "Tackle %": "—" if r["medians"]["tackle_win"] is None
                     else f"{r['medians']['tackle_win']:.0%}",
                     "Fouls /100": round(r["medians"]["fouls_per100"], 2),
                     "Drawn /100": round(r["medians"]["fouls_won_per100"], 2)}
                    for r in rm["roles"]
                ],
                hide_index=True, width="stretch",
            )
            st.caption(
                "Scores are within-role percentiles, not a trained model. Stats with too "
                f"few attempts are skipped ({rm['min_attempts']}). Effectiveness vs. "
                f"discipline Spearman ρ = {rm['effectiveness_vs_discipline_spearman']:.2f}."
            )


# --------------------------------------------------------------------------- #
# 🔧 Under the hood
# --------------------------------------------------------------------------- #
def metrics_rows(metrics: dict) -> list:
    rows = []
    for name, m in metrics["models"].items():
        rows.append({
            "Model": name.replace("_", " ").title()
            + (" (served)" if name == metrics["primary_model"] else ""),
            "CV log loss": f"{m['cv']['log_loss']['mean']:.3f} ± {m['cv']['log_loss']['std']:.3f}",
            "CV ROC AUC": f"{m['cv']['roc_auc']['mean']:.3f} ± {m['cv']['roc_auc']['std']:.3f}",
            "Test log loss": f"{m['test']['log_loss']:.3f}",
            "Test ROC AUC": f"{m['test']['roc_auc']:.3f}",
        })
    return rows


def render_hood():
    st.subheader("How PitchSense works")
    st.markdown(
        "Every number in this app comes from **models trained on real match data**, not "
        "an LLM guessing:\n\n"
        "1. **Data:** StatsBomb open event data from six men's international tournaments "
        "(the 2018 & 2022 World Cups, Euro 2020 & 2024, Copa América 2024 and AFCON 2023, "
        "314 matches), including *freeze-frames*, the position of every player at the "
        "moment of each shot. The xG models also learn from four full 2015/16 club "
        "seasons (Premier League, La Liga, Serie A, Ligue 1), but every score below is "
        "measured on international shots only.\n"
        "2. **Features:** 17 per shot, from distance and angle to how many defenders are "
        "in the shooting cone and where the keeper is.\n"
        "3. **Models:** logistic regression vs XGBoost, each tuned by 5-fold "
        "cross-validated search on log loss (xG must be *calibrated*), with the better "
        "one served. A separate post-shot model adds where the ball finished.\n"
        "4. **Explanations:** the served model's reasoning for any shot splits exactly "
        "into per-factor contributions (TreeSHAP values for XGBoost, coefficients for a "
        "linear model). That's the *why* you see after each reveal.\n"
        "5. **Adaptive practice:** each shot is tagged with concepts; the quiz serves more "
        "of the ones you read worst."
    )
    for label, file in (("Pre-shot xG", "xg_metrics.json"), ("Post-shot xG", "psxg_metrics.json")):
        path = MODELS_DIR / file
        if path.exists():
            m = json.loads(path.read_text(encoding="utf-8"))
            club = m.get("n_club_shots", 0)
            extra = f" (+{club:,} club shots used for training only)" if club else ""
            st.markdown(f"**{label}**: {m['n_shots']:,} international shots, "
                        f"{m['goal_rate']:.1%} goal rate{extra}")
            st.dataframe(metrics_rows(m), hide_index=True, width="stretch")
    st.caption("Full write-up, generalisation tests (leave-one-tournament-out) and code: "
               "[github.com/shireenaqeel/pitchsense](https://github.com/shireenaqeel/pitchsense)")


# --------------------------------------------------------------------------- #
# Layout
# --------------------------------------------------------------------------- #
def init_session():
    ss = st.session_state
    ss.setdefault("games", {})
    ss.setdefault("concept_progress", {})
    ss.setdefault("rng", np.random.default_rng())
    ss.setdefault("lessons_done", {})
    ss.setdefault("compare_answers", {})
    ss.setdefault("lesson_id", LESSONS[0].id)
    ss.setdefault("shots_read", 0)


def render_sidebar():
    with st.sidebar:
        st.markdown("## ⚽ PitchSense")
        st.radio("Mode", ["Beginner", "Expert"], key="mode",
                 captions=["Name the chance, plain language",
                           "Exact %, Brier scoring, model details"])
        st.divider()
        ss = st.session_state
        st.metric("Lessons complete", f"{len(ss.lessons_done)} / {len(LESSONS)}")
        st.metric("Shots read", ss.shots_read)
        if not ss.lessons_done:
            st.caption("New here? Start with **🎓 Learn**.")
        st.divider()
        st.link_button("🎮 Play PitchSense: the game", GAME_URL, width="stretch")
        st.caption("Career mode, boss fights, a daily challenge — the same shots and model.")


st.set_page_config(page_title="PitchSense", page_icon="⚽", layout="wide")
init_session()
render_sidebar()
st.title("⚽ PitchSense")
st.caption("Learn to read a chance like a scout, using real World Cup, Euro, Copa América "
           "and AFCON shots "
           "and a model trained on them.")

ctx = load_ctx()
tabs = st.tabs(["🎓 Learn", "🎯 Shot quiz", "🧪 Be the striker", "🧭 How teams attack",
                "🧑‍🤝‍🧑 Player roles", "🔧 Under the hood"])
with tabs[0]:
    render_learn(ctx)
with tabs[1]:
    render_quiz(ctx)
with tabs[2]:
    render_sandbox(ctx)
with tabs[3]:
    render_tactics()
with tabs[4]:
    render_roles()
with tabs[5]:
    render_hood()
