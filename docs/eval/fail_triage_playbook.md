# Believability fail-triage playbook — root cause → fix

> A **reusable procedure** for analysing the FLAGs from *any* blind-judge run (current or future):
> for each flagged record, find which layer of the pipeline the fail comes from, then apply the fix
> that belongs to that layer. **Judge-model differences are deliberately out of scope** — always hold
> the judge model constant across a comparison; this doc is about *engine/expression/corpus* causes.

## 0. Principle

A flag is not "the engine is wrong." It is "something in the chain that produced this record looks
off." The chain has five layers, each with its **own** kind of fix. Triage = identify the layer, then
act. The single most important question for every flag is:

> **Was the internal STATE trajectory wrong, or only the NARRATION of it?**

Everything downstream of that fork is different work.

## 1. The five layers a fail can come from

```
 (L1) SCENARIO/CORPUS  →  (L2/L3) ENGINE DYNAMICS  →  (L4) EXPRESSION  →  (L5) JUDGE
   input events          states evolve (topology       state → words      verdict on
   (authored)            = structure, calibration       (render_narration)  the words
                          = constants)
```

| layer | what's wrong | fix lives in | NOT fixed by |
|------|--------------|--------------|--------------|
| **L1 Corpus** | degenerate/duplicated/implausible input events | scenario generator | engine, render |
| **L2 Topology** | a structural edge missing / wrong-signed → wrong at *every* weight | spec + wiring (edge/gate), spec-first | tuning |
| **L3 Calibration** | right structure, wrong magnitude/timing | calibration harness (the one constant) | hand-editing, topology |
| **L4 Expression** | state is correct, the *narration* mislabels/contradicts it | `render_narration` (phrase/mood/label logic) | engine dynamics |
| **L5 Judge** | behaviour is defensible; verdict is marginal/strict | rubric wording / accept | engine, render |

## 2. Per-flag decision procedure

For each flagged `scenario_id`, gather the **evidence** (§3), find the moment the judge's note refers
to, then walk this tree:

```
Q1. Reproduce the run (deterministic) and read the STATE at the flagged moment.
    Is the state trajectory PLAUSIBLE there (right emotion, right relation to the source,
    sane pacing)?

    ├─ NO  → it's a DYNAMICS fail → Q2
    └─ YES → the dynamics are fine → Q3

Q2. (dynamics) Is the wrong behaviour present at EVERY parameter setting — i.e. a QUALITATIVE
    error (reacts to the wrong channel; hostility ignores respect[source]; wrong sign; a missing
    gate)?  [the CLAUDE.md topology test]

    ├─ YES → L2 TOPOLOGY. Add/repair the edge or gate. Update spec + diagram FIRST, then code.
    └─ NO  → right shape, wrong amount/timing → L3 CALIBRATION. Re-fit the specific
             gain/threshold/half-life via the harness (never by hand; contrast from dynamics).

Q3. The state is right. Does the NARRATION faithfully describe that state?

    ├─ NO  → L4 EXPRESSION. Fix the reaction-phrase / mood-phrase / label in render_narration.
    │        (e.g. "no notable reaction" stamped on a real reaction; "settled" + "out of sorts".)
    └─ YES → state right AND narration right → Q4

Q4. Is the INPUT itself degenerate (impossible cadence, duplicated/back-to-back events)?

    ├─ YES → L1 CORPUS. Fix the scenario generator (min-spacing / dedup); not the engine.
    └─ NO  → L5 JUDGE-MARGINAL. The behaviour is defensible. Confirm with a fresh re-read
             (same model); if it doesn't sustain, record as judge-noise / sharpen the rubric.
```

**The fork that matters most is Q1** (state vs narration) and then Q2 (topology vs calibration). Most
mis-spent effort is retuning a gain (L3) for what is actually a label bug (L4) or a structural gap (L2).

## 3. Evidence to capture for every flag (the "diagnostic card")

Triage is only repeatable if each flag is backed by the same evidence. For a `scenario_id`, capture:

- **Input:** the scenario's event timeline (type, source, context, clock time).
- **Trace:** the `DebugTrace` — per tick: `global_state` (anger/stress/…), `mode`, `selection.action`
  + `selection.score`, the firing `potentials`, and **`relations[source]`** (trust/respect/resentment
  toward the event's source) at the flagged tick.
- **`explain()`** for any field/affinity/relation read involved.
- **Profile expectation:** what the persona *should* do here (the disposition the judge is checking).
- **Judge note:** the ≤12-word reason (which moment, what jarred).

A flag without this card is an opinion; a flag with it is diagnosable. (Tooling to build, no code yet:
a *flag-triage harness* that takes `results/*.txt`, and for each FLAG emits this card — trace slice
around the flagged tick + events + profile — so L1–L5 classification is mechanical. This is the
`explain()` → debug-trace plumbing already on the backlog.)

## 4. Root-cause catalogue (signatures seen in practice → action)

Use as a lookup once a flag is classified. Examples are from real runs but the **categories** are what
endure.

| signature in the note / trace | layer | root cause | fix |
|---|---|---|---|
| hostility/contempt/ignored-order toward a source the profile **respects** (e.g. halgrim↔Edda); trace shows high `respect[source]` yet a hostile action | **L2/L3** | expressed hostility / compliance not gated by `respect[source]` | if no respect→expression edge exists → **topology** (add a respected-source damper / authority-compliance gate); if it exists but weak → **calibration** |
| erupts/cold at a **kindness or neutral act** with no provocation (burst latched) | **L2/L3** | displaced discharge not gated by **source valence**; `theta_displace` too low | gate discharge to NOT target a positive source (topology) and/or raise `theta_displace` (calibration) — the M20.1 target |
| a **thick-skinned/low-reactivity** persona gives a cold/curt reply to a mild mock | **L3** (verify not **L4**) | insult→anger deposit too high for that trait, or reactive threshold too low | re-fit the trait modulator / threshold — *after* confirming it isn't just a mislabel |
| settled persona **sleeping very late / still working past midnight** | **L3** | `sleep_pressure` rise / night-onset mis-calibrated in the timescale layer | re-fit the sleep/night durations |
| "**no notable reaction**" on a record where a reaction did happen; "settled at ease" **and** "out of sorts" in one line | **L4** | reaction-phrase / mood-phrase logic mislabels a correct state | fix `render_narration` phrasing; no dynamics change |
| **two same-source events seconds/minutes apart**, "back-to-back refusals looks like an artifact" | **L1** | scenario generator emits degenerate cadence | min-spacing / dedup in the generator |
| note **hedges** ("plausible but warrants a check"); a fresh re-read disagrees | **L5** | judge-marginal | accept / sharpen rubric; not an engine change |

## 5. Aggregating a whole run

1. Build a diagnostic card per FLAG (§3); classify each into L1–L5 + a root-cause tag (§4).
2. **Cluster** by `(layer, root_cause)` and by recurring `(persona, channel, source)` — repetition is
   the signal (one halgrim↔Edda flag is noise; twenty is a structural gap).
3. **Prioritise by leverage, not by count:** cheap layers first (L4 expression, L1 corpus), then L3
   calibration, then L2 topology (most expensive, spec-first). A single L2 edge can clear a whole
   cluster.
4. Record the run's **layer histogram** (how many flags per layer) so progress is comparable run to
   run — *with the judge model held constant*.

## 6. What this is NOT

- Not a judge-model comparison. If two runs used different judges, differences are uninterpretable —
  re-judge the baseline with the same model before reading any delta.
- Not "tune until the number goes up." Each fix is tied to a *layer and a cause*; a believability
  number that rises because a gain was hand-fit to please a judge is a regression in disguise.

> Companion: `docs/plans/believability_improvement_plan.md` applies this playbook to the current
> all-Sonnet baseline (the L1–L5 clusters and a ranked action list).
