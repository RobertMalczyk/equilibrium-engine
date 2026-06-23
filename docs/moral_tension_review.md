# M-J Moral Tension / Secrecy Dynamics — concept review (pre-implementation)

> Status: **REVIEW ONLY.** No engine code written. This document evaluates the proposed
> milestone against the Equilibrium Engine architecture, the equation logic, the relation/state
> coupling surface, and the likely emergent outcomes — so the topology can be decided *before*
> calibration (per CLAUDE.md: "topology now, constants from calibration").

Branch: `feature/m-j-moral-tension` (off `main` @ `d84b7c6`).

---

## 0. One-paragraph verdict

The **state half** of the proposal (guilt, exposure_anxiety, repair_drive, avoidance_drive,
rumination, cognitive_load, perceived_injustice as bounded integrators-with-decay, coupled into
stress/anger/frustration/fatigue/boredom and trust/respect/resentment) fits the engine cleanly and
is the strong core of the idea. The **ledger half** (`Secret`/`LieRecord` as identified objects with
owners, `hidden_from` lists, categories) is a genuinely *new kind of data* the engine does not have —
it is an entity store, not an integrator, and must be built as a **read-only cue/impulse source that
never mutates state directly**, or it breaks the "one generic integrator" invariant. Four parts of
the spec are architecturally incompatible as written and must be reshaped: (1) `sigmoid` lie/confession
**probabilities** → deterministic potentials+thresholds; (2) ~80 inline numeric literals → config;
(3) witness/gossip/"social tension" propagation → an **orchestration layer above the per-persona
engine**, not inside it; (4) the milestone scope violates "less is more" by ~10× and must ship as a
vertical slice first. With those four reshapes, the concept is sound and high-value.

---

## (a) ENGINE — does it fit the architecture & invariants?

### Fits cleanly
- **Moral states as integrators.** guilt, exposure_anxiety, repair_drive, avoidance_drive, rumination,
  cognitive_load_from_lies, perceived_injustice are exactly the engine's primitive: `x_next =
  decay·x + impulses − reliefs`, clamp [0,1]. They slot into `GLOBAL_STATES`, `half_lives`, `gains`,
  `couplings` with **zero new code shape** — same extension contract as any state (spec §14).
- **Half-life choices don't disturb dt.** Current fastest = anger (30s) → dt≈3s. Every proposed moral
  half-life is ≥30min, so none becomes the new `min(half_life)`; **dt is unchanged, golden traces for
  non-moral scenarios stay bit-identical.** Good.
- **Action bias via potentials.** confess / lie / deflect / blame_other / apologize / confide / avoid /
  remain_silent enter `POTENTIAL_NAMES` with declarative `potential_terms` + `potential_weights` +
  `theta_react`. This is the intended "bias the selector, don't script" path. Compatible.
- **Suspicion is relational.** `suspicion_by_source: map[AgentId,float]` is structurally identical to a
  relation dimension. Model it as a **4th relation dim** (`trust, respect, resentment, suspicion`) or a
  parallel per-source map reusing `relation_filter`. Reuse, do not invent parallel memory.
- **Confession/repair routed through existing burst seam.** "Outburst is not directly caused by guilt"
  is exactly right and already enforceable: burst latches only on (anger,stress) thresholds (§8). Guilt
  feeds anger/stress; the latch stays the single gate. No new burst mechanism.

### Does NOT fit as written — must reshape
1. **`Secret` / `LieRecord` objects.** The engine has no entity/object store. States are scalars;
   relations are per-source scalar dims. An object with `id, owner_id, hidden_from[], known_by[],
   category` is new infrastructure. **Decision:** build a `MoralLedger` that lives *beside* the runtime,
   is frozen into the snapshot read-only, and whose ONLY engine effect is to **emit cues (events →
   channels via the mapper)** and to be **updated by `post_effects`** (the one sanctioned mutation site
   besides `update`). The ledger must never write `global_state` directly. This keeps "state mutates in
   one place" intact. Per-secret dynamic scalars (`salience, exposure_risk, unresolvedness`) are
   themselves mini-integrators — reuse the same `decay()` helper, do not hand-roll.
2. **Probabilistic `lie_probability = sigmoid(...)`, `confession_probability`.** The engine is
   **bit-for-bit deterministic; no RNG in the loop.** A "probability" that gets sampled would destroy
   determinism and the golden-trace discipline. **Decision:** these are **potentials**, not
   probabilities — compute the score deterministically, compare to `theta_react.lie` /
   `theta_react.confess`, and let the existing argmax arbitration pick. Drop the sigmoid sampling
   entirely; the sigmoid may stay only as a fixed squashing function on a potential term.
3. **Inline numeric literals (≈80 of them):** `0.4 + 0.6*unresolvedness`, `*0.05`, `*0.1`, `*0.3`,
   `trust*0.4`, `mercy*0.3`, … Every one violates "no numeric literal in engine code." **All become
   named config keys** (`gains.*`, `couplings.*`, `potential_weights.*`, `moral.*`). The equations in
   this spec are **topology (which terms exist)** — keep them; the coefficients are **calibration** —
   placeholder them.
4. **Witnesses / gossip propagation / "room or social tension surface".** The engine is **per-persona
   reactive** — one runtime per NPC, events arrive from sources; there is no shared room state, no
   witness fan-out, no cross-agent trust propagation. "Trust from witnesses decreases", "public exposure
   raises room tension", gossip spreading a secret → these are **multi-agent world orchestration**, a
   layer *above* the engine. **Decision:** the engine models the **accused's** and the **accuser's**
   internal states and the relation deltas on *their own* relation rows; propagation to third parties is
   produced by the **scenario/world driver** emitting `accusation` / `secret_exposed` events into each
   witness's runtime. Do not try to put a social graph inside `update`.

### Scope vs. "less is more" (overriding principle)
As written this is **7 new states + 1 relation dim + 2 ledger object types + ~15 traits + ~12 relation
modifiers + ~15 events + ~8 actions + 1400 scenarios + a calibration grid** in one milestone — ~10× the
granularity of any prior MVP step. That contradicts the project's core discipline. **Recommended
staging** (each a shippable vertical slice with its own diagram + tests):

- **M-J.0 — Guilt core (minimal):** ONE secret (config-seeded, no ledger objects yet) → `guilt` +
  `exposure_anxiety` integrators → couple to `stress`, `anger` (damp), `trust`. Actions: `confess`,
  `remain_silent`. Prove a guilt-prone persona confesses earlier than a low-guilt one (the litmus).
- **M-J.1 — Lie loop:** add `LieRecord` + `cognitive_load_from_lies` + `consistency_debt`; actions
  `lie`, `deflect`; couple to fatigue/stress; lie-detected → target anger/resentment/trust-damage.
- **M-J.2 — Repair & confiding:** `repair_drive`, `rumination`, `confide`, `apologize`, `reparation`;
  safe vs. gossip-prone confiding split.
- **M-J.3 — Accusation/scapegoat:** `perceived_injustice`, `suspicion`, accusation/false-accusation,
  the multi-agent driver seam.
- **M-J.4 — Full ledger + calibration grid + 1400 corpus.**

Decide topology for ALL of M-J.0–.4 now (this doc), implement .0 first.

---

## (b) LOGIC — do the equations hold up?

### Sound
- **"A secret is an intention to hide," not just hidden info** → modeling salience as cue-driven (rises
  when target/topic/witness present, decays otherwise) is the right control-systems framing. Correct.
- **"A secret alone must not create guilt"** → `guilt_impulse = responsibility · harm · moral_weight ·
  target_right_to_know · empathy · guilt_proneness · (1−justification)`. Multiplicative gating is
  exactly how the engine keeps terms inert when any factor is 0 (cf. potential terms each carry a
  state/relation factor). White-lie→low guilt, antisocial→high guilt fall out of the product. **Good.**
- **Repair drive as a function of guilt × relationship value × opportunity** — clean, bounded, decays.

### Logic problems to fix
1. **Multiplicative chains collapse to ~0.** Products of 6–7 factors each <1 (e.g. guilt_impulse) yield
   tiny impulses; after decay the state barely moves. Either (a) factors are *gates* {0/near-1} not
   *magnitudes*, or (b) use a weighted-sum-of-products like existing `potential[a]=Σ w·∏term`. **Pick the
   engine's existing form:** `impulse = Σ gain_k · ∏(factor)` so calibration can lift gains. Don't ship
   bare 6-way products.
2. **`secret_salience_impulse` has `(1+guilt)(1+exposure_risk)` self-amplification.** salience→guilt and
   exposure_risk→salience both positive → a **positive feedback loop**. Bounded by clamp, but can pin at
   1.0 (degenerate "always maximally salient"). Needs a damping edge or a saturating coupling
   (the `coupling_escalation`/extinction machinery already exists for exactly this). **Flag for Jury check.**
3. **rumination ↔ stress ↔ fatigue loop.** rumination→stress (+), stress→? , rumination→fatigue (+),
   fatigue→worse-lying→exposure_risk→stress. This is the **main stability risk**: a 3–4 node positive
   loop. The poles-in-unit-circle invariant is non-negotiable; this loop must be net-contractive
   (sum of loop gains < 1) or carry an extinction term. **Must be linearized and Jury-tested before any
   calibration.**
4. **`justification` and `responsibility` are undefined inputs.** Are they per-secret authored constants,
   or derived from traits/relations? Spec leaves them floating. **Decision needed:** author them on the
   `Secret` (like `stakes`, `moral_weight`) — they are scenario inputs, not emergent states.
5. **Confession potential mixes signed terms with raw weights** (`+trust·0.4 +mercy·0.3 −anxiety
   −punishment −shame`). Fine as a potential, but `mercy_of_target` and `expected_punishment` are not
   engine quantities — they must be **derived** from relations (mercy ← f(trust,resentment),
   punishment ← f(authority_gradient, respect)) or authored. No new free-floating scalars.

### Determinism audit
- No RNG (after the sigmoid→threshold reshape). ✔
- All cue detection (target-in-room, topic-mentioned) comes from **events**, which are deterministic
  scenario inputs. ✔
- Ledger updates only in `post_effects`. ✔ — keeps synchronous single-commit semantics.

---

## (c) POSSIBLE RELATION — coupling to the existing state/relation graph

Proposed coupling map, expressed in the engine's vocabulary (every edge = one config line, sparse):

| From (moral) | To (existing) | Sign | Engine slot | Stability note |
|---|---|---|---|---|
| secret.salience·exposure_risk | stress | + | `couplings.stress.<moral>` (via channel) | bounded by clamp |
| secret.salience | boredom | − (curious personas) / +stress (anxious) | trait-modulated gain | **persona-split** — the litmus test |
| rumination | stress, fatigue | + | couplings | **loop — Jury** |
| guilt | stress | + | couplings | ok |
| guilt | anger | − (empathy-gated) | couplings (signed) | damps outburst — good |
| guilt | repair_drive | + | couplings | drives confession |
| guilt+shame | avoidance_drive | + | couplings | withdrawal |
| cognitive_load_from_lies | fatigue | + | couplings | ok |
| exposure_anxiety | stress | + | couplings | ok |
| lie detected (event) | anger[liar], resentment[liar], −trust[liar] | relational gains | `gains.relations.*` | reuse relation_filter |
| accusation (event) | stress, anger, resentment[accuser], perceived_injustice | mixed | gains | ok |
| false-accusation-discovered | guilt[accuser], −trust from witnesses | gains (driver fans out) | multi-agent seam |
| suspicion[source] | exposure_anxiety (when source present) | + | derived, source-gated | reuse social-exposure gate |

Key relational decisions:
- **Reuse `trust/respect/resentment`** for trust-damage, betrayal-anger, mercy-derivation — do NOT add a
  parallel "relationship_value" store. `relationship_value_to_target ← f(trust, closeness)` where
  `closeness` is an authored relation modifier (config), not new memory.
- **Add `suspicion` as the 4th relation dim** (cleanest) — it decays per source with its own half-life,
  filters per source exactly like the other three.
- **Relation modifiers** (closeness, fear, dependency, rivalry, authority_gradient, …) are **authored
  per-relation config**, like persona `initial_relations`, NOT dynamic states. They modulate gains
  (`right_to_know_multiplier` scales the guilt gain; `gossip_risk` scales exposure_risk gain). This is
  the existing gain-modulator pattern, just keyed on a relation field instead of a trait.

Trait hygiene: **reuse before adding.** `anxiety ≈ threat_sensitivity`; `empathy` overlaps `gratitude`;
`pride` exists. Map the 15 proposed moral traits onto the 10 existing where semantics match; add only the
genuinely new ones (honesty_humility, guilt_proneness, machiavellianism, shame_sensitivity, lie_skill,
gossip_tendency, injustice_sensitivity, conflict_avoidance). Avoid two names for one knob.

---

## (d) POSSIBLE OUTCOME — what emerges, and what could go wrong

### Intended emergent behaviors (the value)
- **Same scenario, different play (the litmus):** a secret-bearing event in the same room produces
  *seeking/gossip-probe* in a curious persona (boredom↓) and *withdrawal+stress* in an anxious one — from
  one trait split, no script. This is precisely the project's thesis and the strongest demo.
- **Guilt→confession arc over time:** guilt accumulates, repair_drive crosses threshold, persona confesses
  *unprompted* after N ticks — earlier for guilt-prone, later/never for machiavellian. Emergent timing.
- **Lie maintenance fatigue:** repeated lies raise cognitive_load→fatigue→worse lying→higher
  exposure_risk→stress — a self-tightening noose that ends in a slip or a confession. Emergent, not coded.
- **Cross-day persistence:** serious guilt (72h half-life) survives the nightly sleep stress-reset while
  fast stress clears — "he slept it off but still feels bad." Already supported by per-dimension half-lives.

### Failure modes to guard against (degenerate outcomes)
1. **Always-confess / always-lie / always-outburst** — the spec's own anti-goal. Cause: a dominant
   potential weight or an unbounded driving state. Guard: contrast tests + the "no degenerate loop"
   calibration score; require *both* a confessing and a non-confessing persona on the same case.
2. **Salience/exposure pinned at 1.0** (the `(1+guilt)(1+exposure_risk)` loop) → "permanently maximally
   guilty." Guard: saturating coupling / extinction; Jury check.
3. **Rumination runaway → stress/fatigue blow-up** across a multiday run → "spirals into breakdown every
   time." Guard: net-contractive loop gain; idle_recovery on moral states (nights must relieve fast
   stress while leaving serious guilt).
4. **Room-wide cascade** (everyone suspicious of everyone) once the multi-agent driver fans out
   accusation/gossip events — explicitly called out in the spec. Guard: suspicion gains small +
   fast-ish decay for weak suspicion (48h) vs slow for evidence (14d); cap fan-out per tick in the driver.
5. **Dead system** — nothing moral ever fires because thresholds too high / impulses too small (the
   collapsing-product problem in (b.1)). Guard: the "personality_differentiation" + "state_curve_plausibility"
   calibration scores; a sanity gate like `sanity_multiday.py` that asserts *something* moral moves.
6. **Golden-trace drift on non-moral scenarios.** Adding states/edges with nonzero defaults could change
   existing traces. Guard: **all moral couplings default to 0 / neutral**, moral states default-inert;
   the existing day/multiday goldens must stay byte-identical with the moral layer present-but-dormant
   (verify by hash, per [[verify-engine-change-deterministically]]).

### Lighthouse / thesis check
This *strengthens* the core thesis (visible behavior from internal dynamics) — guilt/secrecy is a rich
new source of emergent, persona-contrasting behavior with no new scripting. The risk to the thesis is
**scope-induced incoherence**: shipping all of it at once, un-calibrated, produces chaotic traces that
*look* scripted-random and undermine the "debuggable control system" claim. Staging (M-J.0 first) is the
mitigation.

---

## Required-before-implementation checklist (topology decisions to lock now)

- [ ] `MoralLedger` is read-only-in-`update`, mutated only in `post_effects`; emits cues as events. 
- [ ] sigmoid probabilities → deterministic potentials + thresholds (no RNG).
- [ ] every coefficient → named config key; zero literals in code.
- [ ] `suspicion` added as 4th relation dim (decision) vs. parallel map.
- [ ] relation modifiers (closeness/fear/…) authored as relation config, modulating gains — not states.
- [ ] traits de-duplicated against the existing 10 before adding 8 genuinely-new.
- [ ] all moral couplings default 0 → existing goldens byte-identical (dormant layer).
- [ ] the two stability loops (salience self-amp; rumination↔stress↔fatigue) linearized + Jury-passed.
- [ ] multi-agent propagation lives in the scenario/world driver, not `update`.
- [ ] control + functional **block diagrams** authored in `docs/diagrams/moral_tension.md` BEFORE code
      (CLAUDE.md directive — no diagram = subsystem not done).
- [ ] scope staged M-J.0 → .4; implement .0 (guilt core) first.

## Next concrete step (if approved)
Author `docs/diagrams/moral_tension.md` (both forms) for the **M-J.0 guilt core** only, plus the
spec delta to `docs/rpg_persona_dynamics_spec_v1.md` (new states + edges + the ledger seam), get
sign-off, then implement M-J.0 as a vertical slice with a small deterministic moral mini-corpus before
scaling to the 1400-case generators.
