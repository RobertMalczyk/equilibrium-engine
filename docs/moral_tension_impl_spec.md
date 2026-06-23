# M-J Moral Tension / Secrecy Dynamics — implementation specification

> Engineering blueprint. Reconciles the original M-J proposal with the Equilibrium Engine architecture
> (`moral_tension_review.md`) and the scope-expansion test strategy (`moral_tension_test_plan.md`).
> Every quantity here is **topology** (decided now) or a **named config key** (calibrated later) —
> there are no chosen numbers and no numeric literals destined for code. Reads against the real engine:
> `engine/schema.py`, `mapper.py`, `update.py`, `potentials.py`, `action_selector.py`, `simulation.py`,
> `debug.py`, `calibration/defaults.yaml`.

---

## 1. Architecture placement (where each piece lives in the tick)

The tick order is unchanged (`simulation.py`): freeze → derived_pre → perception(mapper→filters) →
gating → **update** → commit+clamp → derived_post → potentials → selector → **post_effects** → bookkeeping.
The moral layer inserts only at existing seams:

| Moral piece | Engine seam | Mutation site |
|---|---|---|
| moral states (guilt, …) | `GLOBAL_STATES` integrators | `update.compute` only |
| suspicion | 4th `RELATION_DIMS` entry | `update` (decay) + `post_effects` (action cost) |
| MoralLedger (secrets/lies) | frozen into `Snapshot`, **read-only in `update`** | `post_effects` only |
| moral cues | new mapper channels | `mapper.map_event` |
| moral actions | `POTENTIAL_NAMES` + terms/weights | selector (read) + `post_effects` (book) |
| moral coupling | `gains` / `couplings` config | `update.compute` |

**Invariant preserved:** state mutates in exactly two places — `update` (dynamics) and `post_effects`
(the selector's booked effects). The ledger is read-only everywhere `update` runs.

---

## 2. State extensions (schema.py)

### 2.1 Global moral states (append to `GLOBAL_STATES`, frozen order)
```
guilt, exposure_anxiety, repair_drive, avoidance_drive,
rumination, cognitive_load_from_lies, perceived_injustice
```
Each is a standard integrator-with-decay in `[0,1]`. Default `initial_global_state = 0` for all personas.
No new code shape — `update.compute` already iterates `GLOBAL_STATES`.

### 2.2 Relation dimension (append to `RELATION_DIMS`)
```
trust, respect, resentment, suspicion
```
`suspicion` is per-source, decays with its own half-life, filtered by `relation_filter` exactly like the
other three. Default 0. **This is the only `RELATION_DIMS` edit; it is a one-line tuple change + config.**

### 2.3 Traits (append to `TRAIT_NAMES`, after de-dup)
Reuse existing where semantics match — **do not** re-add:
- `anxiety` → use existing `threat_sensitivity`
- `empathy` → modeled via existing `gratitude` + a new `empathy` only if contrast tests need separation
- `conscientiousness`, `norm_rigidity` → fold into existing `patience`/`base_self_control` unless a test
  proves they must separate.

Genuinely-new traits to add (each a static `[0,1]` gain-modulator):
```
honesty_humility, guilt_proneness, machiavellianism, shame_sensitivity,
lie_skill, gossip_tendency, injustice_sensitivity, conflict_avoidance
```
The spec delta carries the full de-dup map (proposed→canonical).

---

## 3. The MoralLedger (the one genuinely-new structure)

A per-runtime store held beside `global_state`/`relations`, **deep-copied into `Snapshot.freeze()`**,
read-only during `update`/`potentials`, mutated only by `post_effects`.

### 3.1 `Secret` (record; authored fields are scenario inputs, dynamic fields are mini-integrators)
```
id              : str
owner_id        : AgentId
topic           : str               # semantic label (string key, used for cue matching)
category        : enum{ surprise, self_protection, betrayal, crime,
                        shameful_fact, protect_other, social_strategy, false_blame }
hidden_from      : list[AgentId]
known_by         : list[AgentId]
created_at       : int (tick)
# --- authored scenario constants (like persona traits; not emergent) ---
stakes               : [0,1]
moral_weight         : [0,1]
harm_to_target       : [0,1]
target_right_to_know : [0,1]
responsibility       : [0,1]
justification        : [0,1]
protected_target_id  : AgentId | None
harmed_target_id     : AgentId | None
# --- dynamic scalars (mini-integrators; decay() helper; in [0,1]) ---
salience          : [0,1]
exposure_risk     : [0,1]
unresolvedness    : [0,1]
confession_threshold : [0,1]   # derived from category × moral_weight × relation modifiers
```
`responsibility` and `justification` are **authored constants** (the review flagged them undefined) — they
sit on the Secret like `stakes`, not as emergent states.

### 3.2 `LieRecord`
```
id, liar_id, target_id, secret_id?(opt)
lie_type : enum{ omission, denial, fabrication, white_lie, antisocial_lie, blame_shift }
complexity, plausibility, consistency_debt, maintenance_load, detected_risk : [0,1]  # dynamic
last_reinforced_at : int
witnesses : list[AgentId]
```
`consistency_debt`, `maintenance_load`, `detected_risk` are mini-integrators (decay + reinforcement).

### 3.3 Determinism & serialization
Ledger is serialized into the trace with canonical key order; deep-copied at `freeze()`; never carries
RNG. All ledger writes are booked in `post_effects` and appear in the trace's `relation_delta`/ledger-delta
summary.

---

## 4. Cues → channels (mapper.py)

Secrets do not act on their own; a **cue event** raises salience. New mapper event→channel rules
(each emits a `SemanticInputVector` entry; classes: SELF / RELATIONAL / AFFINITY):

| Event | Channel(s) | Class | Source/Target |
|---|---|---|---|
| `secret_cued` | `secret_cue` | SELF | (cue strength = intensity) |
| `direct_question` | `probe` | RELATIONAL | source = questioner |
| `accusation` / `false_accusation` | `accusation` | RELATIONAL | source = accuser |
| `lie_detected` | `betrayal` | RELATIONAL | source = liar (on target's runtime) |
| `secret_exposed` | `exposure` | RELATIONAL/SELF | public flag in context |
| `confession`/`apology`/`reparation` | `repair_in` | RELATIONAL | source = confessor (on target) |
| `confiding` | `confide_in` | RELATIONAL | source = confider |
| `suspicion_raised` | `suspicion_cue` | RELATIONAL | source |

Cue *strength* comes from the event intensity and the world; the engine then computes the salience impulse
(below). Scenarios that use none of these channels are unaffected → existing goldens intact.

---

## 5. Equations (topology fixed; every coefficient is a named config key)

All use the engine form **`impulse = Σ gain_k · ∏(factor)`** (not bare 6-way products — review R6), and the
standard integrator `x' = decay·x + impulse − relief`, clamp `[0,1]`.

### 5.1 Secret salience (per active secret, updated in the ledger pass within `post_effects`)
```
salience_impulse = g_sal · cue_strength
                 · (a_unres + b_unres·unresolvedness)
                 · (a_stake + b_stake·stakes)
                 · f_guilt(guilt) · f_expo(exposure_risk)
```
`g_sal, a_*, b_*` config; `f_guilt`, `f_expo` are **saturating** (e.g. `1 + k·x/(1+x)`) to break the
salience self-amplification loop (review R4). Decay: `minor_secret_salience_half_life` /
`serious_secret_salience_half_life` selected by category.

### 5.2 Lie decision (deterministic potential — NOT a sampled probability)
`lie` is a member of `POTENTIAL_NAMES`. Its potential (potentials.py form `Σ w·∏term`):
```
need     = secret.salience · target_presence · topic_relevance · exposure_risk
resist   = w_hh·honesty_humility + w_g·guilt + w_rel·relationship_value(target)
         + w_fear·fear(target) · suspicion[target]
lie_potential = clamp01( w_benefit·concealment_benefit + w_self·self_protection
                       + w_mach·machiavellianism + w_need·need − resist )
```
Selector arbitration (argmax over in-play actions vs `theta_react.lie`) decides — no RNG, no sigmoid
sampling. (A fixed squashing function may wrap a term, but nothing is *drawn*.)

### 5.3 Lie performed — booked in `post_effects` (global deltas + ledger write)
```
stress           += g_lie_stress · complexity · target_importance · threat_sensitivity
cognitive_load   += g_load · maintenance_load
guilt            += g_lie_guilt · lie_moral_cost · guilt_proneness
exposure_risk    += g_expo · complexity · witness_count
consistency_debt += g_debt · complexity
→ create/update LieRecord; emit `lie_created` trace event
```

### 5.4 Guilt impulse (review-corrected: sum-of-gated-products, not a single tiny product)
```
guilt_impulse = g_guilt · responsibility · harm_to_target · moral_weight
              · target_right_to_know · empathy(target) · guilt_proneness
              · (1 − justification)
```
Kept multiplicative *as gating* (any zero factor → no guilt: a harmless surprise yields ~0), but `g_guilt`
is large enough (calibration) that a fully-responsible harmful secret moves guilt meaningfully. White-lie
vs antisocial-lie separation falls out of `moral_weight`/`category`. Half-life:
`minor_guilt_half_life` / `serious_guilt_half_life`.

### 5.5 Repair drive & confession (deterministic potential)
```
repair_drive_impulse = g_rep · guilt · responsibility · relationship_value(target) · opportunity
confess_potential = clamp01( w_rd·repair_drive + w_tr·trust[target] + w_mercy·mercy(target)
                           − w_exa·exposure_anxiety − w_pun·expected_punishment(target)
                           − w_sh·shame_sensitivity )
```
`mercy(target)` and `expected_punishment(target)` are **derived** from relations
(`mercy ← f(trust, −resentment)`, `punishment ← f(authority_gradient, respect)`), not free scalars.
`confide` is the same shape but target = third party; safe vs gossip-prone split sets whether confiding
lowers `rumination` (safe) or raises `exposure_risk` (gossip-prone, via `gossip_tendency`/`gossip_risk`).

### 5.6 Accusation / false accusation (couplings on accused; driver fans out witnesses)
On the **accused** (booked from the `accusation` channel):
```
stress             += g_acc_stress · accusation_intensity · threat_sensitivity
anger              += g_acc_anger  · accusation_intensity · injustice_sensitivity
resentment[accuser]+= g_acc_res    · accusation_intensity
avoidance_drive    += g_acc_avoid  · accusation_intensity · conflict_avoidance
perceived_injustice+= g_acc_inj    · accusation_intensity
```
On the **accuser, after discovery** (driver emits `false_accusation` discovered → accuser runtime):
```
guilt += g_falseacc · discovered · guilt_proneness ; trust from witnesses ↓ (driver fan-out)
```
Witness propagation is **not** in `update` — the world/scenario driver emits per-witness events (blocked
on **M-MEM** multi-event mapper for simultaneous fan-out; sequence M-MEM first — review R7).

---

## 6. Mandatory coupling coverage (defaults.yaml `couplings`, all default 0)

Every edge is one sparse config line; signs as shown; Jury-checked as a block (review R4/R5).

```
guilt              → stress (+),  anger (−, empathy-gated),  repair_drive (+),  avoidance_drive (+ shame)
rumination         → stress (+),  fatigue (+)
cognitive_load     → fatigue (+)
exposure_anxiety   → stress (+),  avoidance_drive (+)
secret.salience    → stress (+, anxious via threat_sensitivity),  boredom (−, curious via novelty/gossip)
perceived_injustice→ anger (+),  frustration (+ when repair blocked)
suspicion[src]     → exposure_anxiety (+, only when src present — source-gated like social_exposure)
lie_detected(evt)  → anger[liar] (+),  resentment[liar] (+),  trust[liar] (−)   # relational gains
```
**Two loops to linearize before calibration:** salience↔guilt↔exposure_risk (5.1) and
rumination↔stress↔fatigue. Both must have loop gain < 1 or carry the existing `burst_extinction` /
saturating-coupling treatment. `idle_recovery` gains added for moral states so nights relieve fast stress
while serious guilt (72h) persists.

---

## 7. Action bias (potentials.py + action_selector.py)

New `POTENTIAL_NAMES`: `lie, deflect, blame_other, confess, confide, apologize, repair, remain_silent,
avoid`. Declarative `potential_terms` + `potential_weights` + `thresholds.react.*` / `interrupt.*`. The
biases requested in the proposal become signed weight edges (no `if`-scripting):

- exposure_anxiety high → +avoid/+remain_silent/+deflect, +nervous-lie term
- guilt high ∧ trust[target] high → +confess/+apologize/+repair
- guilt high ∧ shame/fear high → +avoid/+remain_silent (shame term inhibits confess)
- cognitive_load high ∧ probed → +deflect (inhibited by `lie_skill`)
- secret threatened ∧ machiavellianism high → +lie/+blame_other
- gossip opportunity ∧ gossip_tendency high → +ask/+gossip/+provoke (boredom-gated)
- perceived_injustice high → +avoid for high conflict_avoidance; +refuse/feeds outburst for low

Outburst is **not** a moral action — it stays gated by the existing burst latch; moral states only feed
anger/stress/frustration that the latch reads (review + proposal both require this).

---

## 8. Trace (debug.py) — every moral effect auditable

Append a `moral` block to `TickTrace` (canonical field order):
```
tick, character_id,
active_secret_count, max_secret_salience,
guilt, exposure_anxiety, repair_drive, avoidance_drive, rumination,
cognitive_load_from_lies, perceived_injustice,
suspicion_by_source : {src: float},
last_moral_event,
selected_moral_action : {avoid|lie|confide|confess|repair|deflect|blame_other|apologize|remain_silent}|null,
coupling_output : { stress_impulse, anger_impulse, frustration_impulse, fatigue_impulse,
                    boredom_modifier, relation_delta : {src:{dim:Δ}} },
ledger_delta : { secrets:[{id,Δsalience,Δexposure_risk}], lies:[{id,Δconsistency_debt}] }
```
The trace must answer: why avoid / why lie / why confess / why angry / why repair / why a secret reduced
boredom for a gossip-prone persona but raised stress for an anxious one — all readable from
`coupling_output` + the term breakdown, without narration.

---

## 9. Tests — scope-expansion of the 2800 (see `moral_tension_test_plan.md`)

- **Baseline (most important):** moral layer present, all moral gains = 0 → existing ~2800 day/multiday
  goldens **byte-identical** (hash gate). Proof the layer is inert until wired.
- **`moral` variant axis:** same personas/seeds/day structures + a deterministic moral overlay
  (secret/lie/accusation thread seeded from `_seed_for`), judged by the expanded invariant set. Scope
  grows, file-count does not balloon to 1400.
- **Small isolated micro-suite** (tens of cases, not 700) for mechanism unit-proofs (clean attribution).
- **Invariants** folded into `sanity_multiday.py` + judge prompt: guilt-prone confesses earlier; mach
  lies more/guilts less; close target → more guilt + trust damage; white_lie < antisocial_lie; safe
  confide ↓rumination; gossip confide ↑exposure_risk; detected lie → target anger+resentment; false
  accusation → accused anger/resentment/injustice; active secret stress↑(anxious)/boredom↓(gossip);
  serious guilt survives night; relation damage persists; **no degenerate loop; outburst ≠ guilt alone.**
- **Stability tests:** Jury check on the expanded coupling matrix (5.1 + §6 loops) as a property test.

## 10. Calibration

Reuse the burst-style overlay + blind-judge regression harness. Grid over
`secret_salience_half_life, guilt_half_life_{minor,serious}, lie_load_half_life, suspicion_half_life,
repair_drive_half_life`; score `0.35·action_order + 0.25·curve_plausibility + 0.20·persona_diff +
0.10·relationship_sensitivity + 0.10·no_degenerate_loops` over the moral-on slice. Same runner, wider
scope. All defaults are **calibration anchors, not psychological laws.**

## 11. Half-life defaults (config placeholders, calibration-owned)
```
minor_secret_salience_half_life  : 12h     serious_secret_salience_half_life : 36h
lie_load_half_life               : 6h      minor_guilt_half_life             : 18h
serious_guilt_half_life          : 72h     exposure_anxiety_half_life        : 60min
concealment_pressure_half_life   : 30min   repair_drive_half_life            : 24h
weak_suspicion_half_life         : 48h     evidence_suspicion_half_life      : 14d
trust_damage_half_life           : 30d (or reuse relation memory)
```
All ≥30min → none beats anger(30s); **dt unchanged**, non-moral traces bit-identical.

## 12. Build order (vertical slices, diagram-per-slice — CLAUDE.md directive)
1. **M-J.0 guilt core** — one config-seeded secret, `guilt`+`exposure_anxiety`, couple→stress/anger/trust,
   actions `confess`/`remain_silent`. Litmus: guilt-prone confesses earlier. `docs/diagrams/moral_tension.md`.
2. **M-J.1 lie loop** — `LieRecord`, `cognitive_load`, `consistency_debt`, `lie`/`deflect`, detection.
3. **M-J.2 repair/confide** — `repair_drive`, `rumination`, `confide`/`apologize`/`reparation`.
4. **M-J.3 accusation/suspicion** — `perceived_injustice`, `suspicion`, multi-agent driver (**needs M-MEM**).
5. **M-J.4 full ledger + calibration grid + scoped corpus**.

## 13. Self-review checklist (to assert at each slice's Definition of Done)
Architecture: no LLM in loop ✦ no behavior-shaping literals in code ✦ all tunables in config ✦ synchronous
single-commit preserved ✦ no event→action scripting (potentials only) ✦ moral layer coupled to existing
states ✦ trace explains every moral outcome ✦ ledger read-only in `update`, written only in `post_effects`
✦ no RNG / deterministic potentials ✦ existing 2800 goldens byte-identical with gains=0 ✦ Jury-stable
coupling matrix ✦ diagram (both forms) synced with code.
Coupling coverage + test/eval checklist: as enumerated in the original proposal, asserted via §6 edges and
§9 invariants.
