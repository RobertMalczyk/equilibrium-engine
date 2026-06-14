# M20.1 — Outburst / Burst-Saturation: STATUS (resume doc)

**Branch:** `m20.1-outburst-calibration` · **HEAD:** `d94e5cb` (pushed to origin).
**NOT on `main`** — 16 commits ahead of `origin/main`, 0 behind, cleanly mergeable, **no PR open**.
**Suite 223 green · `calibration/defaults.yaml` + all goldens BIT-IDENTICAL** — the whole feature ships
**inert by default** and is opt-in via `burst=True`. Nothing is live in the shipped engine yet.

> This file is the single place to resume M20.1 after a session reset. Companion: the full plan in
> `docs/burst_calibration_plan.md`; the spec is `docs/rpg_persona_dynamics_spec_v1.md` §8; the diagram
> is `docs/diagrams/burst_saturation.md`.

---

## The core idea (design philosophy — read this first)

An outburst is a **stability safety valve (a "vent")**, NOT a per-loop dramatic feature. Each *main
pair* of positive feedback loops is individually calibrated **stable** (poles inside the unit circle).
But a character is rarely under one pressure — an insult AND rain AND hunger AND a barren day can excite
several **unrelated** loops at once, and the stability of every such **combination** cannot be
pre-certified (combinatorial, nonlinear). The vent is the global safety mechanism that catches it: when
stacked pressures saturate the shared loop states, it latches, **discharges**, and returns the system to
bounded — so the whole character stays bounded even though only the individual pairs were proven.

**Corollary (load-bearing):** a SINGLE loop — even a relentless one — must stay bounded **without**
venting. A lone relentless provoker is one stable loop; it correctly stays below the band and does NOT
vent. (This retired `cichy_multi_060` as a "must-vent" target — see below.)

---

## What is DONE ✅

### Calibration C1–C5 (`calibration/calibrate_burst.py` → `calibration/calibrated_burst.yaml`)
Every value anchored/provenanced; deterministic; no optimizer. Tests in `tests/test_burst_calibration.py`.

| stage | parameter(s) | value | basis |
|---|---|---|---|
| C1 | `coupling_escalation.{anger.stress, stress.anger}` (k_esc) | **1.10** | feasibility frontier: single pairs stay linearly stable across the whole observed envelope; only the band spirals. KEY finding: ≥3-way pairs don't out-reach ≤2-way, so k_esc can't gate on coincidence count — the **latch band** carries selectivity. |
| C2 | `burst_extinction.anger / .stress` | **0.0435 / 0.0276** | one scalar β=0.65, `ext=β·(1−decay)`; anchored to T_cool=1h=30 ticks; smallest that returns (1,1)→below exit within T_cool, monotone, λ_max=0.976<1. anger faster than stress. |
| C3 | `thresholds.burst_enter.anger/.stress`, `burst_exit`, `burst_confirm_ticks` | **0.80 / 0.60**, **0.40**, **2** | enter = just above the frequent ≤2-way ceiling (0.70/0.526) AND at the spiral boundary; exit < enter & below reactive p99 (0.4426) → chatter-free; confirm=2 = minimal dwell>1. |
| C4 | `action_params.seek_stimulus.per_tick.stress` (B2) / `derived_weights.urge_boredom.stress` (B1) | **0.02** / **0** | B2 = half the rich relief rate (engaging dominates looking). B1 **measured-inert** (boredom already drives seeking; not identified by the contrast). |
| C5 | `thresholds.theta_displace` / `appraisal.displaced_relational_discount` | **0.60** / **0.0** | theta = midpoint of latch band [0.40, 0.80] (deep-burst only). discount 0 = grudge on the innocent fully transient (no fabricated nemesis). |

### Vent acceptance criterion — REFRAMED (`eval/verify_vent_boundedness.py` + tests)
The real gate (replacing the mis-aimed cichy target):
- **(1) SILENT on a single/ordinary load** — `ordinary_pair` never latches. ✅
- **(2) FIRES + SELF-TERMINATES on a ≥3-way coincidence** — `bad_day_stack` arms then discharges
  (anger 1.0→0.47) and the latch releases. ✅
- (3) corpus-wide boundedness = **step 5, still pending** (below).
- Gotcha: a no-mock-world long run leaves the persona fruitlessly SEEKING → a frustration→anger climb
  that is an **artifact**, not the vent. Measure over the forcing+discharge window.

### Spent-fury refractory edge — DECOUPLED from the vent latch (spec-first; `d94e5cb`)
- spec §8 + `docs/diagrams/burst_saturation.md` rewritten: "latched-provoker" → **"spent-fury,"**
  decoupled.
- `engine/simulation.py` `_refractory_pressure`: arms on a **same-source re-provocation while
  anger ≥ `thresholds.refractory_anger`** (the carried heat of a recent eruption), NOT on `burst_latched`.
  The term `refractory_pressure × resentment[src]` is still read **−1.0** by `outburst` (weights already
  in defaults). `refractory_anger` **unset → 0 → bit-identical default**.
- `calibrated_burst.yaml`: `thresholds.refractory_anger = 0.30` (~2× calm baseline; gates the REPEAT,
  never the first eruption = a new source). Superset of the old latch gate (also covers latched bursts).
- **Effect on `cichy_multi_060` (overlay on): 8× `cold_response` + 2 outburst (was 9 outbursts)** — the
  spent fury goes cold WITHOUT the single loop ever venting. `tests/test_burst.py::test_refractory_fires_WITHOUT_the_latch`.

### Overlay wiring (`eval/calibrated.py`)
`burst_overrides()` reads `calibrated_burst.yaml`; `load_eval_persona(..., burst=True)` and
`load_eval_persona_timescale(..., burst=True)` opt in (default False = bit-identical). Threshold keys
with literal dots (`burst_enter.anger`) are kept flat.

---

## What REMAINS ⏳ — Step 5: the corpus-wide boundedness regression (the last gate)

Run the day + multiday corpora with `burst=True` and confirm:
- **NO scenario stays pegged at saturation** (the vent keeps every combination bounded);
- the **vent fires only on genuine coincidences** (not on single/ordinary loads);
- **no regressions** vs the M20 baseline (**day 698/700, multi 626/630**);
- `cichy_multi_060` now reads as one cold-episode, not N eruptions.

How to run (thread `burst=True` through the corpus runners — `eval/sanity_multiday.py` builds cfgs via
`load_eval_persona_timescale`; the 1400 regression harness lives under `eval/`). Acceptance = boundedness
+ no-regression, **NOT "cichy vents"**. If clean → the overlay can be promoted from opt-in toward default,
then **open a PR / merge to `main`** (currently neither done).

Until step 5: all calibration is verified **in isolation** (analytic cool-down, two-world contrast,
threshold geometry, single benchmark scenarios). End-to-end believability across the full corpus is
proven only at step 5.

---

## Key files
- `calibration/calibrate_burst.py` — C1–C5 solver + provenance (run: `PYTHONPATH=. python calibration/calibrate_burst.py`).
- `calibration/calibrated_burst.yaml` — the overlay (generated; do not hand-edit).
- `eval/calibrated.py` — `burst_overrides()` + the `burst=` opt-in.
- `eval/verify_vent_boundedness.py` — the reframed vent acceptance (silent/fires+bounds).
- `eval/verify_burst_overlay.py` — cichy diagnostic + the reframe/decouple narrative.
- `tests/test_burst.py` (G2–G7, incl. the decoupled refractory tests) · `tests/test_burst_calibration.py` (C1–C5 + reframed acceptance).
- `engine/simulation.py` `_refractory_pressure`, latch transitions; `engine/update.py` extinction; `engine/potentials.py` refractory term.

---

## Out of scope / parallel (not part of this branch)
- **Game-facing test expansion** (player-like streams, social-memory, long-run): a scheduled cloud
  routine fired on 2026-06-13T23:20Z but **did not land** any branch/PR (cloud runner lacks GitHub
  write access; ephemeral session). To be re-run **locally** on a fresh `game-facing-tests` branch off
  `main`. NOT started in-repo.
- **Teaser films** (PRIVATE `video/` repo, separate): overview-v2 (133s), burst-saturation-v3 (117s,
  multi-loop vent framing), affinity-field-v2 — all ElevenLabs audio, awaiting watch/upload. Unrelated
  to the engine branch.
