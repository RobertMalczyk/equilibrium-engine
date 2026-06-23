# Phase C — M3: burst displaced-discharge SOURCE-VALENCE gate

> Status: **PLAN ONLY — no code.** Branch (when started): `m3-burst-valence-gate` off `main`.
> Spec of record: §8 (burst & saturation). Diagram: `docs/diagrams/burst_saturation.md`.
> Folds into M20.1 (`docs/burst_calibration_plan.md`) — M3 is the **topology** change; M20.1 calibrates
> the magnitudes. Derives from the believability re-judge (`eval/phaseA_run2/REPORT.md`).

## 0. Why now (evidence)
The Phase-A refined-M1 re-judge (2662/2800, 95.1%, judge held constant) left **88 residual regressions
vs baseline; 64/88 are burst-ON and 48/88 are kindness/displacement-themed** ("bristles/snaps at soup",
"anger-displacement overdone"). That is the single dominant remaining believability defect, and it is
exactly the M3 target. Phase A surfaced it honestly (it was masked before by the mood/kindness mislabels).

## 1. The assumption being overturned (state it plainly)
The current burst gate (decided **2026-06-12**, `engine/simulation.py:319-326`) **deliberately suppresses
kindness above the displacement bar**: while `displaced_gate` is open it sets `kindness_pressure = 0.0`
so fury "no longer HEARS the kindness" — *"even someone kind, even at their kindness"* (the "kicking the
dog" intent). The M20.1 success criterion #5 codifies it: *"kindness suppressed above the bar, honoured
below it."*

**M3 revises this:** a discharge onto a **positive-valence source/event** (a kindness — soup, a hand)
reads as unbelievable to the blind judge. The corrected rule: **a kindness is NOT a discharge target.**
Above the bar, displacement still fires onto **neutral/negative** sources (the loaded-spring "kick the
dog" stays), but a genuinely kind act is honoured (warm/neutral reply), never erupted at. This is an
evidence-backed topology correction, not a tuning task — at *every* current weight a kindness above the
bar is suppressed, so calibration cannot reach the believable behaviour (a topology gap, like the
original gate was). Update §8 spec + diagram + M20.1 criterion #5 **before** code.

## 2. Mechanism (described, not coded) — one condition, one place
Today (`engine/simulation.py:313-332`):
```
displaced_gate = burst_latched AND event_source is not None AND anger >= theta_displace
if displaced_gate: kindness_pressure = 0.0        # <-- the suppression M3 gates
reactive_allowed = is_provocation OR kindness_pressure>0 OR recent-provocation OR displaced_gate
```
M3 adds a **positive-valence** predicate and excludes such events from the displaced gate:
```
positive_valence = _event_is_positive(event, eff, snapshot, config)   # NEW, config-gated
displaced_gate = burst_latched AND event_source is not None
                 AND anger >= theta_displace
                 AND not (valence_gate_on AND positive_valence)        # NEW conjunct
```
Consequences, all automatic from the existing wiring:
- Kindness no longer zeroed (`if displaced_gate` is now false for a kind act) ⇒ `kindness_pressure`
  survives ⇒ the signed kindness inhibitory edge vetoes the hostile potentials ⇒ the selector yields
  **warmth/neutral**, not a snap.
- `reactive_allowed` stays true via `kindness_pressure > 0` ⇒ a reply still happens (a warm one).
- The displaced-discharge relational-discount branch (`:423-439`) requires a HOSTILE reply (resentment
  post-effect); with warmth selected it does not fire ⇒ no grudge booked on the kind source.
- A sourceless stressor (rain) still never opens the gate (unchanged). A neutral/negative source above
  the bar still discharges (unchanged) — only the positive case is carved out.

## 3. What "positive valence" means (scope the predicate)
Two signals, in increasing richness — **ship slice (A) first**:
- **(A) Event-type valence (the flagged cases):** `food_given`, `help` are positive; `insult` negative;
  `command`/neutral are neutral. Mirrors the expression-side `POSITIVE_EVENTS`. Handles every flagged
  "snaps at soup" case. Read from the event semantics already available in `eff`/`event`.
- **(B) Source valence (stage-2 extension):** the **affinity-field / relation sign** of the source — a
  discharge onto a *beloved* person even on a neutral event is also unbelievable. Compose as: positive
  if event-positive **or** `relation[source]`/affinity clearly positive. Defer (B) to a second slice;
  note it in the spec as the extension, do not build ahead of need.

Config: a single flag `burst.displace_valence_gate` (or `appraisal.displace_valence_block`) — **default
OFF ⇒ every existing trace (burst-off golden AND burst-on eval) is byte-identical** until enabled. No
numeric literal in engine; the valence thresholds for (B) come from calibration.

## 4. Interactions (M9 — do not fix in isolation)
- **M3 ⊕ M4 (double-suppression) — FUTURE.** M4 (respect damper, Phase B, not yet built) also damps
  hostility toward a respected source. A kind act from a respected source (Edda/Marta soup) would hit
  *both* gates ⇒ risk of stone-flat silence. M3 alone is safe now (M4 absent). **When M4 lands**, compose
  to "at most a curt/mild reply", never cancel a needed minimal reaction. Add the joint corner case then.
- **M7/M8 → M3 (upstream) — RE-VALIDATE AFTER PHASE B.** The trait→gain re-fit changes anger deposits ⇒
  how often the latch arms / clears `theta_displace` ⇒ how often M3 is even reached. Since we are doing C
  **before** B, M3's calibration (theta_displace, valence thresholds) must be **re-run through the M20.1
  boundedness gate after Phase B** settles. Flag in the M20.1 plan.
- **Overlap with existing edges (already in `simulation.py`):** spent-fury refractory (`_refractory_pressure`,
  same source while hot) and bystander-respect (`_bystander_pressure`, displaced onto respected bystander)
  are distinct axes; M3 is **source/event valence**. Confirm they compose (a kind act from the provoker
  while hot → refractory AND valence both say "no snap" — consistent).

## 5. Determinism & stability (low risk)
M3 adds a **deterministic boolean conjunct** on the frozen snapshot — **no new state, no new feedback
edge, no new integrator** ⇒ the linearized loop poles are unchanged ⇒ the stability test is unaffected by
construction (unlike a gain edge). Synchronous discipline preserved (reads the frozen snapshot + carried
latch). Order-invariance untouched.

## 6. Tests (deterministic, assert on DebugTrace — never the judge)
Hand-authored YAMLs in `eval/scenarios/believability/` + a golden-style assertion module:
- `latched_then_kindness` — arm the burst via a genuine ≥3-loop coincidence, then a **kind** event from a
  fresh source. Assert: action is **NOT `outburst`/hostile toward the kind source** (warm/neutral); no
  resentment booked on it.
- `latched_then_insult` — same latch, deliver an **insult** ⇒ assert the displaced discharge **still
  fires** (no over-suppression; the "kick the dog" onto a neutral/negative source survives).
- `latched_then_weather` — sourceless ⇒ gate never opens (existing invariant, regression guard).
- `genuine_vent_acceptance` — the vent fires on the earned coincidence and **self-terminates** (latch
  releases below `theta_burst_exit`) — boundedness preserved with the gate on.
- (When (B) lands) `latched_kindness_from_beloved` and (when M4 lands) `latched_kind_from_respected`
  (the double-suppression joint case → "at most curt", not stone-flat).

## 7. Calibration (fold into M20.1)
M3 is topology; the magnitudes (theta_displace operating point, valence thresholds for (B)) calibrate
inside M20.1 under the **boundedness gate** at the measured G6 points, preserving the 1400-scenario blind
baseline (day 698/700, multi 626/630) where burst is off, and the persona-contrast litmus.

## 8. Definition of Done
- §8 spec + `docs/diagrams/burst_saturation.md` + M20.1 criterion #5 updated **first** (the assumption
  overturn is explicit, with the re-judge evidence cited).
- New config flag **defaults to identity ⇒ golden byte-identical**; stability test green; order-invariance
  green.
- Corner-case scenarios pass deterministically; persona-contrast holds.
- On a full all-Sonnet re-judge (judge model held constant, same harness as `eval/phaseA_judge_wave.py`),
  the **kindness/displacement regression cluster (48 in `phaseA_run2`) shrinks** and no other cluster
  regresses.
- Lands via PR on branch-protected `main`; **never self-merge** (open PR, stop).
- After Phase B: re-run the M20.1 boundedness gate (M7/M8 → M3 upstream coupling).

## 9. Sequencing
```
spec §8 + diagram + M20.1 §5  (overturn the "suppress kindness above bar" assumption, cite evidence)
   └─► M3 slice (A): event-type valence conjunct on displaced_gate, config flag default OFF
          └─► corner-case tests (DebugTrace) + golden byte-identical + stability
                 └─► enable in burst-ON eval config → full re-judge → confirm 48-cluster shrinks
   M3 slice (B): source/affinity-sign valence — second PR, optional
   (after Phase B) re-validate boundedness; (with M4) compose the double-suppression joint case
```
```
