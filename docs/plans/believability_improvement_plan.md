# Believability improvement plan — analysis of the all-Sonnet 2800 baseline

> Status: **ANALYSIS / PLAN ONLY — no code.** Inputs: the all-Sonnet blind judge of the full corpus
> (2,800 = 700 day + 700 multi × burst OFF/ON), `eval/hourly_runs/` (`results/` = this run;
> `FINAL_report.md` = aggregate). The dt merge is verified inert (engine output byte-identical, 0/2800
> diff — see the dt-merge verification finding), so these flags are about the engine's *believability*,
> not the dt work.

## 1. Baseline (all-Sonnet judge — model held constant)

- **Overall: 2618/2800 PASS (93.5%), 182 FLAG.**
- Flags are **uniform across cohorts** (day-OFF 7.1%, day-ON 6.4%, multi-OFF 5.6%, multi-ON 6.9%) →
  no single cohort dominates; this is broad, not a localized break.
- Per persona (flags): **lutek 41, halgrim 34, branic 29, welf 26, cichy 19, edda 18, wojslaw 15.**

> Note: Sonnet is a stricter judge than the earlier mostly-Opus run (97.6%). Some flags are
> judge-marginal ("plausible but warrants a check"). **Confirm the real defects before chasing them**
> (see R7) — the actionable set is smaller than 182.

## 2. Failure taxonomy (note-clustered; a flag may hit >1 theme)

| # | theme | ~count | nature |
|---|-------|-------|--------|
| T1 | hostility/contempt toward a **respected** source, or **ignoring a respected authority's order** (halgrim↔Edda) | ~large slice of "displaced" + halgrim | engine (relational gating) |
| T2 | **erupts/cold at a kindness/soup with no provocation** (burst-ON displaced discharge) | within the 94 "displaced/kindness" bucket | engine (burst) |
| T3 | **thick-skinned persona gives a cold/curt reply to mockery** it should shrug (lutek) | part of 44 "under/over" + lutek | engine (trait gating) |
| T4 | **under-reaction / "no reaction" where some response is expected** | 44 | engine + expression |
| T5 | **tone / labeling glitch** ("no notable reaction" wrong label, "out of sorts" contradictions) | 38 | expression seam |
| T6 | **pacing**: very late sleep onset ("working past 23:30", "sleeps past 00:00") for settled men (welf/branic) | 27 | calibration (sleep/timescale) |
| T7 | **corpus artifacts**: two soups 10 min apart, back-to-back duplicate refusals ("looks like artifact") | several | scenario generator, NOT engine |
| T8 | burst **recovery cadence** (cichy: "four eruptions, saturation not recovering") | ~6 | engine (burst extinction) |
| — | unclustered | ~35 | needs manual read |

## 3. Root causes + candidate solutions (no code — options to weigh)

**R1 — Relational respect doesn't gate hostility/compliance (biggest real cluster; T1).**
Halgrim repeatedly goes cold/contemptuous toward Edda — *whom his profile respects* — or silently
ignores her orders. Hypotheses & options:
- The anger/contempt expression isn't damped by `respect[source]` for the target; hostility "spills"
  onto a respected source. Option: a relational gate so expressed hostility toward a source scales
  *down* with `respect[source]` (target-policy already has a bystander filter — extend with a
  respected-source damper).
- Compliance with a high-authority, high-respect order should win over a mild irritation. Option:
  raise the command-compliance potential when `has_authority ∧ respect[source]` is high.
- Decide whether this is **topology** (a missing respect→expression edge) or **calibration** (edge
  exists, gain too weak). Diagnose first with `explain()`/trace on 2–3 flagged halgrim records.

**R2 — Burst displaced discharge fires on positive/neutral acts (T2; the known M20.1 target).**
Erupting/cold at a kind gesture or soup with no provocation. Options:
- Gate the displaced-discharge by **source valence**: do not open the reactive gate toward a
  *positive/kind* source (a kindness shouldn't be a discharge target), only neutral/negative ones.
- Raise `theta_displace` so only a genuinely high-arousal latch displaces.
- This is exactly the displaced-aggression calibration already flagged; fold these records into the
  M20.1 target set.

**R3 — Thick-skinned / low-reactivity persona over-replies to mockery (T3; lutek).**
Lutek (high thick-skin) produces a cold/curt reply where he should shrug. Options:
- Strengthen the trait modulator on the `insult→anger` gain for high thick-skin (lower deposit), or
  raise the reactive threshold for low-reactivity personas so a mild mock stays sub-threshold.
- Verify it's not just the *label* (see R5) before retuning gains.

**R4 — Sleep-onset pacing too late (T6; welf, branic).**
Settled men still working past 23:30 / sleeping after midnight. Options:
- Re-fit `sleep_pressure` rise / night-onset in the believable-timescale layer so a calm persona
  reaches sleep at a believable hour; check the `seek/rest` cadence isn't holding them awake.
- Pure calibration (durations), not topology.

**R5 — Expression/labeling glitches (T4/T5; cheapest wins, no engine-dynamics change).**
"no notable reaction" wrong label; "settled at ease" vs "out of sorts" contradictions; curt phrasing.
These live in the **expression seam** (`render_narration`), not the dynamics. Options: fix the
reaction-phrase selection + mood-phrase consistency so the *narration* matches the state. High value,
low risk — and some "under-reaction" flags are really mislabels, so do this *before* retuning R3.

**R6 — Corpus authoring artifacts (T7; not the engine).**
Near-simultaneous duplicate events (two soups 10 min apart, back-to-back refusals). Option: dedup /
min-spacing in the scenario generator so the judge isn't reacting to input artifacts.

**R7 — Judge methodology: confirm before chasing (do FIRST).**
Many flags are judge-marginal. Option: re-judge the 182 flagged records with an **adversarial
2-of-3 Sonnet vote** (a record is a real defect only if a majority of fresh judges flag it). This
separates true defects from single-judge noise and yields the actionable set (likely well under 182).
Keep the **judge model constant** (all-Sonnet) for every future A/B — a model swap alone moved the
aggregate ~4pp.

## 4. Recommended sequence (cheapest / highest-leverage first)

1. **R7** — confirm-vote the 182 flags → the real defect list (cheap, decides everything else).
2. **R5 + R6** — expression-label fixes + corpus dedup (cheap, removes a chunk of "flags" that aren't
   dynamics defects).
3. **R1** — relational respect gating (largest *real* behavioural cluster; diagnose topology-vs-gain).
4. **R2** — burst displaced-discharge valence gate (fold into M20.1).
5. **R3, R4** — trait-gating + sleep-onset calibration (after R5 confirms they're real, not labels).
6. Re-run the full all-Sonnet judge; compare to this 93.5% baseline (same judge model).

## 5. Guardrails

- Every engine change keeps the golden trace **byte-identical** and goes through the staged
  spec-first / PR flow; behaviour changes are justified as a contrast, tuned by calibration not hand.
- A finer-`dt` operating point (now available via `resolution_factor`) is a separate validation; don't
  conflate it with these believability fixes.
