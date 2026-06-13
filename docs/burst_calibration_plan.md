# M20.1 — Outburst / burst-saturation calibration plan

> Branch: `m20.1-outburst-calibration` (off `main` @ `3dcf4a3`, the burst merge).
> Status: **PLAN ONLY — no development yet.** Spec of record: §8 (burst & saturation),
> §14 (coupling escalation), §16 (calibration loop). Diagram: `docs/diagrams/burst_saturation.md`.
> Design rationale: `Ideas/burst_saturation_design_note.md` (private overlay).
> This plan calibrates the **magnitudes** of a frozen topology. It chooses no numbers by hand —
> it specifies the gates, the method, and the scenarios that will produce them.

---

## 0. One-paragraph framing

The burst subsystem is **structurally complete and inert**: the escalation factor `k_esc`, the
burst latch, the extinction term, Loop 2 (relief-seeking through the world), and the
`theta_displace` displacement gate are all implemented and ship as neutral defaults
(`0`/disabled), so today's behaviour is bit-identical. M20.1 turns the feature **on** by
calibrating its ~8 magnitude families under a **boundedness** gate (not a pole gate), at the
**measured G6 operating points**, while preserving every existing litmus contrast and the
1400-scenario blind-regression baseline. This is the method change the design note flagged:
the anger⇄stress loop is deliberately driven *locally unstable* in rare drive-coincidences, and
**saturation + extinction + latch** — not weak gains — keep it bounded.

---

## 1. What we want to achieve (success criteria)

1. **A real outburst exists.** For at least the burst-prone personas (wojsław; the M20.1 memo
   names **cichy_060** (`eval/scenarios/day/cichy/cichy_day_060.yaml`) as the residual that must
   clear), a sufficiently bad stacked day produces
   a genuine spike→plateau→slow-cool episode — fury that *holds* — not a gentle weak-gain rise.
2. **It is bounded — always.** Every latched episode extinguishes and the latch releases below
   `theta_burst_exit` within a bounded time and **stays down** (no re-ignition without fresh
   drive). This is the **boundedness gate**, made quantitative (§5, G3*).
3. **It is rare and earned.** Linear stability is *preserved* at the frequent G6 combinations
   (pairs, ≤13.9% of ticks); bursts fire only in the accepted ≥3-way region (0.89%), and only
   when discharge is blocked (the loaded-spring condition).
4. **Nothing else regresses.** All litmus contrasts (burst-vs-suppress A, obey-vs-refuse B,
   prisoner-3-way C) hold bit-for-bit where burst is off; the 1400-scenario blind regression
   does not regress below the M20 baseline (**day 698/700, multi 626/630**); the multiday sanity
   gate stays at its current pass rate with burst calibrated on.
5. **The episode texture is right.** Spike→plateau→slow-cool over ~"an hour" of game time;
   displacement lands on the bystander as transient (no durable grudge); kindness suppressed
   above the bar, honoured below it.

**Non-goals (explicitly deferred):** the stage-2 authority↔resentment back-edge, mood contagion,
leveled grievance, and the affinity-field people-seeding — all tracked separately. M20.1 does not
touch Layer-1/Layer-2 gains already calibrated; it adds the burst overlay *on top of* them.

---

## 2. What we already have (inventory — do not rebuild)

| Asset | Where | State |
|---|---|---|
| Escalation math `g_eff = g·(1+k_esc·y)` | `engine/update.py` | implemented; `k_esc=0` default = exact linear loop |
| Burst latch (band + confirm + hysteresis) | `engine/simulation.py`, `engine/schema.py` (`burst_latched`, `last_provocation_*`) | implemented; disabled when thresholds absent |
| Extinction term (while latched) | `engine/update.py` (`burst_extinction`) | implemented; empty dict default = inert |
| Loop 2 edges (seek cost / relief urge) | `calibration/defaults.yaml` (`seek_stimulus.per_tick.stress`, `urge_boredom.stress`) | implemented; `0` default |
| `theta_displace` + displaced booking | `engine/simulation.py`, `appraisal.displaced_relational_discount` | implemented; disabled default |
| Structural tests **G0–G5** | `tests/test_burst.py` (29 tests) | **green** — math, latch discrimination, boundedness-exists, displacement, config-error guards, determinism |
| Block diagram (control + functional) | `docs/diagrams/burst_saturation.md` | in sync with code |
| **G6 co-occurrence data** | `eval/burst_cooccurrence_report.md`, `eval/measure_cooccurrence.py` | **measured**: pairs 13.9% (hungry+tired 11.0%), ≥3-way 0.89% |
| Demo arcs (5) | `eval/burst_eval.py` | rich-relief, barren-windup, loaded-spring displacement, extinction, spike-no-burst |
| Calibration framework | `engine/calibration.py`, `engine/loss.py` | Layer-1/2: Morris screen → CMA-ES → hard acceptance gate → provenance YAML |
| Regression corpora | `eval/scenarios/{day,multiday}/`, `eval/sanity_multiday.py`, judge harness | 700+700; sanity gate 7-checks; blind-judge batches |

**Conclusion: no new topology, no new state, no new test *category* is needed.** What is missing
is (a) the numbers, (b) a quantitative boundedness gate to choose them against, and (c) a small
set of *bad-day* calibration scenarios that actually reach the ≥3-way region.

---

## 3. Parameters to calibrate (the free set)

Eight families, in two groups. **No number is chosen by hand** — each is an output of §4.

**Group A — the burst core (the boundedness loop):**

| # | Param | Role | Neutral | Bound / constraint |
|---|---|---|---|---|
| A1 | `coupling_escalation.anger.stress` (`k_esc⁺`) | escalation on anger←stress edge | 0 | ≥0; linear stability must hold at all G6 *pairs* at their operating points |
| A2 | `coupling_escalation.stress.anger` (`k_esc⁻`) | escalation on stress←anger edge | 0 | ≥0; same Jury-at-operating-point constraint |
| A3 | `burst_extinction.anger`, `.stress` | relaxation rate while latched | {} | in (0,1); must **dominate** escalated coupling off-ceiling (boundedness) |
| A4 | `theta_burst_enter.anger`, `.stress` | latch arm band | disabled | both in (0,1); arm only on the loop plateau |
| A5 | `theta_burst_exit` + `burst_confirm_ticks` | release hysteresis + dwell | disabled | `exit < enter.anger`; confirm ≥1 |

**Group B — the surrounding behaviour:**

| # | Param | Role | Neutral | Constraint |
|---|---|---|---|---|
| B1 | `derived_weights.urge_boredom.stress` (`w_s`) | Loop 2 relief-seeking return edge | 0 | rich world → stress descends; barren → wind-up |
| B2 | `action_params.seek_stimulus.per_tick.stress` | Loop 2 forward (fruitless looking wears you down) | 0 | small; barren-world monotone wind-up only |
| B3 | `theta_displace` | displacement bar (THE dial) | disabled | `>> react.*`, `< ` typical burst-anger so it actually fires |
| B4 | `appraisal.displaced_relational_discount` | grudge on the innocent bystander | 0 (transient) | keep at 0 unless a target says otherwise (provenance) |

---

## 4. Calibration method (per the project's calibration discipline)

Following the standing rules — *1-D sub-blocks via deterministic scalar search, not a blind
CMA-ES over everything; contrast gates as min-margin not weighted sum; one absolute anchor, the
rest relative; every target carries provenance* — the order is **inner loop → boundedness →
behaviour → contrasts**, each stage frozen before the next:

- **Stage C1 — `k_esc` (A1, A2) against the Jury-at-operating-point constraint.**
  For each frequent G6 pair, compute the *escalated local gain* `g·(1+k_esc·y*)` at that pair's
  operating point `y*` and require the 2-cycle Jury margin to stay positive. This is an analytic
  inequality per pair → solve for the **largest** `k_esc` that keeps every pair stable (we *want*
  escalation strong, bounded only by "pairs must stay linear"). Deterministic; no optimizer needed
  — it is a feasibility frontier read off `eval/measure_cooccurrence.py` operating points + the
  existing Jury/spectral-radius routine in `engine/stability.py` (used by `engine/loss.py`). Verify the complement: at least one ≥3-way combination
  crosses the bound (otherwise the burst can never fire).

- **Stage C2 — extinction (A3) against the boundedness gate.**
  Given `k_esc` from C1, find the extinction rate s.t. a latched trajectory from the ceiling
  returns below `theta_burst_exit` within target time T_cool (~"an hour" of game time, in believable
  dt) and stays down. 1-D deterministic search (`minimize_scalar` on "time-to-release minus target",
  or smallest rate meeting the return-and-stay predicate). The design-note condition — *extinction
  dominates escalated coupling outside the saturated region* — is the analytic sanity check.

- **Stage C3 — latch band + hysteresis (A4, A5).**
  Set `theta_burst_enter` at the saturation band entry (where the escalated loop has actually
  spiralled, read from the C1/C2 trajectories), `theta_burst_exit` below it for chatter-free
  release, `burst_confirm_ticks` long enough to reject single-tick spikes but short vs. the plateau.
  Chosen from the trajectory geometry, not free-optimised; guarded by the existing G4 discrimination
  test and the `confirm_dwell_reset` test.

- **Stage C4 — Loop 2 (B1, B2).**
  Calibrate `w_s` and the seek stress-cost so that in a **rich** mock world stress descends
  (relief) and in a **barren** world it is a monotone wind-up that lifts Loop 1's operating point
  into burst range. Two-scenario contrast (rich vs barren), min-margin between the two slopes.

- **Stage C5 — `theta_displace` (B3) and discount (B4).**
  `theta_displace` is set so displacement fires only in deep burst (above typical reactive anger,
  below the plateau). Validated by the existing G5 displacement tests; the discount stays 0 unless
  a story/persona target with provenance says a particular character carries a partial grudge.

**Provenance:** one absolute anchor (the believable cool-down duration T_cool, justified from the
design note's "~an hour" and the believable-timescale corpus); every other burst number expressed
**relative** to it or to the already-calibrated Layer-2 gains. Output written to a new
`calibration/calibrated_burst.yaml` with the same provenance shape as `calibrated_layer2.yaml`
(seed, free_set, reads_on_top_of, per-param status), leaving `defaults.yaml` untouched.

---

## 5. Tests / gates needed (what proves it)

**Already green (keep green — regression guard):** G0 (ship inert), G2 (escalation math),
G4 (latch discrimination), G5 (displacement), config-error guards, determinism — all in
`tests/test_burst.py`.

**New tests to add (the calibration-acceptance layer):**

| Gate | New check | Home |
|---|---|---|
| **G3\*** boundedness, quantitative | with the *calibrated* `k_esc`+extinction (loaded from `calibrated_burst.yaml`), every seeded bad-day scenario that latches releases within T_cool and final anger `< theta_burst_exit`; assert across the bad-day set, not one fixture | `tests/test_burst_calibration.py` (new, `@slow` ok) |
| **G2\*** stability-at-pairs | for each frequent G6 pair, the escalated-local-gain Jury margin is ≥ 0 at the measured operating point; the chosen `k_esc` is the feasibility frontier | new test reading `measure_cooccurrence` operating points |
| **G6\*** burst actually fires | at least one ≥3-way bad-day scenario produces `burst_latched=True` for a sustained plateau (otherwise the calibration is vacuously safe) | new test |
| **Loop-2 contrast** | rich-world stress-descends vs barren-world wind-up, on the mock-world runner | `eval/` scenario test |
| **Contrast preservation** | A/B/C litmus matrices unchanged where burst is off; with burst on, burst-vs-suppress *margin widens* (wojsław bursts harder, halgrim still suppresses) — min-margin, not absolute | extend `tests/test_acceptance_matrix.py` |
| **Golden traces** | regenerate only the burst-on goldens deliberately; all burst-off goldens byte-identical (G0) | `tests/golden/`, `GOLDEN_REGEN=1` |

**Regression (the big gate):** re-run the **1400-scenario blind regression** (700 day + 700
multiday) with the burst overlay active and confirm **no regression** vs the M20 baseline
(day 698/700, multi 626/630); re-run `eval/sanity_multiday.py --all` (7-check gate) and confirm
the pass rate holds; target the **cichy_060** residual clears. Blind-judge a fresh batch on the
bad-day scenarios specifically (the episodes are the new behaviour the judge has not seen).

---

## 6. Scenarios to construct (and their sources)

The existing corpora rarely reach the ≥3-way region by design (0.89% of ticks) and never hold
the **loaded-spring / blocked-discharge** condition that produces a *plateau* rather than a vented
spike. So M20.1 needs a small, deliberate **bad-day calibration set** — the only genuinely new
authoring work.

| Set | Purpose | Count | Construction | Source of the content |
|---|---|---|---|---|
| **Bad-day stack** | drive the ≥3-way coincidence so the loop spirals | ~6–10 | hand-authored YAML in `data/scenarios/` (calibration benchmarks, same format as `same_soup_bad_day.yaml`): hunger + fatigue + repeated provocation + fruitless seeking stacked over a believable day | **Sapkowski keep day-types** already in the multiday generator (`short_rations` + `drill` + `foul_weather` + `bad_blood`) — compose the existing lore-flavoured multipliers, do not invent new channels |
| **Loaded-spring (blocked discharge)** | the plateau: hot, pinned, *no one to vent on* until a bystander arrives | ~3 | extend the `eval/burst_eval.py` loaded-spring arc into seeded scenarios; provoker absent, then a kind/neutral bystander at the peak | the wojsław/Marta measurement already cited in `test_burst.py` G5 |
| **Rich vs barren world pair** | Loop 2 sign (relief vs wind-up) | 2 | one scenario in a mock world with activities available, one barren | mock-world runner (`eval/`), `seek_stimulus` semantics |
| **cichy_060 (the named residual)** | the specific scenario M20.1 must fix | 1 | locate `cichy` day-scenario index 060 in `eval/scenarios/day/cichy/`; if it is the fury-on-waking / dense-refusals residual, it is the acceptance target | existing corpus + the project-status residual note |
| **Persona-contrast trio** | bursts differ by persona, not by a per-persona number | 3 (wojsław/halgrim/branic) | same bad-day excitation, three personas → burst / suppress / obey-priority | `data/personas/*.yaml` traits; contrast must emerge from state+traits, not a hand-set per-persona burst param |

**Authoring discipline:** scenarios are **deterministic** (numpy-seeded, not LLM-generated);
predicates use the existing predicate types (threshold/boolean/comparative/shape); content is
sourced from the existing Sapkowski day-type vocabulary and the cast/relation graph in
`rpg_persona_dynamics_persony.md` — **no new event channel, no new persona, no invented numbers.**

---

## 7. Work sequence (when development starts — not now)

0. **Spec/diagram check.** Re-read spec §8/§14/§16; confirm the diagram still matches. If C1–C5
   reveal a topology gap (a bug present at *every* weight), stop and fix topology in the spec first.
1. Author the bad-day + loaded-spring + rich/barren calibration scenarios (§6). Verify they reach
   the ≥3-way region and (for loaded-spring) hold the plateau — *before* any number is tuned.
2. C1 `k_esc` feasibility frontier → C2 extinction → C3 latch geometry → C4 Loop 2 → C5 displacement
   (§4), each frozen and its gate green before the next. Write `calibration/calibrated_burst.yaml`.
3. Add the G2\*/G3\*/G6\* + Loop-2 + contrast tests (§5); regenerate burst-on goldens deliberately.
4. Wire the calibrated burst overlay into the eval loader (alongside `recovery`/`timescale`
   overrides) behind an explicit opt-in so burst-off paths stay bit-identical.
5. Full suite green → `eval/sanity_multiday.py --all` → **1400-scenario blind regression** →
   targeted blind-judge of the bad-day episodes. Confirm cichy_060 clears, no regression elsewhere.
6. Update spec §8 status (placeholders → calibrated) + the diagram's status line; PR to public main.

**Commit-per-step, spec-first, measure-before-deciding.** Respect the push window (no remote pushes
9:00–15:00 Mon–Fri; commit locally, push outside).

---

## 8. Risks / open questions to resolve during the work

- **Feasibility tension:** if the largest `k_esc` that keeps all pairs linearly stable is *too
  small* to ever spiral at ≥3-way, the burst is vacuous → revisit whether a pair's operating point
  is mis-binned, or whether the band thresholds (not `k_esc`) should carry more of the trigger.
- **cichy_060 diagnosis first:** confirm what the residual actually is (fury-on-waking vs
  dense-refusals vs mild-grumble) before assuming the burst overlay is the fix — it may be a
  night-reset or target-policy interaction, not a burst-tuning task. Classify against LIGHTHOUSE
  before treating as a problem.
- **Believable-timescale interaction:** T_cool (~an hour) must be expressed in the believable dt,
  and the latch confirm/dwell counters are in *ticks* — re-derive them when the time_scale knob is
  applied, or the latch geometry shifts under the eval timescale.
- **Goldens:** burst-on changes some traces by design; be deliberate about which goldens are
  regenerated and prove every burst-*off* golden is byte-identical (G0 is the guard).
- **Contrast must stay dynamics-born:** resist a per-persona `k_esc`/`theta` as anything but a
  temporary stopgap; the burst-vs-suppress split should come from traits→state, not a hand-set
  per-persona burst number.

---

## 9. Definition of done

- `calibration/calibrated_burst.yaml` exists with full provenance; `defaults.yaml` untouched.
- `tests/test_burst_calibration.py` (G2\*/G3\*/G6\* + Loop-2 + contrast) green; full suite green.
- Burst-off goldens byte-identical; burst-on goldens deliberately regenerated.
- 1400-scenario blind regression: no regression vs M20 baseline (day 698/700, multi 626/630).
- `sanity_multiday.py --all` pass rate held; **cichy_060 clears**.
- Spec §8 + diagram status updated (calibrated, not placeholder); the subsystem is "done" only
  with the synchronized diagram (project rule).
