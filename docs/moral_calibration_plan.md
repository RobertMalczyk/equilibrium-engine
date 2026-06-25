# M-J.4.4 — moral calibration plan (the LLM-judge stage)

> The remaining, non-deterministic half of M-J.4.4. The engine + topology are frozen and litmus-proven;
> every magnitude in `calibration/moral_overlay.yaml` is still a **PLACEHOLDER**. This stage turns the
> placeholders into calibrated values and scores the moral-on corpus with the blind judge.
> Prereqs DONE: deterministic gates A/B/C (`tests/test_moral_gates.py`), per-slice litmus + Jury stability.
> This stage is **budgeted LLM-judge work** — run deliberately, not in CI.

## 1. What gets calibrated (the grid)

Half-lives (spec §11 anchors) + the per-cue gains. Grid axes (spec §10):
`{minor,serious}_guilt_half_life`, `exposure_anxiety_half_life`, `lie_load_half_life`,
`repair_drive_half_life`, `rumination_half_life`, `{weak,evidence}_suspicion_half_life`,
`secret_salience_half_life`, and the dominant gains (`guilt.wrongdoing`, `exposure_anxiety.probe`,
`perceived_injustice.accusation`, `betrayal.{anger,trust,resentment}`, `secret_salience_to_stress`,
`lie_decay`, `salience_decay`). **Invariant:** every half-life stays ≥ 30 min so `dt` is unchanged (Gate A).

## 2. Objective (spec §10 loss)

```
score = 0.35·action_order        # litmus orderings hold (guilt-prone confesses earlier, mach lies more, …)
      + 0.25·curve_plausibility  # state curves read as believable (judge / curve heuristics)
      + 0.20·persona_diff        # different moral personas visibly diverge on the same scenario
      + 0.10·relationship_sensitivity   # trust/resentment/suspicion move sensibly
      + 0.10·no_degenerate_loops # bounded, Jury-stable, no pin-at-1 / dead-system
```

## 3. Staged execution (cheapest first — fail fast before spending judge tokens)

1. **Deterministic pre-filter (free, already built).** For each grid point: load the overlay, assert
   Gate B equivalence holds, Jury margin > 0, all moral states bounded, and the §9.2 invariant orderings
   (`tests/test_moral_*` litmus) pass. Discard any grid point that fails — no judge call. Reuse
   `engine/stability.py` + the litmus runners; extend `eval/sanity_multiday.py` with the moral invariants.
2. **Small judged sample.** Take the surviving grid points; run a SMALL labeled sample (tens of scenarios)
   through the existing blind-judge harness (`eval/regression_judge.py` / `eval/judge_corpus.py`,
   `eval/select_judge_sample.py`). Rank by the §2 score. Keep the top few.
3. **Full judged corpus (the budgeted run).** For the winner(s): the labeled `M-J-MORAL-OVERLAY-ONE-DAY`
   (700) + `M-J-MORAL-OVERLAY-MULTI-DAY` (700) categories WITHIN the existing 1400+1400 budget (an overlay
   axis, NOT added on top — spec §5). Generate with `eval/generate_{day,multiday}_scenarios.py` tagged with
   the moral overlay; judge with the held-constant judge model; gate on the §9.2 invariants + score.

## 4. Corpus partitioning (the four labels, spec §5 / §9.1)

| Label | Judged by |
|---|---|
| `M-J-LEGACY-COMPATIBILITY` | Gate A — byte-identical legacy hashes (already green) |
| `M-J-ZERO-GAIN-EQUIVALENCE` | Gate B — `zero_gain_overrides` behavioral equivalence (already green) |
| `M-J-MORAL-OVERLAY-ONE-DAY` (700, within budget) | Gate C — moral invariants + trace explainability |
| `M-J-MORAL-OVERLAY-MULTI-DAY` (700, within budget) | Gate C — moral invariants + trace explainability |

Plus the micro-suite (the existing `tests/test_moral_*` — invariant unit-proofs), counted inside the budget.

## 5. Harness reuse (no new judge infra)

- Overlay loader: `eval/moral.py` (`moral_overrides` / `zero_gain_overrides`).
- Grid runner: mirror `calibration/calibrate_burst.py` (the burst-style overlay calibrator).
- Blind judge: `eval/regression_judge.py`, `eval/judge_corpus.py`, `eval/judge_multiday.py`,
  `eval/select_judge_sample.py`; hold the judge model constant (risk R11), prefer deterministic
  narration-diff where possible.
- Scenario gen: `eval/generate_day_scenarios.py`, `eval/generate_multiday_scenarios.py` (+ moral tagging).
- Reports: `eval/test_report.py` / `eval/hourly_report.py` pattern.

## 6. Definition of Done

Placeholders replaced by calibrated half-lives/gains; the moral-on slice clears the §2 score threshold and
all §9.2 invariants under the held-constant judge; Gates A/B stay green; goldens re-baselined ONLY if a
conscious moral-trace change is intended (bump `TRACE_VERSION`); corpus stays within 1400+1400.

## 6a. Multi-day stage — findings (2026-06-25, `eval/moral_multiday.py`)

The judge **step-2 loop is validated** on Sonnet (mean believability 3.17 → 4.83 over one collect-fix-rejudge
pass; `calibration/moral_judge_verdict.json`). Moving toward the full corpus (step 3), the MULTI-DAY axis was
investigated, since the half-lives only discriminate over days:

- **The multi-day moral dynamics work.** On the believable day layout (dt≈120s, ~717 ticks/day), serious
  guilt **survives the night** (0.46 → 0.42 across a night's sleep — the sleep reset decays the FAST states,
  not the slow moral ones, exactly as spec §9.2 requires).
- **The half-life signal is REAL and discriminating** — with PRIVATE wrongdoing-reminders (a SELF cue: raises
  guilt, opens no reply window, so no confession resolves it), the evening-guilt trajectory separates cleanly
  by half-life: 6h ≈ `[0.04,0.05,0.05]` (forgotten by evening), 18h ≈ `[0.15,0.21,0.23]`, 72h ≈
  `[0.23,0.42,0.56]` (a deepening burden). This is the curve_plausibility signal the judge scores.
- **Two scenario/renderer requirements surfaced for step 3:**
  1. The arc must keep the wrong UNRESOLVED — interrogation (probe) triggers a confession that relieves guilt
     to 0, flattening the half-life signal. Use private reminders, or a persona who conceals.
  2. The observable renderer must SURFACE the lingering burden. Over long idle days, boredom→seek builds
     incidental frustration that an anger-first demeanor read masks; `render_moral._demeanor` needs a
     multi-day variant that weights the (real, discriminating) guilt over the incidental idle-day mood.

**Status:** the multi-day methodology + the half-life signal are proven; the full judged 700+700 corpus is
the budgeted scale-up, pending (1) multi-day moral scenarios with balanced activity and (2) a burden-surfacing
multi-day renderer.

## 7. Budget note

Steps 1 (pre-filter) and the existing deterministic gates are free. Step 2 is a small judged sample (cheap).
Step 3 is the expensive run (≈1400 moral-overlay scenarios judged). Sequence 1→2→3 so judge tokens are spent
only on grid points that already pass the deterministic gates.
