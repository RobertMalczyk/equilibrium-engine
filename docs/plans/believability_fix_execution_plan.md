# Believability fixes — execution plan + test-suite enlargement

> Status: **PLAN ONLY — no code.** Branch `blind-judge-sonnet-baseline`. Turns the modification spec
> (`engine_modifications_spec.md`) into a *how-to-solve* sequence, and — the focus here — names every
> **corner case that must be represented by a NEW deterministic test scenario**, so each fix ships with
> regression protection and the interaction risks (spec §M9) are pinned.

## 1. How each modification is solved (steps)

Each lands as its **own PR** (branch-protected `main`, never self-merge), spec/diagram first for any
topology change, config param **defaulting to identity** so the golden stays byte-identical until
calibration sets a value.

- **M1 mood_phrase weighs anger (L4).** Add an anger band to the bearing read in `render_narration`;
  pick the band from the data (anger-at-peak vs anger-after-decay). Steps: define band → update
  `mood_phrase` → narration unit checks → re-judge.
- **M2 acknowledge positive events while busy (L4).** Add a positive-event branch to the reaction-line
  selection: a `food_given`/`help` with no hostile reaction renders a mild acknowledgement, never the
  slight-style phrase. Steps: branch on event valence + no-negative-deposit → phrase → unit checks.
- **M3 burst source-valence gate (L2/L3, in M20.1).** Add a valence condition to the displaced-discharge
  gate (a positive event/source is not a discharge target). Steps: spec §8 + burst diagram → param
  (default = today) → boundedness + acceptance scenarios → re-judge.
- **M4 respect→hostility/compliance (L2/L3).** First **diagnose** topology-vs-gain on flagged
  halgrim↔Edda traces; then a single `relation_source(respect)` modulator that (a) damps expressed
  hostility toward a respected source and (b) lifts compliance with a respected-authority command.
  Steps: diagnose → spec §5/§8/§14 + diagram → param (k=0 default) → contrast gates → re-judge.
- **M5 stranger-command policy (L2/L3).** Fold into ONE compliance model with M4 (see §3.1):
  `command_compliance = f(has_authority, respect[source], own_authority)`. Steps: design the unified
  term with M4 → spec → param → tests.
- **M6 sleep-onset (L3).** Re-fit `sleep_pressure` rise / night-onset in the timescale keeper against
  the duration ground-truth. Steps: re-fit → multi-day sanity gate → re-judge.
- **M7+M8 trait→gain curve (L3).** ONE joint calibration of the `insult→anger` trait modulator across
  personas (lutek down, wojslaw up). Steps: joint fit with contrast-gate objective → re-judge.

## 2. Sequencing (from the interaction analysis)

```
Phase A  M1, M2  (expression; cheap, dynamics-free)  → RE-JUDGE (constant model) → trust residual flags
Phase B  M4 ⊕ M5 (one compliance+respect model)   ‖   M7 ⊕ M8 (one trait→gain curve)
Phase C  M3      (burst valence gate; AFTER anger deposits settle; with M20.1)
Phase -  M6      (sleep; independent, any time)
```
Rationale: A removes the ~45 label flags that masquerade as dynamics; B/C are then calibrated against
*real* defects; M3 depends on the post-B anger-deposit levels.

## 3. Test-suite enlargement — corner cases that NEED a scenario

The random day/multi corpus is good for *aggregate* believability but does **not** reliably hit the
precise corner cases these fixes target, and the blind judge is non-deterministic. So each fix ships
with **hand-authored, deterministic scenarios** (named YAML with explicit event timing, like the
existing `eval/scenarios/*.yaml` goldens and burst-acceptance set) whose assertions read the
**DebugTrace** (state/action/mode), not the LLM judge. Proposed home: `eval/scenarios/believability/`
+ an assertion layer in `tests/` (deterministic, golden-style).

> **Assertion discipline:** assert on the trace (e.g. *action ≠ `outburst` toward a kind source while
> latched*; *action == `cooperate` to a respected-authority command*; *`mode == SLEEP` by tick T*), as
> a contrast/min-margin where personas should differ — never on the judge verdict.

### 3.1 Per-modification corner cases

| guards | scenario (setup → assertion) |
|---|---|
| **M1** | `post_outburst_residual` — provoke an outburst, then a quiet window. Assert: while `anger ≥ band`, the **mood bearing is NOT "settled/at ease"** (and the converse: genuinely calm ⇒ settled). Also `high_stress_low_anger` and `low_stress_low_anger` to lock the band edges. |
| **M2** | `kindness_while_busy` — a `food_given`/`help` timed **during a `rest`/`self_activity` window**. Assert: the line **acknowledges** the kindness (not "lets it pass"); state shows no negative deposit. Companion `kindness_while_idle` (already warm) and `kindness_while_angry` (acknowledges **and** still tense — M1∩M2 composition). |
| **M3** | `latched_then_kindness` — arm the burst via a genuine ≥3-loop coincidence, then deliver a **kind** event from a fresh source. Assert: **no `outburst` toward the kind source.** Paired `latched_then_insult` — same latch, deliver an **insult** → assert **discharge still fires** (no over-suppression). Plus `latched_then_weather` (sourceless never opens — existing invariant) and the genuine-vent acceptance (vent fires + self-terminates). |
| **M4** | `angry_then_respected_command` — raise anger, then a `command` from a **respected authority** (Edda). Assert: action == `cooperate` (or at worst curt), **not** cold contempt / ignore. Contrast twin `angry_then_stranger_command` (low respect) → hostility/refusal **allowed** → assert the **margin** between the two. Plus `respected_source_insult` → respect damps, but `betrayed_respect` (repeated) can still curdle (standing-grievance floor holds). |
| **M5** | Compliance matrix `command_{authority×respect}` — same `command` event from {has_authority∧respected, has_authority∧neutral, no-authority stranger} to a **high-authority** persona (edda) and a **low-status** persona. Assert: stranger→castellan = refuse/ignore; legitimate authority→comply; the single compliance model is monotone in (authority, respect). |
| **M6** | `calm_day_sleep_hour` — an uneventful day. Assert: `mode == SLEEP` reached by a believable hour (no work past ~23:00 / sleep past 00:00). Twin `late_stress_day` — heavy evening stress → sleep legitimately later **but still sleeps and wakes recovered** (multi-day night_reset holds). |
| **M7** | `thickskin_mild_mock` — lutek + a single mild mock. Assert: **shrug** (no hostile/cold action; anger sub-threshold). Twin `thickskin_sustained_mock` — repeated strong mocks → **eventually reacts** (not inert). |
| **M8** | `proud_kindness` — wojslaw + a kindness. Assert: **muted** warmth (not "near-saintly"); contrast twin `warm_kindness` (welf) → full warmth → assert the warmth **margin** wojslaw < welf. `proud_provocation` → hot reaction preserved. |

### 3.2 Cross-cutting corner cases (the §M9 interactions — most important to add)

| risk | scenario → assertion |
|---|---|
| **M3 ⊕ M4 double-suppression** | `latched_kind_from_respected` — latched, then a **kindness from a respected source** (Edda/Marta soup) — *both* gates apply. Assert: **at most a curt/mild response — NOT an eruption AND NOT stone-flat silence** (the two gates must compose, not cancel a needed minimal reaction). This is the single highest-risk joint case. |
| **M4 ⊕ M5 unified compliance** | the §3.1 M5 matrix doubles as the M4 check — one term, monotone in (authority, respect); assert no contradiction (a respected non-authority vs an unrespected authority resolve sensibly). |
| **M7 ⊕ M8 / contrast litmus** | `same_mock_all_personas` and `same_kindness_all_personas` — the **identical** event delivered to all 7 personas, asserting the **ordering + min-margins** (wojslaw/cichy hot, lutek/welf mild, edda composed). This is the existing persona-contrast gate **enlarged** to cover the new respect/valence edges; it is the guardrail that M4/M7 damping and M8 sharpening don't collapse the contrast. |
| **M7/M8 → M3 coupling** | re-run the **burst boundedness gate** after the trait→gain re-fit (changed anger deposits change how often the latch arms) — not a new scenario but a required **re-validation step** gating M3. |

### 3.3 Suite-level additions

- A small **`believability` scenario pack** (the named YAMLs above) + a deterministic assertion test
  module, run in CI alongside the goldens.
- **Enlarge the persona-contrast gate** with the respected-source / kind-source / authority axes
  (§3.2) so contrast is asserted on exactly the edges these fixes touch.
- Keep the **random corpus** as the aggregate believability check (full all-Sonnet re-judge per phase),
  but the *correctness* of each fix is pinned by the deterministic pack above.

## 4. Definition of Done (per phase)

- New dynamics params **default to identity → golden byte-identical**; stability test green (poles in
  unit circle).
- The fix's **corner-case scenarios pass deterministically**; the **enlarged contrast gate** holds
  (personas still differ on the new axes).
- The targeted flag cluster **shrinks** on a full re-judge with the **judge model held constant**
  (all-Sonnet baseline = 93.5%); no other cluster regresses.
- Spec + diagram updated with the code; lands via PR; **never self-merge**.
