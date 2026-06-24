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

## 7. Detailed pass / fail

> **Full per-scenario report** (every scenario's PASS/FLAG + stimulus + narration, TEST_REPORT style):
> `eval/hourly_runs/TEST_REPORT.md` / `.html` (regenerated from run5).

### 7a. Believability — final run (run5): **2686/2800 PASS, 114 FLAG**

FLAGs by persona:

| persona | FLAGs |
|---|---|
| wojslaw | 25 |
| halgrim | 23 |
| lutek | 23 |
| branic | 19 |
| cichy | 18 |
| edda | 4 |
| welf | 2 |

FLAGs by sub-corpus:

| sub-corpus | FLAGs |
|---|---|
| day burstON | 53 |
| day burstOFF | 30 |
| multi burstON | 24 |
| multi burstOFF | 7 |

Interpretation: the blind judge is non-deterministic, so a portion of these are run-to-run noise.
The structural residual is (a) **resented-source galls** (wojsław/branic — a kindness from a giver who
wronged them earlier; engine-correct, persona-calibration to soften), (b) **cichy's prisoner stance**
(cold to the jailer's soup — intentional, judge-debatable), and (c) scattered single-flags. These set
the next levers (persona-resentment polish, M20.1 burst calibration, Phase B).

<details><summary>Full FLAG list — all 114 run5 failures (scenario : judge reason)</summary>

- `branic_day_burstoff_008` — Declines direct order at 22:14 after three barbs; thin-skinned but recruit refusing sergeant needs scrutiny.
- `branic_day_burstoff_037` — erupts twice then refuses order; recovery to settled feels too quick
- `branic_day_burstoff_045` — Defiant refusal after eruption, then calm within minutes; recovery too fast.
- `branic_day_burstoff_068` — erupts at 20:41 after mocks, then calm at 00:04; burst resolution oddly fast
- `branic_day_burstoff_086` — Halgrim order at 08:42 logged as "lets it pass, no notable reaction"
- `branic_day_burstoff_099` — ignores first order at 06:40 with no prior provocation
- `branic_day_burston_008` — refuses order at 22:14 after barbs; refusal arc plausible but abrupt
- `branic_day_burston_026` — lingering temper at 20:03 and 22:04 despite soup at 19:33
- `branic_day_burston_037` — Erupts twice then refuses an order; escalation steep for one day.
- `branic_day_burston_042` — erupts twice; second fury with no clear fresh provocation
- `branic_day_burston_053` — refuses orders then defies twice late at night; escalation steep with no clear trigger
- `branic_day_burston_078` — snaps at routine order at 16:58 with no prior provocation shown
- `branic_day_burston_086` — order at 08:42 gets "lets it pass" not compliance; odd
- `branic_day_burston_089` — two orders ignored mid-day with "lets it pass"; inconsistent
- `branic_multi_burston_024` — day 1 eruption at calm order with no prior provocation
- `branic_multi_burston_059` — Day 2 "still hasn't shaken off" with no Day 1 eruption
- `branic_multi_burston_066` — three full eruptions in two hours under sustained evening mockery
- `branic_multi_burston_095` — fury then immediate compliance at 21:47-22:18 jarring
- `branic_multi_burston_100` — day 4 saturated with 7+ defiant refusals every hour
- `cichy_day_burstoff_006` — lets mock pass with no reaction; too mild for this captive
- `cichy_day_burstoff_025` — three fury eruptions including 22:04, recovery to settled mid-day jars
- `cichy_day_burstoff_056` — three furious eruptions same evening; soup accepted calmly mid-rage
- `cichy_day_burston_006` — early mock met with no reaction; flat for a resentful captive
- `cichy_day_burston_009` — erupts at 21:21 then looks settled at ease by 22:04; too fast
- `cichy_day_burston_014` — erupts at guard taunt then looks settled at ease 20min later
- `cichy_day_burston_020` — "still hasn't shaken temper" at 20:03 but looks settled at 18:03
- `cichy_day_burston_029` — erupts at full fury at 08:12 with no prior buildup
- `cichy_day_burston_036` — Bristles at mock at 21:55 then looks settled at ease at 22:04.
- `cichy_day_burston_056` — two soups within 36 minutes morning, unusual feeding cadence
- `cichy_day_burston_083` — snaps furiously at 22:38 then sleeps calmly two minutes later
- `cichy_day_burston_089` — erupts in full fury at 06:54, then looks settled at ease by 08:00
- `cichy_multi_burstoff_060` — seven consecutive fury eruptions Day 2 afternoon, no recovery gap
- `cichy_multi_burston_009` — Day 1 outburst at 07:36 with no visible ramp-up or trigger
- `cichy_multi_burston_055` — wakes settled then tense by 06:06 Day 2 with no intervening event
- `cichy_multi_burston_056` — same pattern: wakes settled, tense by 06:06 Day 2 with no trigger
- `cichy_multi_burston_064` — Day 4 "still hasn't shaken off" with no same-day prior spike
- `cichy_multi_burston_068` — Day 5 guard mock "lets it pass, no reaction" contradicts profile
- `edda_day_burstoff_007` — refuses stranger order at 21:45 then complains again at 22:28; escalation without buildup
- `edda_day_burstoff_056` — stranger orders castellan twice; she simply complies, no authority friction
- `edda_day_burston_056` — castellan complies when stranger orders her twice; fits subordinate not commander
- `edda_multi_burston_076` — Day 3 repeated stranger-orders refused in cluster; escalation lacks clear trigger
- `halgrim_day_burstoff_009` — ignores Edda's order at 22:08 with no notable reaction
- `halgrim_day_burstoff_013` — curtness spills onto Edda after Wojsław provocation; borderline for iron self-control
- `halgrim_day_burstoff_015` — mutters complaint at Edda's late order; minor but notable for Halgrim
- `halgrim_day_burstoff_024` — ignores Edda's first order; odd for a disciplined sergeant
- `halgrim_day_burstoff_027` — mutters complaint at Edda's late order; mild but notable
- `halgrim_day_burstoff_030` — ignores Edda's orders twice with "no notable reaction"
- `halgrim_day_burstoff_046` — Edda order at 21:41 met with "lets it pass"; unusual for normally compliant Halgrim
- `halgrim_day_burstoff_076` — Tense at 14:02 after warmth and rest, no clear trigger.
- `halgrim_day_burston_009` — ignores Edda's order at 22:08; he respects and obeys her
- `halgrim_day_burston_010` — ignores Edda's order at 10:01; incongruent with his respect for her
- `halgrim_day_burston_013` — cold contempt toward Edda twice; excessive given genuine respect
- `halgrim_day_burston_027` — complains at Edda order (21:09); Halgrim buttons down, rarely complains
- `halgrim_day_burston_036` — grumbles at second Wojsław order; grumbling sits low for Halgrim
- `halgrim_day_burston_076` — tension at 14:02 unexplained after positive Marta stretch
- `halgrim_day_burston_079` — tense after rest with no preceding provocation that day
- `halgrim_day_burston_087` — snaps at Edda with contempt after Wojsław pile-on; displaces onto wrong target
- `halgrim_day_burston_090` — cold contempt at Edda after Wojsław provocation; displaces onto respected superior
- `halgrim_multi_burstoff_040` — mutter followed immediately by "still seething" mismatched intensity
- `halgrim_multi_burstoff_047` — "seething" label jars for man famous for going cold not hot
- `halgrim_multi_burston_007` — cold contempt directed at respected Edda, Day 1 22:46 burst spillover
- `halgrim_multi_burston_010` — contempt at Edda repeated across days 3-5, too frequent for man who respects her
- `halgrim_multi_burston_015` — contempt at Edda order (Day 5 14:16) jars with his respect for her
- `halgrim_multi_burston_060` — Day 2 "still seething" at 12:07 after calm wake, no new trigger
- `lutek_day_burston_006` — "still seething, jaw tight" after one barb; too harsh for thick-skinned Lutek
- `lutek_day_burston_021` — snaps at stranger at 19:35 then cold to kindness at 22:48; thick-skinned man shouldn't hold grudge this long
- `lutek_day_burston_027` — residual temper at 22:04 with no visible provocation; Lutek is thick-skinned and doesn't nurse grudges
- `lutek_day_burston_040` — sleeps at 00:08 Day 2 after being settled at 00:04; very late
- `lutek_day_burston_054` — answers curtly after two quick mocks; slight friction for thick-skinned Lutek
- `lutek_day_burston_055` — unexplained tension at 18:03 with no preceding provocation visible
- `lutek_day_burston_057` — tension appears at 18:03 and persists to 20:03 with no trigger shown
- `lutek_day_burston_058` — tension builds through evening with no visible cause; accumulates oddly
- `lutek_day_burston_059` — tension at 18:03 and 22:04 with no provoking event between
- `lutek_day_burston_060` — seething at 20:03 after insult he let pass at 19:43; disproportionate
- `lutek_day_burston_068` — lingers tense at 22:04 with no clear prior provocation visible
- `lutek_day_burston_070` — residual temper at 22:04 after only a mild mock, no escalation shown
- `lutek_day_burston_089` — tense at 18:00 answers curtly; temper lingers despite kindnesses
- `lutek_multi_burstoff_014` — answers curtly to public mock; thick-skinned Lutek wouldn't snap
- `lutek_multi_burstoff_026` — curt reply to mockery when tense; contradicts thick-skinned profile
- `lutek_multi_burstoff_039` — curt reply to public mock contradicts thick-skinned profile
- `lutek_multi_burston_003` — seething after mockery contradicts thick-skinned profile
- `lutek_multi_burston_004` — seething after kindness; profile says mockery rolls off him
- `lutek_multi_burston_014` — "still seething, jaw tight" after mock jars with thick-skinned profile
- `lutek_multi_burston_017` — answers mock "curtly and coldly" contradicts thick-skinned profile
- `lutek_multi_burston_025` — "still seething" after mild mockery; too intense for thick-skinned Lutek
- `lutek_multi_burston_026` — "curtly and coldly" twice; sharper than profile allows for insults
- `lutek_multi_burston_039` — answers mock curtly and coldly; profile says mockery rolls off
- `welf_day_burston_098` — tense from 18:00 onward with no clear trigger, sleeps past midnight
- `welf_multi_burston_019` — "earlier temper" lingers day 3 night with no visible trigger
- `wojslaw_day_burstoff_008` — barbed mock at 07:58 draws no reaction; too mild for Wojslaw
- `wojslaw_day_burstoff_016` — complains at kindnesses (15:24, 15:28); proud man grumbling at help jars
- `wojslaw_day_burstoff_025` — lets public mockery pass at 08:52, then erupts later without new trigger
- `wojslaw_day_burstoff_035` — erupts three times in evening including at 22:12 just before sleep
- `wojslaw_day_burstoff_037` — lets three separate mocks pass with no reaction, too passive for profile
- `wojslaw_day_burstoff_042` — lets public mockery pass at 20:55 after calm evening; too mild
- `wojslaw_day_burstoff_046` — lets barbed remark pass at 10:11 and again at 17:48 while settled
- `wojslaw_day_burstoff_048` — lets public mockery pass at 21:13 after a warm Marta-heavy evening
- `wojslaw_day_burstoff_066` — lets first public mockery pass entirely, too lenient for Wojsław
- `wojslaw_day_burstoff_084` — ignores early mock then erupts later with no clear trigger escalation
- `wojslaw_day_burstoff_098` — mocks him at 22:50 just before sleep; erupts then sleeps immediately, jarring close
- `wojslaw_day_burston_008` — lets early public mockery pass with no reaction; jarring for Wojsław
- `wojslaw_day_burston_016` — mutters complaints at kindnesses (15:24, 15:28); prickly man but odd reaction
- `wojslaw_day_burston_021` — erupts at 11:59, settled at 12:01 one minute later
- `wojslaw_day_burston_026` — erupts at 21:47, settled at 22:04, erupts again at 22:32
- `wojslaw_day_burston_035` — three separate fury eruptions same evening; saturation strains belief
- `wojslaw_day_burston_037` — lets three mocks pass without reaction; too placid for Wojslaw
- `wojslaw_day_burston_042` — proud man lets public mockery pass twice without reaction
- `wojslaw_day_burston_046` — mocks ignored twice, prickly man too placid under insults
- `wojslaw_day_burston_048` — erupts at midday mock, then ignores late-night mock when still tense
- `wojslaw_day_burston_052` — erupts at late-night barb after calm well-fed evening; jarring spike
- `wojslaw_day_burston_060` — erupts at 22:54 then sleeps settled at 23:02; too fast reset
- `wojslaw_day_burston_099` — unusually warm all day; barely any irritability for this man
- `wojslaw_multi_burstoff_097` — Day 3 12:07 erupts in fury at stranger offering kindness
- `wojslaw_multi_burston_017` — Day 3 18:05 mutters complaint at a kindness, jarring

</details>

### 7b. Unit / determinism tests — **307 collected (303 passed, 4 skipped), all green**

Deterministic suite run at every step (golden byte-identical for the expression + default-off M3 changes).

| test module | tests |
|---|---|
| `tests/test_acceptance_matrix.py` | 23 |
| `tests/test_authority.py` | 8 |
| `tests/test_behavioral_dynamics_validation.py` | 17 |
| `tests/test_believable_timescale.py` | 5 |
| `tests/test_burst.py` | 31 |
| `tests/test_burst_calibration.py` | 18 |
| `tests/test_burst_world.py` | 4 |
| `tests/test_calibration.py` | 8 |
| `tests/test_diagnostics.py` | 1 |
| `tests/test_expectations.py` | 11 |
| `tests/test_filters.py` | 10 |
| `tests/test_game_facing_longrun.py` | 10 |
| `tests/test_game_facing_memory.py` | 15 |
| `tests/test_game_facing_social_streams.py` | 20 |
| `tests/test_loss.py` | 12 |
| `tests/test_metrics.py` | 7 |
| `tests/test_narration_expression.py` | 10 |
| `tests/test_night.py` | 6 |
| `tests/test_order_invariance.py` | 1 |
| `tests/test_proactive_path.py` | 11 |
| `tests/test_resolution_factor.py` | 5 |
| `tests/test_social_event_mapper.py` | 36 |
| `tests/test_stability.py` | 2 |
| `tests/test_target_policy.py` | 4 |
| `tests/test_tick_golden.py` | 27 |
| `tests/test_time_scale.py` | 3 |
| `tests/test_weather_channel.py` | 2 |
| **total** | **307** |

