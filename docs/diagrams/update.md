# Block diagram — update (M6, the integrator core)

> Maintained in two forms (spec §12): **control** (integrators, summing junctions, gains, signed
> feedback) and **functional** (the cycle in domain language). Synchronized with `engine/update.py`.
> **Invariants made visible:**
> - **The only place state evolves.** Every state is the *same* generic integrator; a "role" is a
>   parameter preset, not a separate block (spec §14).
> - **Synchronous / frozen snapshot.** Couplings read `snapshot[y]` (start-of-tick), never the
>   in-progress `new` — so equation order cannot change the result.
> - **No clamp here.** `update` emits a raw additive `delta = new − old`; clamping happens at commit
>   (tick step 5), not inside this member.
> - **Sparse, declared wiring.** Only the listed coupling edges exist; everything else = 0 (neutral default).

## Member inputs / outputs

```
IN:  snapshot{global_state, relations, mode}   <- freeze (step 1, FROZEN)
     eff: EffectiveInputVector                 <- filters (M4); absent => no input terms
     derived_pre                               <- M5 (currently unused by the equations; reserved)
     config{decay, drifts, setpoints, gains, gain_modulators, couplings, action_params, idle_recovery, traits}
     active_action                             <- runtime (for BUSY per-tick effects)
     recovering: bool                          <- simulation: mode==IDLE AND unprovoked (idle homeostasis)
OUT: StateDelta{global: dict, relations: dict}  (raw deltas; commit clamps)
```

## Functional form (the cycle in domain language)

```
for each GLOBAL state x:                 # one generic integrator, 8 instances
    new = decay[x]·old                   # keep most of the old value (low-pass / memory)
        + (1−decay[x])·setpoint(x)       # pull toward the rest level (emotions: 0; self_control: base)
        + drift(x)                       # accumulators rise on their own: hunger, fatigue, boredom*
        + Σ gain[x][ch]·mod[x][ch]·eff[ch].value   # gated external inputs; mod = trait modulator (default 1)
        + Σ coupling[x][y]·snapshot[y]   # sparse state->state, read from the FROZEN snapshot
        + (mode∈{BUSY,SEEKING}) per_tick[x]   # BUSY=engaged activity relief (boredom×engaged_novelty;
                                         #   self_activity stress−/external+); SEEKING=seek cost (+frustr). M7 S2
        + (recovering) idle_factor·idle_recovery[x]  # IDLE & unprovoked: settle toward calm (stress/anger−). D11.
                                         #   the IDLE counterpart of BUSY per_tick; mutually exclusive with it.
                                         #   idle_factor = clamp01(1+k·(reactivity−ref)) in [0,1]: a reactive
                                         #   persona settles SLOWER (keeps its edge); calm ones recover fully.
                                         #   NOT below idle_recovery_floor[x]·resentment_max: a standing
                                         #   grievance keeps a persona tense (resentful captive idles wary). D11.
    delta_global[x] = new − old          # raw; commit clamps to [0,1]

for each relation src, dim in {trust,respect,resentment}:   # same integrator, memory preset (decay≈1)
    new = decay[dim]·old + (1−decay[dim])·setpoint(dim)
        + Σ dim_gain[ch]·eff[ch].value   for channels whose eff[ch].source == src
    delta_relations[src][dim] = new − old   (only nonzero deltas emitted)
```

`* drift(boredom)` is the M3b addition: idleness is a boredom source (topology edge declared in config;
magnitude is a calibration placeholder, not hand-set). Without it boredom rises only from the
`repetition` channel (events), so an empty watch produced no boredom.

`mod[x][ch]` is the **gain modulator** (spec §14): an input→state gain may be scaled by a trait,
`mod = 1 + k·(trait − ref)`, default `1` (no modulator = identity), declared sparsely in config like the
couplings. **First instance: `mod[anger][insult] = 1 + k·(pride − 0.5)`** — wound-sensitivity: a proud
persona's insult deposits *more* anger, a low-pride one *less*, so the sting differentiates from a TRAIT
(not from output-side stoicism). Anchored at `ref = 0.5` so a reference-pride persona keeps the calibrated
`gain[anger][insult]` exactly (Layer-2 freeze stays valid; only the per-persona *spread* is new). `mod` is
clamped `≥ 0` (a gain can't flip sign). `k` is a believability-strength placeholder (ordering authorized;
magnitude pending Level-3, spec §17).

## Control form (integrators / summing junctions / feedback)

```
            drift(x)         setpoint(x)·(1−decay)
               │                   │
   inputs ─►[Σ gain·mod]──►(+)     │            ┌─────────── one-pole integrator ───────────┐
                        │          ▼            │   x[t] = decay·x[t−1] + (Σ at the node)    │
   couplings ─►[Σ g·y_snapshot]─►(+)──►(Σ)─────►│   (decay = exp(−ln2/half_life))            │──► new_x ─► delta=new−old
                        ▲          ▲            └────────────────────────────────────────────┘
   BUSY per_tick ───────┤          │            (BUSY/SEEKING active per_tick XOR idle_recovery, never both)
   idle_recovery ───────┘          │            (gate: mode==IDLE & unprovoked -- D11 ambient homeostasis)
                                   └── decay·old   (old = snapshot[x], FROZEN)

   FROZEN COUPLING TOPOLOGY (signs all +; gains from calibration):
        hunger ─┐
        fatigue ┼──► stress ◄────────────┐         feedforward into the loop:
                                          │ (+)        hunger,fatigue → stress
        boredom ───► frustration ───► anger          boredom → frustration → anger
                                     │   ▲ │
                                     │   │ └──► stress     ┌─ THE ONLY FEEDBACK LOOP ─┐
                                     │   └───────────────  │   anger ↔ stress (2-cycle)│
                                     └─ (frustration→anger)└───────────────────────────┘

   STABILITY (mandatory re-check on gain change, spec §8):
     linearized 2-cycle [[decay_stress, g(anger→stress)],[g(stress→anger), decay_anger]]
     Jury:  g(anger→stress)·g(stress→anger) < (1−decay_stress)·(1−decay_anger)
     regime test: spectral radius of the full 6-state submatrix < 1.

   boredom has TWO deliberate outputs (spec §8):
     boredom ─► frustration→anger/complain   (REACTIVE, this coupling, 0.04)
     boredom ─► urge_boredom                 (PROACTIVE, read in derived.py — see derived.md)
   These are two outputs of one state into two paths, NOT a re-entanglement of the urge path.
```

## Role presets (same integrator, different parameters — spec §14)

| Role | setpoint | drift | decay | states |
|---|---|---|---|---|
| emotion | 0 | 0 | fast | boredom, stress, frustration, anger, satisfaction |
| accumulator | 0 | >0 | slow | hunger, fatigue, **boredom (drift added M3b)** |
| homeostat | base_self_control | 0 | medium | self_control |
| memory | 0 (or none) | 0 | ≈1 (very slow) | trust, respect, resentment |

`boredom` is both an emotion (fast decay to 0) and now carries a drift (idleness bores) — a parameter
preset, not a separate type. Its drift competes with that fast decay, so its idle equilibrium =
drift/(1−decay_boredom): a calibration quantity, not asserted by tests.
