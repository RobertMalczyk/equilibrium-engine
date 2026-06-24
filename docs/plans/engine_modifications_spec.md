# Engine modifications — spec, impact, risk, interactions

> Status: **DESIGN ONLY — no code.** Branch `blind-judge-sonnet-baseline`. Derives the concrete changes
> from the verified triage (`docs/eval/fail_triage_playbook.md`, `believability_improvement_plan.md`,
> `eval/hourly_runs/TRIAGE.md`). Each item names its target member, mechanism (described, not coded),
> the flags it addresses, and its **impact / risk / mitigation**; §M9 analyses how they interact.

## 0. Standing constraints (apply to every modification)

- **Config-gated, neutral default.** Any new dynamics edge/gate ships with a config parameter whose
  **default = identity/0**, so `defaults.yaml` and every **golden trace stay byte-identical** until a
  value is set by calibration. No numeric literal in engine code.
- **Spec-first.** Topology changes update `spec_v1.md` + the relevant `docs/diagrams/*.md` **before**
  code, in the same change.
- **Expression never mutates state.** `render_narration` changes (M1, M2) cannot affect the
  `DebugTrace`/dynamics — they are not gated and need no neutral default, but they also cannot fix a
  dynamics defect.
- **Determinism + stability.** New feedback edges must keep the linearized loop poles inside the unit
  circle; verify on the stability test. Constants come from the calibration harness, never hand-set.
- **Litmus held.** Persona-contrast must survive every change (two personas still play differently).

Layers (per the playbook): **L4** = expression (render only), **L2/L3** = dynamics (topology or
calibration), **L3** = calibration only.

---

## M1 — `mood_phrase` must weigh residual anger (L4, expression)

- **Target:** `engine/render_narration.py :: mood_phrase` (read-only consumer of state).
- **Mechanism:** the mood line currently keys on `stress` (+ boredom/frustration) and **ignores
  `anger`**, so a low-stress/high-anger state right after an `outburst` prints "settled at ease". Add
  anger to the bearing read: a high-`anger` state reads tense/seething regardless of low stress;
  define the anger band thresholds as render constants (expression-side, not engine config).
- **Flags addressed:** the whole "settles too fast / settled↔fury contradiction" group (verified:
  `wojslaw_day_burstoff_073` — anger stayed high, only stress was low).
- **Impact:** narration only; the *visible bearing* now matches anger. No state/action change.
- **Risk:** **low.** Golden traces are `DebugTrace` (state/action), not narration text → **unaffected**.
  Only risk: over-reporting tension if the anger band is too low → narration reads angry when calm.
- **Mitigation:** choose the anger band from the data (anger after decay vs at peak); add a narration
  unit check (high-anger ⇒ not "settled at ease"); keep stress/boredom/frustration logic intact.

## M2 — acknowledge a positive event even when the action is `rest`/`busy` (L4, expression)

- **Target:** `engine/render_narration.py` reaction-phrase / event-line selection.
- **Mechanism:** when a `food_given`/`help` event coincides with the NPC being in `rest`/`self_activity`
  (no `positive_response` action that tick), the line currently falls back to the mockery-style "lets
  it pass / no notable reaction". Add a branch: a *positive* event with no hostile reaction renders a
  mild acknowledgement ("takes it without fuss / a nod of thanks"), never the slight-style phrase.
- **Flags addressed:** the ~40 "soup/kindness rendered as 'lets it pass'/'no reaction'" mislabels
  (verified: `welf_multi_burstoff_015` — action was `positive_response`/`rest`, state fine).
- **Impact:** narration only.
- **Risk:** **low.** No dynamics. Risk: masking a *genuine* missing-warmth dynamics case (if the engine
  truly should have emitted warmth and didn't).
- **Mitigation:** scope the new phrasing to events where the trace shows **no negative deposit** (state
  confirms it's benign); if a persona *should* warm up but doesn't, that's a separate L3 item (M7/M8),
  not hidden by the label.

## M3 — burst displaced-discharge: source-valence gate (L2/L3, dynamics — fold into M20.1)

- **Target:** the burst displaced-discharge gate in the selector / target-policy (`action_selector`,
  spec §8 burst; the M20.1 overlay).
- **Mechanism:** while the burst latch is SET and `anger ≥ theta_displace`, the reactive gate currently
  opens to **any** sourced event, so a *kind* act (food/help) becomes a discharge target. Add a
  **valence condition**: the displaced gate does not open toward a **positive-valence** event/source
  (a kindness is not a discharge target); only neutral/negative sources qualify. Valence read from the
  event type / the affinity-field or relation sign — config-gated.
- **Flags addressed:** "erupts/cold at a kindness while latched" (verified: `branic_day_burston_025` —
  anger 0.80 then `help` → `outburst`).
- **Impact:** **burst-ON path only.** Fewer eruptions at kind acts; bounded-vent behaviour otherwise
  unchanged. Burst-OFF entirely unaffected.
- **Risk:** **medium.** Touches the burst latch/gate that is itself mid-calibration (M20.1). Could
  over-suppress a legitimate discharge if "positive" is read too broadly; interacts with the latch
  (M9). Determinism safe (gate is deterministic).
- **Mitigation:** ship as part of M20.1 (one coherent burst change, not a parallel edge); default = the
  current behaviour until the valence gate is enabled; re-run the **boundedness gate** + the displaced-
  aggression acceptance scenarios; verify the vent still fires on a genuine ≥3-loop coincidence.

## M4 — relational respect gates hostility expression + compliance (L2/L3, dynamics — likely topology)

- **Target:** the expression/selection path for hostile actions and command compliance
  (`action_selector` potentials + possibly a new `respect→expression` damper edge; spec §5/§8/§14).
- **Mechanism (two coupled effects, one relational axis):**
  - **Hostility damper:** expressed hostility toward a source scales **down** with `respect[source]`
    (high respect ⇒ a respected superior gets curtness at most, not cold contempt). Today hostility
    "spills" onto a respected source unmodulated.
  - **Compliance lift:** a `command` from a high-`respect` + `has_authority` source raises the
    `cooperate` potential over a mild irritation (he obeys the one he respects).
  - Both via a single declared relational modulator (a `relation_source` factor on the relevant
    potentials), config-gated; **diagnose first** whether the edge is missing (topology) or present but
    too weak (calibration).
- **Flags addressed:** the ~18 "cold/contempt/ignored-order toward a RESPECTED source" (halgrim↔Edda).
- **Impact:** changes how hostility/compliance render toward respected sources across day + multi,
  burst on/off. Largest *real* behavioural cluster.
- **Risk:** **medium–high.** It is a new modulating edge on the action layer → affects selection
  broadly; could **flatten persona-contrast** (over-damping makes everyone deferential) or mute a
  legitimately-earned grievance; persona-contrast + the authority/Edda story tests are sensitive here.
- **Mitigation:** neutral default (modulator k=0 ⇒ bit-identical); calibrate against **contrast gates**
  (min-margin, not weighted sum) so a hot persona stays hot toward a non-respected source; keep the
  standing-grievance floor (a betrayed respect can still curdle); add persona-contrast assertions for
  respected-vs-stranger source.

## M5 — high-authority persona vs a no-authority stranger command (L2/L3, target-policy)

- **Target:** command-compliance in `action_selector` (the `command_pressure` term).
- **Mechanism:** a `command` from a source **without** authority should not compel a **high-authority**
  persona (a castellan doesn't obey a stranger). Make the compliance pressure scale with
  `context.has_authority` **and** the persona's own authority/standing — a no-authority order from a
  stranger yields refusal/ignore as the *correct* behaviour, not compliance.
- **Flags addressed:** the 6 "high-authority persona COMPLIES with a stranger order" (edda).
- **Impact:** edda-like authority personas; narrow.
- **Risk:** **low–medium.** Same compliance term as M4's compliance-lift → must be **one** model (M9),
  not two gates. Risk of edda refusing *legitimate* authority if the authority read is wrong.
- **Mitigation:** unify with M4 into a single `command_compliance = f(has_authority, respect[source],
  own_authority)` term; neutral default reproduces current; test both "stranger→refuse" and
  "legitimate authority→comply".

## M6 — sleep-onset / late-pacing calibration (L3, calibration)

- **Target:** the believable-timescale sleep layer (`eval/calibrated.py timescale_overrides`:
  `sleep_pressure` rise, night-onset; possibly the seek/rest cadence keeping them awake).
- **Mechanism:** re-fit so a settled persona reaches sleep at a believable hour (no "working past
  23:30 / sleeping past 00:30"). Pure duration re-fit, not topology.
- **Flags addressed:** ~18 late-sleep flags (welf, branic).
- **Impact:** shifts sleep timing across the believable-day corpus; multi-day night reset.
- **Risk:** **medium.** Sleep timing feeds the night temper-reset; mis-fit could break the
  "wakes recovered" property or shorten the waking day. Only affects the eval/timescale path
  (`time_scale≠1`), not the base golden.
- **Mitigation:** re-fit via the timescale keeper against the duration ground-truth; re-run the
  multi-day sanity gate (sleeps / night_reset / recovers checks); base golden untouched.

## M7 — thick-skinned persona over-reply to mockery (L3, calibration)

- **Target:** the `insult→anger` gain **modulator** keyed on the relevant trait (`gain_modulators`).
- **Mechanism:** for high thick-skin / low-reactivity, lower the insult→anger deposit (or raise the
  reactive threshold) so a mild mock stays sub-threshold and is shrugged off.
- **Flags addressed:** the 5 "thick-skinned persona gives a cold/curt reply" (lutek) — **after** M1/M2
  confirm it is not just a label.
- **Impact:** lutek-like personas react less to mockery.
- **Risk:** **medium.** Same `insult→anger` modulator curve as M8 (opposite direction) → must be
  **jointly** calibrated (M9), or they fight; over-damping could make lutek inert (a contrast loss the
  other way).
- **Mitigation:** calibrate the trait→gain curve as one fit across personas; contrast gates keep a hot
  persona reactive; confirm the flagged cases are dynamics (trace shows a real cold action), not M2
  label.

## M8 — persona-contrast too weak (too mild for profile) (L3, calibration)

- **Target:** same `insult→anger` / negativity gains + per-persona trait presets.
- **Mechanism:** wojslaw (proud/ungrateful) reads "near-saintly / too mild" — raise his reactivity /
  reduce his warmth uptake so the profile shows. Calibration of the trait preset, not topology.
- **Flags addressed:** the 3 "too mild / sustained warmth inconsistent with profile" (wojslaw).
- **Impact:** sharpens the hot end of the contrast.
- **Risk:** **medium.** Opposite pull to M7 on the **same** modulator → joint fit required; over-doing
  it re-introduces the "snaps at everything" failure.
- **Mitigation:** one joint trait→gain calibration (M7+M8); contrast gates as the objective; re-judge.

---

## M9 — Interaction analysis (do the modifications affect each other?)

**Grouped by shared surface — the couplings that must be designed together, not in isolation:**

1. **Single compliance model: M4 ⊕ M5.** Both modify command compliance. M4 *raises* it for
   respected/authoritative sources; M5 *lowers* it for no-authority strangers. These are the **same
   term** viewed from two ends → implement as ONE
   `command_compliance = f(has_authority, respect[source], own_authority)`, not two competing gates, or
   they will double-count/contradict. **Dependency: design M4 and M5 jointly.**

2. **Hostility gating overlap: M3 ⊕ M4.** A discharge target that is *both* a kind act **and** a
   respected source (e.g. Edda/Marta bringing soup) is suppressed by *both* the valence gate (M3) and
   the respect damper (M4) → risk of **double-suppression** (over-flat, no reaction at all). Define
   precedence/composition: M3 keys on **event valence**, M4 on **source respect**; they should combine
   to "at most a mild/curt response", not cancel a needed reaction elsewhere. **Test the joint case.**

3. **One trait→gain curve: M7 ⊕ M8 (opposite directions).** M7 lowers insult→anger for thick-skinned
   lutek; M8 raises it for proud wojslaw. Same `gain_modulators` curve → **must be a single joint
   calibration**, never two independent hand-tweaks, or each undoes the other at the margins.

4. **Upstream→downstream: M7/M8 → M3.** Changing how much anger an insult deposits (M7/M8) changes how
   often the burst latch arms and thus how often M3's displaced gate is even reached. **Re-fit/re-check
   M3 (and the M20.1 boundedness gate) AFTER the anger-deposit calibration settles**, not before.

5. **Sequencing: expression (M1, M2) FIRST.** They are cheap, dynamics-free, and they remove the L4
   mislabels that currently *masquerade* as dynamics flags. Doing them first (a) clears ~45 flags
   without engine risk and (b) makes the residual dynamics flags trustworthy, so M3/M4 are calibrated
   against real defects, not label noise. M1↔M2 themselves barely interact (different lines), but when
   anger is high *and* a kindness lands, the lines must compose coherently ("takes it, still tense").

6. **Mostly independent: M6.** Sleep-onset pacing shares no term with the others; only loose coupling
   is that M1 (now showing anger) may make a late-evening tense state read worse — but that's a label,
   not a dynamics interaction.

7. **Cross-cutting risk — contrast vs damping.** M4 (respect damper) and M7 (thick-skin damper) both
   *reduce* reactions; M8 *increases* one. The net must preserve the **litmus** (personas differ).
   Calibrate all damping/contrast mods against the **same persona-contrast gate set**, with min-margin
   objectives, so the suppressors and the sharpener are balanced as a system.

**Dependency graph (design/calibrate in this order):**
```
M1, M2  (expression, independent, FIRST)
   └─► re-run judge → trust residual flags
M4 ⊕ M5 (one compliance+respect model)        M7 ⊕ M8 (one trait→gain curve)
                         └──────────► M3 (burst valence gate; after anger deposits settle, with M20.1)
M6 (sleep) — independent, any time
```

## 10. Per-modification Definition of Done

- Topology/dynamics (M3, M4, M5): spec + diagram updated first; new param **defaults to identity →
  golden byte-identical**; stability test passes (poles in unit circle); persona-contrast gates hold;
  the targeted flag cluster shrinks on a re-judge (judge model held constant).
- Calibration (M6, M7, M8): re-fit via the harness (not by hand); the relevant sanity/contrast gate
  passes; golden re-baselined **only** as a conscious, documented step.
- Expression (M1, M2): narration unit checks; **golden unaffected** (no state change); the L4 clusters
  shrink on re-judge.
- Every change lands via PR (branch-protected `main`); **never self-merge**; a finer-`dt` operating
  point is validated separately.
