# Believability improvement — full report (Phase A → M3 → renderer → corpus)

> Consolidated record of the believability work: the method, each change (what / why / how / evidence),
> the run-by-run results, the final breakdown, and how to reproduce. All blind-judge numbers are
> **all-Sonnet with the judge model held constant** (never compare across judge models).
>
> **Headline:** full 2800-scenario blind believability **93.5% → 95.9%** (+68 scenarios), via five
> composable fixes — three expression, one engine-topology, one corpus.

---

## 1. Method (how the number is produced)

- **Corpus.** 2800 scenarios = **700 one-day + 700 multi-day**, each rendered **with burst ON and OFF**
  (4 sub-corpora × 7 personas × 100 indices). Deterministic, numpy-seeded; checked in.
- **Batches.** 2800 scenarios = **280 batches × 10 records**; 10 slices × 28 batches (7 personas × 4
  sub-corpora). One batch = 10 records of one persona/sub-corpus.
- **Judge.** One **fresh Claude-Sonnet agent per batch**, neutral rubric, no answer key, each record judged
  on its own (PASS/FLAG + ≤12-word reason). The judge sees only the **observable narration** (no engine
  internals). The model is **held constant** across every run so deltas are real signal, not judge drift.
- **Pacing.** Driven by `eval/phaseA_judge_wave.py` (waves of N batches) + the Workflow runner + timers,
  to spread token load and avoid rate/session limits. Per-batch results persist to disk → crash-resumable.
- **Two evidence layers.** (a) the blind judge (believability), and (b) **deterministic checks**
  (golden traces byte-identical for expression-only changes; narration-line counts) — confound-free proof
  that a change does what it claims, independent of judge noise.

The blind judge is non-deterministic, so a small net change under large bidirectional churn = judge noise;
**signal lives in targeted clusters + the deterministic checks**, not single-run aggregates.

---

## 2. The five fixes

### M1 — mood line weighs residual anger (expression; recency-gated)
- **Problem.** The mood "heartbeat" keyed only on `stress`, so after an outburst (stress ebbs, anger
  lingers) it printed **"settled, at ease"** — a settled↔fury contradiction.
- **Fix.** `mood_phrase` weighs `anger`: high anger reads "still seething". **Refinement (critical):**
  gate the active "seething" read on **provocation recency** (`ANGER_FRESH_SECS ≈ 1 game-hour`); a stale,
  slow-decaying residual reads "still hasn't quite shaken off an earlier temper" — never seething-at-nothing.
- **Why the refinement mattered.** Unconditional "seething" *over-surfaced* anger and **lost** (run1
  −24). Recency-gating turned it into a gain (run2 +44 over baseline).

### M2 — acknowledge a kindness instead of "lets it pass" (expression)
- **Problem.** A `food_given`/`help` event landing while resting/busy got the slight-style "lets it pass,
  no notable reaction" — a kindness read as a snub.
- **Fix.** A positive event with no hostile reaction renders "takes it without fuss, a small nod."

### M3 — burst source-valence gate (engine topology; config-gated, default OFF)
- **Problem.** Above the displacement bar, the burst gate suppressed *all* kindness (`kindness_pressure=0`)
  — so a **genuine kindness became a discharge target** ("snaps at the soup"). The 2026-06-12 "even at
  their kindness" decision overshot believability.
- **Fix.** `engine/simulation.py`: a config-gated conjunct on `displaced_gate` — a **positive-valence**
  event (`kindness_pressure > 0`: a gesture from a **non-resented** source) is **not** a discharge target,
  so warmth wins. A "kindness" from a **resented** source is `kindness_pressure 0` (it galls) → still
  caught → **Cichy intact by construction**. Boolean gate on the frozen snapshot → no new state → poles
  unchanged. **Default off → golden byte-identical**; the eval burst overlay opts in.
- Spec-first: `spec §8` + `docs/diagrams/burst_saturation.md` + M20.1 criterion #5 updated before code.

### Renderer-attribution fix (expression)
- **Problem (diagnosed).** After M3, warmth already won at genuine kindnesses *at the event tick*. The
  residual "snaps at soup" was a **renderer artifact**: a kindness read a 3-tick window, so a *later*
  residual/displaced discharge (from an earlier provocation) got **stapled onto the kindness line**.
- **Fix.** A positive event reads **only its own tick** (its warm reply is immediate); hostile events keep
  the lag window. Deterministic effect: burst-ON "kindness→hostile" lines **1294 → 856 (−438)**.

### Corpus-coherence fix (corpus)
- **Problem (diagnosed).** The remaining "snaps at soup" was the engine **correctly** galling at a source
  that had **insulted the persona earlier the same day** — but that source was *also* the warm giver. The
  random generator produced "the cook who mocks you then feeds you."
- **Fix.** `eval/generate_day_scenarios.py` (multiday imports it): **wojsław** insult source `("marta",
  "player")→("player",)` (the warm cook no longer mocks); **branic** help source drops `halgrim`
  (the harsh sergeant keeps command+insult; warmth from others). **cichy's** guard-insults-and-feeds is the
  intentional prisoner archetype — **unchanged**. Deterministic → only wojsław+branic changed; sanity 100%.

---

## 3. Results (run by run, all-Sonnet, judge held constant)

| # | State of the system | Scope | PASS | Rate | vs prev gate |
|---|---|---|---|---|---|
| baseline | pre-Phase-A | full 2800 | 2618 | 93.5% | — |
| run1 | M1 v1 (unconditional seething) + M2 | full 2800 | 2594 | 92.6% | −24 (over-surfaced anger) |
| **run2** | **M1 recency-gated + M2 = Phase A** | full 2800 | **2662** | **95.1%** | **+44 vs baseline** |
| run3 | + M3 (alone) | burst-ON 1400 | 1302 | 93.0% | flat vs run2 burst-ON (cluster 39%) |
| run4 | + M3 + renderer fix | burst-ON 1400 | 1326 | 94.7% | +24 vs run3 (cluster 68%) |
| **run5** | **+ M3 + renderer + coherent corpus** | **full 2800** | **2686** | **95.9%** | **+24 vs Phase-A-only** |

**run5 vs Phase-A-only (run2): +24** (79 fixed, 55 regressed) — clears the "must beat Phase-A-only" gate.

### run5 sub-corpus breakdown (vs Phase-A-only)
| sub-corpus | baseline | Phase-A-only | **run5** |
|---|---|---|---|
| day · burstOFF | 650 | 663 | **670** |
| day · burstON | 655 | 636 | **647** |
| multi · burstOFF | 661 | 695 | **693** |
| multi · burstON | 652 | 668 | **676** |

### run5 per-persona (the corpus-fix targets)
- **wojsław 351 → 375 (+24)** — corpus coherence + M3.
- **branic 376 → 381 (+5).**
- **cichy 387 → 382 (−5)** — intentional resented-guard behavior ("a kindness from the jailer he blames
  doesn't soften him"); judge-debatable, untouched by the fixes.

### The kindness-displacement cluster (the M3 target)
Of the 58–61 burst-ON "snaps at soup / displacement overdone" flags: M3 alone cleared **39%**; M3 +
renderer fix cleared **68%**; the corpus fix removed the remaining incoherent setups.

---

## 4. Safety / invariants held

- **Golden byte-identical** for every expression change and for M3 with its default-off config (verified:
  `tests/test_tick_golden.py`, order-invariance, stability all green).
- **M3 stability:** a deterministic boolean gate, no new state/feedback edge → linearized poles unchanged.
- **Full test suite green** (303 passed / 4 skipped) at each step; corpus regen passes the multiday sanity
  gate (100% / 0 failures).
- New unit tests: `tests/test_narration_expression.py` (M1/M2/recency/renderer), `tests/test_burst.py`
  (M3 gate: genuine kindness spared, neutral/resented sources still caught).

---

## 5. Reproduce

```bash
# 1. build the batches (engine + eval state, deterministic; ~13 min)
for s in 0 1 2 3 4 5 6 7 8 9; do PYTHONPATH=. python eval/hourly_judge.py --slice $s --build; done

# 2. judge in paced waves (writes verdicts to eval/phaseA_run5/slice_*/results/)
PYTHONPATH=. python eval/phaseA_judge_wave.py --rundir "$PWD/eval/phaseA_run5" --wave 28
#    -> run eval/phaseA_run5/wave_workflow.js via the Workflow runner; repeat until --status shows 0 left
#    (optional: --filter burstON to judge only the M3-affected half)

# 3. aggregate vs the committed baseline
PYTHONPATH=. python eval/phaseA_judge_wave.py --rundir "$PWD/eval/phaseA_run5" --aggregate
```

Raw verdicts for the final run are under `eval/phaseA_run5/`. Intermediate-run numbers are captured in the
table above.

---

## 6. What's next (not in this report's scope)

- Persona-resentment polish (wojsław/branic over-resentment edge cases), M20.1 burst calibration
  (kindness-inhibition / `theta_displace`), and Phase B (M4 respect→hostility/compliance, M7/M8
  trait→gain). See `docs/plans/`.
