# M-J Moral Tension — implementation summary + test plan (scope-expansion)

> Companion to `moral_tension_review.md`. This file fixes (1) the implementation concept and (2) the
> testing strategy, which **replaces the spec's "1400 new moral scenarios" with scope-expansion of the
> existing ~2800 corpus** (user decision, 2026-06-23).

---

## 1. Implementation concept (summary)

The engine stays a deterministic, sampled time-domain integrator. The moral layer adds **state** +
**a read-only ledger** + **edges**, all config-backed, all dormant-by-default.

**A. Moral states** (new integrators, same `decay()` primitive, default-inert):
`guilt, exposure_anxiety, repair_drive, avoidance_drive, rumination, cognitive_load_from_lies,
perceived_injustice`. All ≥30min half-life → **dt unchanged**.

**B. Suspicion** = 4th relation dimension (`trust, respect, resentment, suspicion`), per-source, decays,
reuses `relation_filter`.

**C. MoralLedger** (the genuinely new structure): `Secret` / `LieRecord` records held *beside* the
runtime, **frozen read-only into the snapshot**, **mutated only in `post_effects`**, and whose sole
engine effect is to **emit cues as events** (→ mapper → channels). Never writes `global_state` directly →
"state mutates in one place" preserved. Per-secret `salience/exposure_risk/unresolvedness` are mini
integrators using the same decay helper.

**D. Actions** enter `POTENTIAL_NAMES`: `lie, deflect, blame_other, confess, confide, apologize, repair,
remain_silent, avoid` — declarative terms + weights + thresholds; **deterministic potentials, not
sigmoid probabilities**; outburst still gated only by the existing burst latch.

**E. Couplings** (all config, default 0 → goldens byte-identical): guilt→stress(+)/anger(−, empathy),
guilt→repair_drive, rumination→stress/fatigue, cognitive_load→fatigue, exposure_anxiety→stress,
secret.salience→stress(anxious)/boredom(−, curious), lie-detected→target anger/resentment/−trust.

**F. Traits**: reuse the existing 10 where semantics match; add only the genuinely-new
(honesty_humility, guilt_proneness, machiavellianism, shame_sensitivity, lie_skill, gossip_tendency,
injustice_sensitivity, conflict_avoidance). Relation modifiers (closeness/source_threat/authority_gradient/…) are
**authored relation config that modulates gains**, not new states.

**Build order** (vertical slices, each with its own `docs/diagrams/*.md`): M-J.0 guilt core → M-J.1 lie
loop → M-J.2 repair/confide → M-J.3 accusation/suspicion (needs **M-MEM** multi-event mapper for
witness fan-out) → M-J.4 full ledger + calibration grid.

---

## 2. Testing — expand scope of the 2800, do NOT add 1400 files

**Decision:** the moral layer is tested by **broadening what the existing corpus exercises and asserts**,
not by generating a separate moral-only world. Rationale: a moral-only corpus tests moral mechanics in a
vacuum (the "dead-system / always-confess" failure modes hide there); folding moral threads into real
mixed days tests them where they must actually coexist with hunger/fatigue/anger.

### 2.1 What "expand scope" means concretely — three moves, not more files

1. **Keep the existing ~2800 byte-identical as the dormant-layer regression baseline.** With the moral
   layer present but all moral gains = 0, every existing day/multiday golden must hash-identical. This is
   the first and most important moral test: *proof the layer is inert until wired.* (cf.
   verify-engine-change-deterministically.)

2. **Add a `moral` variant axis** — exactly like the existing `burst-{on,off}` axis. The SAME personas,
   seeds, and day structures are reused; a deterministic **moral overlay** injects a secret/lie/accusation
   thread into a scenario's existing event schedule (seeded from the same `_seed_for` scheme, new moral
   verbs spread across the day). Corpus *count* stays ~2800 base; the matrix gains a moral-on slice judged
   by the expanded invariant set. **Scope grows, file-count does not explode into 1400 unrelated cases.**

3. **Expand the invariant/sanity checkers, not the case list.** `sanity_multiday.py` and the blind-judge
   prompt gain moral invariants (below). One scenario now asserts 7→N properties instead of one scenario
   per property.

### 2.2 New event vocabulary (extends the 4-verb catalog deterministically)
`secret_cued, lie_created, lie_reinforced, lie_detected, secret_exposed, confession, confiding, apology,
reparation, accusation, false_accusation, suspicion_raised, direct_question, deflection, blame_shift,
remain_silent` — each maps to channels in the mapper; existing scenarios that don't use them are
unaffected.

### 2.3 Moral invariants folded into the judge/sanity gates
(asserted *within* existing scenarios that carry a moral overlay, not as standalone files)
- high guilt_proneness confesses earlier than low, all else equal (persona contrast)
- high machiavellianism → more lies, lower guilt
- close target → more guilt + more trust damage on detected lie
- white_lie < antisocial_lie guilt
- safe confiding lowers rumination; gossip-prone confiding raises exposure_risk
- detected lie → target anger + resentment + trust drop
- false accusation → accused anger/resentment/perceived_injustice; discovery → accuser guilt + trust loss
- active secret: stress↑ for anxious persona, boredom↓ for gossip-prone (the litmus split)
- serious guilt survives the night reset; relation damage persists across days
- **no degenerate loop**: never always-confess / always-lie / always-outburst; outburst needs
  accumulated pressure, never guilt alone

### 2.4 Calibration
Reuse the existing burst-style overlay + blind-judge regression harness. The moral half-life/gain grid is
scored with the spec's weighted score (action-order match, curve plausibility, persona differentiation,
relationship sensitivity, no-degenerate-loops) over the moral-on slice of the 2800 — **same runner, wider
scope.**

---

## 3. Risks in the concept + mitigations

| # | Risk | Why it bites | Mitigation |
|---|------|------|-----------|
| R1 | **Golden-trace drift** when scoping moral into existing scenarios | mutating the 2800 files breaks the believability baseline and every regression | Do NOT mutate base files. Moral = a *variant axis* (overlay), base stays byte-identical with gains=0. Hash-gate the base. |
| R2 | **Ledger becomes a parallel hidden state system** | `Secret`/`LieRecord` mutating outside `update`/`post_effects` violates single-commit + "one source of truth" | Ledger read-only in `update`; mutated only in `post_effects`; only effect is emitting cues. Trace every ledger write. |
| R3 | **Non-determinism via lie/confession "probability"** | sigmoid + sampling = RNG in loop → bit-for-bit determinism lost | Probabilities → deterministic potentials + thresholds; argmax arbitration; no RNG. |
| R4 | **Stability: salience self-amp loop** `(1+guilt)(1+exposure_risk)` | positive feedback → salience pins at 1.0 ("permanently maximally guilty") | saturating coupling / extinction (existing burst machinery); Jury check before calibration. |
| R5 | **Stability: rumination↔stress↔fatigue loop** | 3-node positive loop → multiday blow-up / breakdown every run | net loop gain < 1; idle_recovery on moral states; linearize + Jury-test the expanded coupling matrix. |
| R6 | **Multiplicative impulses collapse to ~0** | 6–7-factor products under decay = dead system, nothing moral fires | use engine form `Σ gain·∏term`; calibration lifts gains; sanity gate asserts *something* moral moves. |
| R7 | **Multi-agent gap** (witnesses/gossip/social tension) | engine is per-persona; no shared room state | propagation lives in the scenario/world driver; engine models accused+accuser only; **blocked on M-MEM** multi-event mapper. Sequence M-MEM before M-J.3. |
| R8 | **Scope creep undermines "less is more" + debuggability** | 7 states + ledger + traits + actions at once → chaotic traces that read as scripted-random | ship M-J.0 guilt core first; full topology decided now, implemented in slices; diagram per slice. |
| R9 | **Trait duplication** (anxiety vs threat_sensitivity, empathy vs gratitude) | two knobs for one effect → un-calibratable | de-dup against existing 10 before adding; map table in the spec delta. |
| R10 | **Overlay confounds invariant isolation** | with many systems live in one day, a failed moral invariant is hard to attribute | overlay carries a labeled probe window + the moral trace fields; judge reads the moral coupling_output, not just narration; keep a *small* isolated moral micro-suite (≪700) for unit-level mechanism proofs alongside the scoped corpus. |
| R11 | **Judge-model confound on the moral slice** | believability A/Bs drift with judge model, not engine (known issue) | hold judge model constant for moral A/Bs; prefer deterministic narration-diff for "did the engine change" questions. |

---

## 4. Open decisions to confirm before coding
- Confirm the **overlay-axis** interpretation of "expand scope" (reuse base scenarios + moral variant) vs.
  the alternative (enrich a *subset* of base files in place — rejected here for R1).
- Keep a **small isolated moral micro-suite** for mechanism unit-tests (R10), or rely solely on the scoped
  corpus? (recommend: keep a small one — tens of cases, not 1400.)
- `suspicion` as 4th relation dim (recommended) vs. parallel per-source map.
