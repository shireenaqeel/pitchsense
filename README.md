# PitchSense

An interactive tool that teaches football tactics and concepts (xG, pressing, offside, formations) by replaying real match data as animations, asking you to predict outcomes, and comparing your guess against a trained machine-learning model — with difficulty that adapts to your weak areas.

Unlike a typical xG dashboard, the whole point here is a real pipeline: **real match data → trained ML models → animated replay → interactive quiz → adaptive personalization.** The predictions come from models trained on data, not from an LLM pretending to be a football expert.

## Problem

"How likely was that shot to score?" is something even experienced fans disagree on. Expected Goals (xG) answers it with data: given where a shot was taken and what was happening around it, what share of similar shots historically became goals? PitchSense trains that model and then uses it as a yardstick to help a learner build intuition.

## Data

- **Source:** [StatsBomb Open Data](https://github.com/statsbomb/open-data) — free, public, real professional match events.
- **Competition used:** FIFA World Cup 2018 (`competition_id=43`, `season_id=3`), 64 matches.
- Data is pulled on demand via `statsbombpy` and cached locally under `data/` (git-ignored, not committed).

## Approach (Phase 1 — baseline xG model)

For every shot we engineer features from the event and its freeze-frame (the snapshot of player positions at the moment of the shot):

| Feature | Meaning |
|---|---|
| `distance` | Distance from the shot to the centre of the goal |
| `angle` | Angle of the goal mouth visible from the shot location (wider = easier) |
| `defenders_in_cone` | Opponents inside the triangle between the shot and the two goal posts |
| `is_header` | Headed shot |
| `is_first_time` | Struck first time, without a touch to control |
| `is_one_on_one` | One-on-one against the keeper |
| `under_pressure` | A defender was closing the shooter down |
| `from_open_play` | Regular open play vs. a set-piece pattern |
| `assist_cross` | The assisting pass was a cross |
| `assist_cutback` | The assisting pass was a cutback |
| `assist_through_ball` | The assisting pass was a through ball |

The assist features are joined from the assisting pass event via each shot's
`shot_key_pass_id`.

**Target:** whether the shot was a goal. Penalties are excluded — they score far more often than open play and would distort the model.

**Models:** two are trained and compared — Logistic Regression (standardized
features) and XGBoost. The pipeline picks whichever has the lower held-out log
loss as the model it serves; it is not hardcoded.

## Results (held-out test set)

Trained on World Cup 2018 (1,638 open-play shots, 8.2% goal rate, 11 features):

| Model | ROC AUC | Log loss | Brier |
|---|---|---|---|
| **Logistic Regression** (served) | **0.758** | **0.242** | **0.066** |
| XGBoost | 0.708 | 0.267 | 0.073 |

On this single-competition dataset the linear model wins on every metric. That
is the expected outcome, not a bug: with only ~135 goals, a gradient-boosted
tree overfits, whereas the core xG signal (distance and angle) is smooth and
close to linear in log-odds — exactly what logistic regression models well. The
tree should overtake it once the training set is expanded across competitions.

The served model is well calibrated: for its highest-probability bucket of shots
it predicts ~0.36 and the actual goal rate is ~0.39. For reference, StatsBomb's
own production xG reaches ~0.78–0.80 AUC using more features (including richer
freeze-frame geometry), so this baseline sits in a sensible range.

Both models are saved (`models/xg_logreg.joblib`, `models/xg_xgboost.joblib`),
the served model is copied to `models/xg_baseline.joblib`, and the full
comparison is written to `models/xg_metrics.json` on every training run.

## Project layout

```
src/pitchsense/
  data.py       # load & cache StatsBomb shots
  features.py   # pitch geometry + feature engineering (pure, tested)
  train.py      # train, evaluate, and save the baseline model
tests/          # unit tests for the geometry and feature frame
data/           # cached raw data (git-ignored)
models/         # trained model + metrics (git-ignored)
```

## Setup

Requires Python 3.11+.

```bash
python -m venv .venv
.venv/Scripts/activate        # Windows
# source .venv/bin/activate   # macOS / Linux
pip install -r requirements.txt
```

## Run

```bash
# Train and evaluate the baseline xG model (downloads & caches data on first run)
PYTHONPATH=src python -m pitchsense.train

# Run the tests
pytest
```

## What's tested

- Pitch geometry: distance, shot angle (relative ordering and bounds), and the
  defenders-in-cone point-in-triangle logic, including teammate/opponent handling,
  missing freeze-frames, and numpy-array locations from the parquet cache.
- Feature frame assembly: penalties dropped, goals labelled, header flag, and the
  assist-type features (present and defaulted-to-zero cases).

Not yet tested end-to-end: the live data fetch (it hits the network) is exercised
manually via `python -m pitchsense.train`.

## Known limitations

- Single competition (World Cup 2018) — a larger multi-competition training set
  would improve and stabilise the model, and is what would let XGBoost overtake
  the linear baseline.
- No hyperparameter search or cross-validation yet; metrics come from a single
  train/test split with a fixed seed.
- Freeze-frame geometry is summarised as a single defenders-in-cone count; the
  keeper's position and finer spatial detail aren't used yet.

## Roadmap

1. **Data + baseline xG model** (Logistic Regression vs XGBoost, assist-type
   features) — done.
2. Static pitch visualization (single frame of player/ball positions).
3. Animated replay of an event sequence.
4. Quiz layer: pause, guess, compare to the model, explain the gap.
5. Adaptive difficulty + per-concept progress tracking.
6. Stretch: tactical pattern classifier, player-role clustering, leaderboard.
