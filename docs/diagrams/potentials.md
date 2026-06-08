# Block diagram — potentials (M7, reactive action potentials)

> Pure, combinational (no dynamics) — an **I/O contract + a combinational schematic**; the
> term→action weights live in `wiring.md`. Synchronized with `engine/potentials.py`.
> **Invariant (validated at load):** every declared *term* carries ≥1 state/derived/relation_agg factor;
> traits only MODULATE — `trait×trait` is forbidden, so personality alone (e.g. high stoicism) can never
> fire a reaction at zero emotion. Knows NO thresholds; selects nothing.

## I/O
`In:` state' + relations' + traits + derived_post + `command_pressure` (transient, this tick's order; 0 if
none) + `kindness_pressure` (transient, this tick's appraised kindness; 0 if none) + `event_source` (the
order's/event's/gesture's source, for the per-source relation factor). `Out:` PotentialVector
(complain, outburst, cold_response, cooperate, refuse, positive_response), each `clamp01` (shared scale with
the selector's thresholds).

## Combinational form

```
   declared TERMS (config.potential_terms) = product of factors (state / derived / relation_agg / trait, opt. complemented):
     dissatisfaction_x_pride = dissatisfaction · pride        anger_x_low_control = anger · (1 − eff_self_control)
     anger_x_stoicism = anger · stoicism                      frustration_x_need_control = frustration · need_for_control
     resentment_max = max over sources of resentment          (+ bare: frustration, hunger, irritability, dissatisfaction)
   obedience TERMS (command-gated; command_pressure = this tick's order, 0 if none; relation = the COMMAND's source):
     command_x_respect_src = command_pressure · respect[src]          command_x_resentment_src = command_pressure · resentment[src]
     command_x_lowrespect_x_nfc = command_pressure · (1−respect[src]) · need_for_control
     command_x_frustration_x_nfc = command_pressure · frustration · need_for_control
   kindness TERMS (gesture-gated; kindness_pressure = this tick's appraised kindness, 0 if none; relation = the GESTURE's source):
     kindness_x_nonresent_src = kindness_pressure · (1−resentment[src])     kindness_x_trust_src = kindness_pressure · trust[src]
       (both pair the transient with a per-source RELATION factor → the load invariant holds; a transient can't fire alone)
   bystander TERM (target policy; bystander_pressure = a non-provoking event from a source S ≠ the current provoker, within the
                   residual window; 0 otherwise; relation = that source S):
     bystander_x_respect_src = bystander_pressure · respect[src]            (a respected bystander is spared displaced anger)

   potential[action] = clamp01( Σ weight · term ) :
     complain          = 0.70·dissatisfaction + 0.40·frustration + 0.15·hunger + 0.40·dissatisfaction_x_pride − 1.0·kindness_x_nonresent_src   ◄ INHIBITORY
     outburst          = 1.20·anger_x_low_control + 0.20·irritability − 1.0·command_x_respect_src − 1.0·kindness_x_nonresent_src − 1.0·bystander_x_respect_src  ◄ INHIBITORY×3
     cold_response     = 1.10·anger_x_stoicism + 0.20·frustration − 1.0·kindness_x_nonresent_src − 1.0·bystander_x_respect_src                ◄ INHIBITORY
     cooperate         = 1.0·command_x_respect_src                                                  (GATE 3 — comply w/ a respected commander)
     refuse            = 1.0·command_x_resentment_src + 0.8·command_x_lowrespect_x_nfc + 0.5·command_x_frustration_x_nfc
     positive_response = 0.40·kindness_x_nonresent_src + 0.60·kindness_x_trust_src                  (THEME A — warm reply; floor + trust bonus)
```

## Emergent suppression split (why two actions from one anger)
`anger × stoicism → cold_response` vs `anger × (1−eff_self_control) → outburst`: the SAME anger, weighted
by different trait modulations, routes to different actions — the suppression split is emergent from the
term wiring, not an `if`. The selector (M8) then gates these against thresholds.

## Obedience priority over venting (signed/inhibitory edge — D11 Branic)
`command_x_respect_src` (= `command_pressure · respect[src]`) is read with a **+** weight by `cooperate`
and a **−** weight by `outburst` — the system's first **inhibitory** potential edge. A respected
commander's order therefore *lowers* the venting potential, so a recruit carrying residual ambient anger
**obeys** instead of snapping at the SAME order he obeyed a tick earlier. Neutral by default (no order →
`command_pressure = 0` → 0; low respect → small; high respect → strong) → litmus-safe by construction (the
command-less burst contrast and the low-respect `refuse` are untouched). Scoped to `outburst` only — a curt
`cold_response` to a respected order stays believable. `k` is a believability-strength **placeholder**
(ordering authorized; magnitude pending §17), like the pride→insult modulator.

## Kindness appraised → positive_response + inhibitory edge (Theme A — the mirror of provocation)
`kindness_pressure` (this tick's appraised goodwill — a **gesture** `food_given`/`help`, appraised
non-negative, from a **non-resented** source: `resentment[src] < provocation_resentment`; computed in
`simulation`, the mirror of `_event_is_provocation`; `0` otherwise) drives **`positive_response`**
(`kindness_x_nonresent_src` floor + `kindness_x_trust_src` bonus → a warm reply, post-effect `+trust[src]`
goodwill, the mirror of `outburst`'s `+resentment[src]`) and `kindness_x_nonresent_src` is read with a
**−** weight by the hostile potentials (`outburst`/`cold_response`/`complain`) — the **second inhibitory
edge** (after obedience priority). A kind
gesture therefore *filters down* the urge to lash out: pre-loaded anger, armed above threshold and latched,
is **not** released onto the kind giver when the gesture opens the gate — it stays suppressed and
`positive_response` wins (no branch; same signed-edge mechanism). Neutral by default (no gesture / resented
source → `kindness_pressure = 0` → hostile potentials and selection bit-untouched; `positive_response = 0`).
Keeps Cichy by construction (jailer's soup → resented → not kindness → still galls). `k_kind`, the goodwill
deposit, and `react.positive_response` are **placeholders** (ordering authorized; magnitude owned by
calibration). **Displaced aggression** (a high-anger burst landing on the kind giver despite this) is OUT of
scope — gated behind a high `theta_displace` and deferred to `Ideas/burst_saturation_design_note.md`.

## Target policy: a respected bystander is spared displaced anger (THIRD inhibitory edge)
`bystander_pressure` (computed in `simulation`: a NON-provoking event from a source S that is NOT the current
provoker — `runtime.last_provocation_source` — while residual anger lingers within `reactive_window_ticks`; 0
otherwise) drives `bystander_x_respect_src = bystander_pressure · respect[S]`, read with a **−** weight by
`outburst`/`cold_response`. With one global `anger` pool, leftover anger from provoker X would otherwise vent
on whoever interacts next; this edge damps that venting **in proportion to how much you respect the bystander**
(`halgrim_068`: no cold contempt at respected Edda for Wojsław's offence → the obedience response wins
instead). Neutral by construction (fresh provocation / the provoker themselves / no residual anger → 0 →
single-source litmus bit-identical). The unification with the other per-entity filters is the HIGH-priority
`Ideas/filter_unification_milestone.md`. **Displaced aggression** (the burst DOES land at very high anger)
stays deferred behind `theta_displace`.
