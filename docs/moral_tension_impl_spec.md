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

### 1.1 Design decision — one-tick moral latency (intentional)

Because the ledger is read-only during `update` and mutated only in `post_effects`, and because
`potentials`/`selector` read the frozen start-of-tick state, a cue event that changes secret salience
cannot influence action selection in the same tick. **This is intentional, not a defect.**

**Decision: use one-tick moral latency.**
- A moral cue event observed in tick `T` is mapped and booked in tick `T`.
- Persistent `MoralLedger` changes (salience, exposure_risk, consistency_debt, …) are written in
  `post_effects` of tick `T`.
- `potentials` and action selection observe that ledger change starting in tick `T+1`.
- This preserves deterministic single-commit tick semantics — no mid-tick ledger mutation, no
  order-dependence.

Same-tick moral reflexes are allowed **only** through existing global-state couplings already available
on the frozen/update path (e.g. an `accusation` channel deposits into `stress`/`anger` in `update` of
tick `T`, visible to potentials of `T` via the post-commit state, exactly like any other channel). The
*ledger* never moves mid-tick to produce a reflex.

**Future-work note (do NOT implement now):** if same-tick *ledger-derived* reflexes are ever needed,
introduce a **read-only transient `moral_view`** derived from `Snapshot` + the current
`SemanticInputVector`, consumed by `potentials` without mutating the ledger before `post_effects`. This
keeps the single-commit invariant. It is explicitly deferred.

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
- `anxiety` → use existing `threat_sensitivity` (anxiety semantics are served by threat_sensitivity).
- `conscientiousness`, `norm_rigidity` → fold into existing `patience`/`base_self_control` unless a
  contrast test proves they must separate.

**`empathy` is a SEPARATE moral trait — added now, NOT aliased to `gratitude`.** Empathy and gratitude
are orthogonal: empathy is the capacity to feel a target's harm; gratitude is owed-debt for received
benefit. Guilt, repair, and harm-to-target reasoning depend on *empathy* even when no gratitude exists.
Examples: Halgrim can feel guilt toward Cichy without being grateful to him; Edda can empathize with
Cichy without owing him gratitude. `gratitude` remains a separate existing affect/relation-derived
modifier and is untouched.

Genuinely-new traits to add (each a static `[0,1]` gain-modulator):
```
empathy, honesty_humility, guilt_proneness, machiavellianism, shame_sensitivity,
lie_skill, gossip_tendency, injustice_sensitivity, conflict_avoidance
```
The spec delta carries the full de-dup map (proposed→canonical), including the explicit
`empathy ≠ gratitude` and `anxiety → threat_sensitivity` entries.

**`honesty_humility` ≠ `machiavellianism` — kept as two separate knobs (NOT one signed axis).**
They look like opposite poles of one dimension but model two *different aspects* of a person:
- `honesty_humility` (low) = a **bad habit** — a disposition to lie/deceive as the easy way out. The
  person still has a normal conscience: lying creates internal cost (cognitive_load, exposure_anxiety),
  they *can* feel guilt, and being forced to reveal the secret is **frustrating** (a thwarted goal).
  It gates the **lie / deflect** potentials.
- `machiavellianism` (high) = a **strategic, manipulative disposition** — calculated long-game
  manipulation with the moral-emotional cost suppressed. It does NOT merely flip honesty's sign: it
  **suppresses the guilt pathway** (low effective `empathy`/`guilt_proneness` response) so manipulation
  carries no remorse — the literature's *"Machiavellian cool syndrome"* (callousness + low anxiousness
  *during the act* avoid the guilt of harming others). It gates the **lie / blame_other** potentials on
  the *cold-calculation* side.

  **NOT identical to psychopathy (literature-checked, Dark Triad).** Machiavellianism and psychopathy
  are distinct facets. Psychopathy is impulsive, reckless, thrill-seeking and **low-anxiety**;
  Machiavellianism is calculated, patient, control-driven and — counter-intuitively — **uniquely
  associated with *higher* anxiety/stress and neuroticism**. So a Machiavellian is guilt-free but **not
  fearless**: they feel real `exposure_anxiety`/`stress` about being caught and about losing control.
  A fearless, anxiety-free, remorse-free profile is **psychopathy** — reserve that for a *separate
  future trait*, do not fold it into `machiavellianism`.

Because they touch different actions and different internal costs, a persona can sit low on **both**
(the conflicted coward who neither confesses nor schemes — just stays silent and avoids), which a single
collapsed axis could not represent. **Add per-slice, not all at once:** M-J.0 introduces only the four it
uses — `empathy, guilt_proneness, shame_sensitivity, honesty_humility`. `machiavellianism` + `lie_skill`
land with M-J.1, `gossip_tendency`/`conflict_avoidance` with M-J.2, `injustice_sensitivity` with M-J.3.

**Calibration / test expectation (machiavellian persona):** a high-`machiavellianism` persona feels
**no `guilt`** and **no guilt-derived `frustration`** — manipulation carries no moral cost (cool
syndrome), so the guilt→frustration path stays near-zero. But — per the literature correction above —
they are **not emotionally flat**: they **do** feel `exposure_anxiety`/`stress` about being caught and
about losing control, and on exposure they show **cold/calculated `anger`** rather than an impulsive
blow-up. Any frustration is *instrumental* (thwarted control), not *moral*, and is expressed as cold
anger. Contrast targets on the SAME exposure event:
- **habitual liar** (`honesty_humility` low, normal conscience): some `guilt` + moral `frustration`.
- **machiavellian** (guilt-suppressed, anxious): `exposure_anxiety` + cold `anger`, **no guilt**, no
  *moral* frustration.
- *(future)* **psychopath**: low anxiety, anger without guilt or frustration — a SEPARATE trait, not
  machiavellianism.
This is a persona-contrast assertion (per CLAUDE.md litmus), not a hard number.

---

## 2bis. Control-system reading: events are finite deposits, states are leaky integrators

Moral dynamics use the **same discrete first-order control form as every other state** (see
`docs/control_interpretation.md` for the full treatment). Nothing here is special-cased; the wording
below exists only to prevent a recurring misreading.

**An event is NOT a Dirac delta.** A moral cue (a `direct_question`, an `accusation`, a `lie_committed`)
is a **finite single-tick event deposit** into a bounded leaky state — a *discrete impulse-like* input of
bounded magnitude, never the continuous-time `D·δ(t)` of an idealized spike, and never stored *as* a spike
inside the state. The state itself is a **first-order bounded leaky integrator**:

```
x[n+1] = decay·x[n] + gain·event[n] + couplings + drift        decay = 2**(-dt/half_life), clamp [0,1]
```

- **Fast rise** is modeled by a **high finite event gain** (a big bounded jump on the tick the cue lands).
- **Slow fall** is modeled by a **long half-life** (slow decay back toward rest).
- A **one-time** event → the state rises immediately by a bounded amount, then decays along its half-life
  tail. **Repeated** events → a step-like input; the state accumulates toward a bounded level (clamped at 1).
- Unconstrained drift-only steady state is `x_inf = drift/(1−decay)` (before couplings/setpoints/clamp) —
  computed per state by the diagnostic `eval/state_response_report.py` (see `docs/control_interpretation.md`).

So "a guilt that spikes on the lie and lingers for days" is **high `g_lie_guilt` + long `serious_guilt_half_life`**,
not a delta function — fully bounded, fully decaying.

### 2bis.1 Four quantities that are easy to conflate — keep them distinct

| Name | Kind | Meaning | Lives in |
|---|---|---|---|
| `exposure_anxiety` | **global internal state** | the character's own anxiety about being exposed, accused, punished, or morally revealed — accumulates from cues, decays with a long half-life | `GLOBAL_STATES` |
| `source_threat(target)` / `expected_punishment(target)` | **relational/contextual modifier** | how threatening a *specific* observer/source is (perceived threat / fear of consequences from that person) — authored or derived `f(authority_gradient, respect, resentment)`, modulates gains; **not a stored state** | relation config / derived |
| `suspicion[target]` | **relation dimension** | how much that target currently *suspects* the character — per-source, decays with its own half-life | 4th `RELATION_DIMS` |
| `moral_tension` | **emergent conflict signal, NOT a state, NOT fear** | the normative-conflict pressure *between* the moral drives — it is the configuration of guilt vs exposure_anxiety vs loyalty vs injustice, never a single scalar and never just "fear" | emergent (read off the state vector) |

**`source_threat` vs `expected_punishment`:** same relational-modifier slot, two readings — use
`source_threat(target)` when the meaning is *perceived threat from a person/source*, and
`expected_punishment(target)` when the meaning is specifically *fear of consequences*. Both are
relation-keyed gain modulators, **never** stored states. (This replaces the earlier ambiguous
`fear(target)`.)

### 2bis.2 Moral tension is a normative conflict, not fear

`moral_tension` is the **conflict pressure between competing moral drives**, read off the state vector —
not a synonym for fear/anxiety. Its constituent pushes:

- `guilt` → pushes toward **confession / repair** (`+confess`, `+apologize`, `+repair`).
- `exposure_anxiety` → pushes toward **concealment / avoidance** (`+remain_silent`, `+avoid`, `+deflect`).
- loyalty / `trust[target]` → **reduces lying**, increases confession.
- `perceived_injustice` → **reduces guilt**, increases **anger/resentment** (shifts the response away from
  remorse toward grievance).
- `suspicion[src]` + authority → **raise exposure pressure** (source-gated `exposure_anxiety`).
- `cognitive_load_from_lies` → raises **stress** and **rumination** (the self-tightening lie noose).

The visible behavior is the *resolution* of these opposed pushes by the existing argmax selector — that is
the "tension," and it is emergent, not a stored or scripted quantity.

**Derived observable (topology fixed; weights are calibration placeholders).** When a single scalar is
needed (trace, diagnostics, the future Inn panel), `moral_tension` is **computed read-only** from the
committed state vector — never integrated, never stored as a state, never mutated:

```
P_confess = w1·guilt + w2·repair_drive + w3·trust[target]                       # pull: own up
P_conceal = w4·exposure_anxiety + w5·avoidance_drive
          + w6·source_threat(target) + w7·cognitive_load_from_lies              # pull: hide
P_defend  = w8·perceived_injustice                                              # pull: it's unfair

moral_tension = clamp01( g_mt · CONFLICT(P_confess, P_conceal) + g_inj · P_defend · guilt )
    where CONFLICT(a,b) = 2ab / (a + b + ε)        # harmonic-style: ≈0 if EITHER pull ≈0; large only if BOTH large
```

The `CONFLICT` operator is the topology decision: tension is high **only when opposing pulls are
simultaneously strong** (guilt-high ∧ exposure-anxiety-high; repair-drive ∧ avoidance-drive both high;
trust-toward-honesty fighting source_threat-toward-concealment), plus a cross-term for injustice fighting
guilt. It is therefore **not** `max`/sum of the drives and **not** equal to fear, guilt, or stress. All
`w*`/`g_*` are named config keys (`moral.tension.*`), calibrated later; with them at default the observable
reads 0. Implementation lands as a pure read-only helper (alongside `eval/observe.py`) **once the M-J.0
states exist** — it has nothing to read before then.

### 2bis.3 Half-life policy — moral states are SLOW; no new ultra-fast global state

The moral states (`exposure_anxiety`, `guilt`, `rumination`, `repair_drive`, `avoidance_drive`,
`cognitive_load_from_lies`, `perceived_injustice`) all take **long half-lives** relative to the fast
emotions (anger ≈ 30s). Every proposed moral half-life is ≥ 30 min, so **none becomes the new
`min(half_life)` → `dt` is unchanged and non-moral goldens stay bit-identical** (§review (a)).

**Do NOT introduce a new ultra-fast persistent global state** (e.g. a `startle`) to model a same-tick
shock: it would lower `min(half_life)`, shrink `dt`, and re-time the whole simulation. If a same-tick
shock is ever needed for action selection, model it as a **transient event channel** that deposits into
existing states on the frozen/update path (like `accusation` → `stress`/`anger`), **not** as a new
persistent state. (Cf. the `command_pressure`/`kindness_pressure` transient-channel pattern.)

### 2bis.4 Event → state worked examples (topology; gains are calibration placeholders)

| Event (cue channel) | Primary deposits (finite, single-tick) | Reading |
|---|---|---|
| `direct_question` / `accusation` / `suspicion_raised` | `exposure_anxiety +=`, (`accusation` also `stress/anger +=`) | being probed/accused raises exposure anxiety |
| `lie_committed` | `guilt +=`, `cognitive_load_from_lies +=`, `exposure_anxiety +=` (risk) | a fresh lie deposits guilt + maintenance load + exposure risk |
| `confess` / `repair` (action, booked in `post_effects`) | `guilt −=`, `exposure_anxiety −=` | owning up / making amends relieves guilt and exposure anxiety |
| `perceived_injustice` high (state) | shifts selection toward `resentment`/`anger`, **away from** guilt/confession | injustice converts remorse into grievance |

Each row is a finite bounded deposit on the tick the cue lands, then the standard leaky decay — never a
stored spike.

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
hidden_from      : list[AgentId]      # targets the owner is ACTIVELY hiding the secret from
known_by         : list[AgentId]      # CONFIRMED knowledge of the secret
rumor_by         : map[AgentId, float] # UNCONFIRMED belief / partial info / gossip exposure (strength)
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

### 3.4 Secret lifecycle
- `known_by` = **confirmed** knowledge of the secret. `hidden_from` = targets the owner is **actively**
  trying to hide it from. `rumor_by` = **unconfirmed/partial** belief or gossip exposure (with strength).
- **Gossip or suspicion must NOT automatically add a character to `known_by`** — they add to `rumor_by`
  and/or raise relational `suspicion`. Knowledge and pressure are distinct.
- **Confession** to a target: remove that target from `hidden_from`, add to `known_by`.
- **Public exposure** (`secret_exposed`): add all relevant witnesses to `known_by`.
- **Safe confiding**: add the confidant to `known_by`, but the harmed/deceived target may remain in
  `hidden_from`.
- **Successful repair** reduces `unresolvedness`. **Rejected repair** may reduce guilt slightly but can
  raise `shame`/`exposure_anxiety`/`resentment` depending on target response (booked via the repair
  channel's effects).
- **Inactivation:** if `hidden_from` is empty **and** `unresolvedness` is low, the secret becomes
  **inactive** — it stays in trace/history but **must not continue to drive salience loops** (salience
  impulse gated to 0 for inactive secrets).

### 3.5 LieRecord lifecycle
- `lie_created` → new `LieRecord`.
- `lie_reinforced` → refresh `maintenance_load`, increase/refresh `consistency_debt`.
- `lie_detected` → raise `detected_risk`; emit betrayal/anger/resentment/trust-damage on the target;
  may raise `suspicion` in witnesses.
- `lie_confessed` (confession involving the lie) → reduce `cognitive_load_from_lies` and
  `maintenance_load`, but may create a short-term trust shock.
- **Stale** `LieRecords` decay and become **inactive**; they remain in trace/history but no longer drive
  `cognitive_load_from_lies` or `exposure_risk`.
- **Repeated lies about the same secret accumulate `consistency_debt` on the existing record** — do NOT
  spawn a fresh unrelated `LieRecord` each time.

### 3.6 Knowledge propagation (knowledge vs. pressure)
A strict separation, important for later Inn-side multi-agent behavior:
- `known_by` = **confirmed truth**.
- `rumor_by` = **unconfirmed/partial belief**; can raise `suspicion` and gossip dynamics **without
  becoming knowledge**.
- relational `suspicion` = **pressure, not knowledge**.
- `secret_exposed` can move agents from `rumor_by` → `known_by`.
- `direct_question` and `suspicion_raised` raise **pressure** (exposure_anxiety / suspicion) **without
  necessarily revealing truth**.
- Therefore: a character can spread/react to a rumor without knowing the real secret (Welf spreads a
  half-truth), leak a detail without understanding the whole (Lutek), detect inconsistency without
  knowing the truth (Branic), or *look* suspicious from avoidance without being guilty (Cichy). None of
  these promote anyone to `known_by`.

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
         + w_pun·expected_punishment(target) · suspicion[target]
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
- guilt high ∧ shame/exposure_anxiety high → +avoid/+remain_silent (shame term inhibits confess)
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

### 8.1 Trace / schema compatibility & migration

Because `GLOBAL_STATES`, `RELATION_DIMS`, `Snapshot`, and `TickTrace` change, byte-identical legacy
output is preserved by **versioned serialization, not by avoiding the schema change**:
- Introduce **`trace_v2`** (or a moral feature flag on trace serialization). The new moral trace block
  (§8) is emitted **only** when the moral feature is enabled or `trace_v2` is requested.
- **Legacy trace mode remains available** and, when requested, **omits all moral fields** → existing
  golden hashes unchanged.
- The new relation dimension **`suspicion` defaults to 0** and **must not appear in legacy relation
  output** when the moral feature is disabled (legacy serialization writes only the original three dims).
- Frozen field orders are extended **append-only**; any appended field is documented here and has a
  **deterministic default** (moral states default 0; `rumor_by` default empty; ledger default empty).
- No schema field may be reordered or removed; migration is additive only.

---

## 9. Tests — scope-expansion within a bounded corpus (see `moral_tension_test_plan.md`)

M-J is a **deterministic moral overlay / variant axis inside the existing day and multi-day generation
strategy** — NOT an additional corpus. The M-J test strategy **keeps the total generated corpus bounded
at 1400 one-day cases and 1400 multi-day cases.** Within that fixed budget the generator emits clearly
labeled case categories (a partition of the budget, not an addition to it):

| Label | Category | Judged by |
|---|---|---|
| `M-J-LEGACY-COMPATIBILITY` | legacy / non-moral baseline | byte-identical legacy hashes (gate A) |
| `M-J-ZERO-GAIN-EQUIVALENCE` | moral enabled, all gains 0 | behavioral equivalence (gate B) |
| `M-J-MORAL-OVERLAY-ONE-DAY` | moral enabled, non-zero overlay (1-day) | moral invariants + trace explainability (gate C) |
| `M-J-MORAL-OVERLAY-MULTI-DAY` | moral enabled, non-zero overlay (multi-day) | moral invariants + trace explainability (gate C) |

The **`M-J-MORAL-OVERLAY-*` cases are the actual M-J behavioral validation** and cover both one-day and
multi-day dynamics — but are generated **within** the existing 1400 + 1400 budget, with reproducible
seeds and case IDs. Each overlay case reports its overlay type, moral config, invariant list, and
pass/fail reason.

Implementation rules:
- M-J may be implemented as a moral overlay axis over the existing day/multiday generators.
- Total generated corpus **must not exceed 1400 one-day + 1400 multi-day**. Do **not** create 1400
  additional moral cases; do **not** create thousands of hand-written tests.
- Existing non-moral corpora remain intact; existing corpus names and semantics are not replaced.
- A **small isolated micro-suite** (tens of cases) for mechanism unit-proofs is permitted and is counted
  *inside* the budget partition, not on top of it.

### 9.1 Three separate compatibility / validation gates (replaces the old "byte-identical goldens" line)

Adding moral fields to `GLOBAL_STATES`/`RELATION_DIMS`/`Snapshot`/`TickTrace` makes a single
"byte-identical with gains=0" requirement impossible. Split it into three explicit gates:

**Gate A — Legacy disabled (byte-identical):**
- Moral feature disabled → legacy trace serialization **omits all moral fields** (§8.1).
- Existing legacy goldens remain **byte-identical** where legacy trace mode is requested.

**Gate B — Moral enabled, zero-gain behavioral equivalence:**
- Moral feature enabled, **all moral gains = 0** → legacy behavior remains *equivalent* (not necessarily
  byte-identical, since `trace_v2` may carry inert moral fields):
  - same selected actions
  - same non-moral state curves
  - same non-moral relation curves
  - **no moral action selected**
  - **no ledger writes** except inert/default ledger initialization if required
- `trace_v2` may contain inert moral fields; the gate compares behavior, not raw hashes.

**Gate C — Moral enabled, non-zero overlay:**
- The `M-J-MORAL-OVERLAY-*` slice runs with a non-zero moral config overlay.
- Judged by **moral invariants + trace explainability**, **not** by byte-identical legacy hashes.
- Runs within the same bounded 1400 + 1400 corpus strategy.

Compatibility gates (A, B) are kept **separate** from moral-on behavioral validation (C).

### 9.2 Moral invariants (asserted in the overlay slice, folded into `sanity_multiday.py` + judge prompt)
guilt-prone confesses earlier; mach lies more/guilts less; close target → more guilt + trust damage;
white_lie < antisocial_lie; safe confide ↓rumination; gossip confide ↑exposure_risk; detected lie →
target anger+resentment; false accusation → accused anger/resentment/injustice; active secret
stress↑(anxious)/boredom↓(gossip); serious guilt survives night; relation damage persists;
inactive secrets / stale lies stop driving dynamics; **no degenerate loop; outburst ≠ guilt alone.**

### 9.3 Stability tests
Jury check on the expanded coupling matrix (5.1 + §6 loops) as a property test.

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
All ≥30min → none beats anger(30s); **dt unchanged**, so non-moral dynamics are preserved (Gate A
byte-identical in legacy mode; Gate B equivalent when moral-enabled at zero gain — §9.1).

## 12. Build order (vertical slices, diagram-per-slice — CLAUDE.md directive)
1. **M-J.0 guilt core — ✅ IMPLEMENTED (opt-in overlay).** `guilt`+`exposure_anxiety` states, cues
   `wrongdoing`→guilt (×`guilt_proneness`) and `probe`→exposure_anxiety (sourced → opens the reply
   window), couplings guilt→stress(+)/anger(−) and exposure_anxiety→stress(+), actions
   `confess`(relieves guilt+exposure_anxiety in `post_effects`)/`remain_silent`. **Litmus PROVEN**
   (`tests/test_moral_guilt_core.py`): a guilt-prone persona confesses, a low-guilt one stays silent on
   the SAME scenario — contrast from `guilt_proneness` alone. Diagram `docs/diagrams/moral_tension.md`.
   **Mechanism (Gate A byte-identical):** the moral layer is an **opt-in overlay**
   (`calibration/moral_overlay.yaml`, loaded via `eval/moral.py::moral_overrides` as deep-merged
   `param_overrides`). "Enabled" = the overlay supplies the moral half-lives; without it a persona carries
   NONE of the moral states/actions, so every legacy persona loads and traces **byte-identically** (proven:
   all goldens unchanged). Conditional presence is enforced by 7 small guards (yaml_io/runtime/update/
   potentials/metrics/stability) — each neutral for legacy (which has exactly the canonical states). All
   magnitudes are calibration placeholders; only the litmus ORDERING is asserted. Couplings are
   feed-forward (no moral→moral return edge), so the anger⇄stress Jury margin is unchanged.
   NOTE: one event per tick today (the deferred **M-MEM**), so the micro-scenario stages wrongdoing then
   probe on separate ticks; simultaneous moral fan-out waits on M-MEM.
2. **M-J.1 lie loop — ✅ IMPLEMENTED (internal cognitive-load loop; ledger + detection DEFERRED).**
   State `cognitive_load_from_lies` (opt-in, 6h placeholder); actions `lie` (rises with `exposure_anxiety`
   × (1−`honesty_humility`), SELF-LIMITED by −`cognitive_load` and −`guilt`) and `deflect`; `lie`
   `post_effects` book a finite `cognitive_load`/guilt/exposure deposit; couplings
   `cognitive_load→stress(+)`/`fatigue(+)` (the self-tightening noose). **Litmus PROVEN**
   (`tests/test_moral_lie_loop.py`): on the SAME probing a habitual liar (low `honesty_humility`, low
   `guilt_proneness`) LIES while a guilt-prone honest persona CONFESSES; the load is finite, bounded, and
   self-limiting (no runaway). Same opt-in overlay / byte-identical discipline as M-J.0.
   **DEFERRED (documented, not built):** `LieRecord` ledger, `consistency_debt`, and cross-agent lie
   DETECTION (lie-detected → target anger/resentment/trust-damage) — detection needs the multi-agent
   driver / M-MEM. This slice is the LIAR's internal loop only.
3. **M-J.2 repair/rumination — ✅ IMPLEMENTED (`apologize`; `confide` split DEFERRED).** States
   `repair_drive` + `rumination` (opt-in); couplings guilt→repair_drive(+), guilt→rumination(+),
   rumination→stress(+)/fatigue(+); action `apologize` keyed on `guilt`×`empathy` (the empathic-repair
   impulse) + `repair_drive`, relieving guilt/repair_drive/exposure in `post_effects`. **Litmus PROVEN**
   (`tests/test_moral_repair.py`): on the SAME scenario an EMPATHIC guilt-prone persona APOLOGIZES (makes
   amends) while a DETACHED one merely CONFESSES; rumination builds from guilt as a bounded integrator that
   couples to stress/fatigue (feed-forward → anger⇄stress Jury margin unchanged).
   **M-J.2 completions — ✅ IMPLEMENTED (`tests/test_moral_confide.py`, `data/scenarios/moral_confide.yaml`):**
   - `confide` SAFE-VS-GOSSIP split. New trait `gossip_tendency` + action `confide`, driven (spec §5.5
     shape) by `guilt × trust[confidant_source] × (1-gossip_tendency)`: a DISCREET persona unburdens to a
     TRUSTED ear present this tick → `rumination` relieved in `post_effects`; a GOSSIP-PRONE persona collapses
     the `(1-gossip_tendency)` gate (CAN'T confide safely → the secret keeps weighing) AND its
     `gossip_tendency` modulates the `probe→exposure_anxiety` gain UP (the LEAK — the only trait-modulated
     state input the engine offers is event-gains, not couplings) → more exposed. Gated on `trust`, so it is
     inert in the legacy `moral_probe` runs (interrogator trust 0). New benign mapper channel
     `confide_opportunity` (RELATIONAL, no deposit) marks who is present; the reply fires while the
     interrogation `reactive_window` is still open.
   - `reparation`. `apologize` now books a RELATIONAL `source_relations` amends (trust ↑, resentment ↓) on
     the wronged target — the moral loop closes through the RELATIONSHIP, not only inside the persona.
4. **M-J.3 accusation/scapegoat — ✅ IMPLEMENTED (accused+accuser only; witness fan-out needs M-MEM).**
   M-J.3.0 PLUMBING: GLOBAL_STATES += `perceived_injustice`, `avoidance_drive`; RELATION_DIMS += `suspicion`
   gated by `MORAL_RELATION_DIMS` (opt-in like the moral states: yaml_io/runtime/update gates keep legacy
   relation rows carrying exactly trust/respect/resentment → byte-identical); TRAIT_NAMES +=
   `injustice_sensitivity`, `conflict_avoidance`; POTENTIAL_NAMES += `avoid`, `blame_other`. M-J.3.1 CORE:
   the `accusation` mapper cue deposits `perceived_injustice` (×injustice_sensitivity), `avoidance_drive`
   (×conflict_avoidance), stress and `resentment[accuser]`; couplings `perceived_injustice→anger(+)` and the
   GRIEVANCE SWITCH `perceived_injustice→guilt(−)` ("felt justified"); `blame_other` (grievance-driven; casts
   `suspicion[accuser]`) vs `avoid` (avoidance-driven). **Litmus PROVEN** (`tests/test_moral_accusation.py`,
   `data/scenarios/moral_accusation.yaml`): on the SAME accusation a SENSITIVE persona BLAMES the accuser
   back (perceived_injustice builds, guilt suppressed, suspicion+resentment cast on the accuser) while an
   AVOIDANT persona AVOIDS; feed-forward → anger⇄stress Jury margin unchanged.
   M-J.3.2 SUSPICION CUE (`tests/test_moral_suspicion.py`, `data/scenarios/moral_suspicion.yaml`): the
   `suspicion_raised`→`suspicion_cue` channel raises PRESSURE — `suspicion[suspecter]` (relation dim) +
   `exposure_anxiety` + a conflict_avoidance-gated `avoidance_drive` deposit — WITHOUT creating guilt or
   truth ("looks suspicious from avoidance without being guilty"; spec §3). `false_accusation` is wired as
   the same accused-side `accusation` channel (vocab alias). NOTE: the diagram's `exposure_anxiety→
   avoidance_drive` edge is realized as a trait-gated cue GAIN, not a standing coupling (couplings can't be
   trait-modulated; an always-on edge would fire `avoid` in the probe litmus).
   M-J.3.3 WITNESS FAN-OUT + FALSE-ACCUSATION DISCOVERY — ✅ IMPLEMENTED on **M-MEM** (the R7 unblock;
   `tests/test_moral_witness_fanout.py`, `data/scenarios/moral_public_accusation.yaml`,
   `moral_false_accusation_discovered.yaml`):
   - **Public-accusation fan-out (accused side).** A public charge lands as ONE M-MEM tick carrying the
     accuser's `accusation` + each witness's `suspicion_raised`; the accused grows wary of EVERY witness at
     once (`suspicion[witness_i]` all rise on the same tick) while `perceived_injustice` builds. No new
     engine code — the cues exist; M-MEM delivers them simultaneously.
   - **False-accusation discovery (accuser side).** New SELF cue `false_accusation_discovered` → `guilt`
     (×`guilt_proneness`: a guilt-prone accuser feels remorse, a callous one barely does) + `exposure_anxiety`
     (exposed as a false accuser); the crowd turning is the witnesses' `suspicion_raised` fanned onto the
     accuser on the discovery tick. **Litmus PROVEN.** Byte-identical (cue opt-in); Jury margin unchanged.
   `blame_shift` remains a `lie_type` for the M-J.4 ledger, not an accusation event.
5. **M-J.4 full ledger + calibration grid + scoped corpus.** Decomposed into sub-slices:
   - **M-J.4.0 ledger plumbing — ✅ IMPLEMENTED (`tests/test_moral_ledger_plumbing.py`).** `Secret`/`LieRecord`/
     `MoralLedger` data model (spec §3.1–3.2); `moral_ledger` field on `PersonaRuntime` + `Snapshot`,
     DEEP-COPIED in `freeze()` (read-only for the tick); serialized into the trace ONLY when non-empty
     (`debug._ledger_dict`, sorted-id canonical order) → legacy goldens byte-identical. No lifecycle yet.
   - **M-J.4.1 LieRecord lifecycle + consistency_debt — ✅ IMPLEMENTED (`tests/test_moral_lie_ledger.py`).**
     `lie`/`deflect`/`blame_other` book a LieRecord via `action_params[action].ledger` (post_effects phase,
     `simulation._update_ledger`): one record per TARGET (`lie:<target>`), reinforced by repeated lies — debt
     accrues on the SAME record, never one-per-lie (spec §3.5). `consistency_debt`/`maintenance_load` are
     mini-integrators that DECAY each tick by `ledger_params.lie_decay` (stale lies fade). `blame_other`
     records the `blame_shift` lie_type, `deflect` an `omission`. Opt-in → legacy byte-identical.
   - **M-J.4.2 lie detection — ✅ IMPLEMENTED (`tests/test_moral_lie_detection.py`).** `lie_detected`→
     `betrayal` mapper channel (RELATIONAL, source = the other party). TARGET side: overlay gains
     anger/frustration + `resentment[liar]`(+) + `trust[liar]`(−) — discovering a lie collapses trust and
     breeds a grudge (spec §5.6). LIAR side: `simulation._book_detection` raises `detected_risk` on the
     persona's matching `LieRecord` (`lie:<detector>`) by `ledger_params.detected_risk_on_detect`, and the
     caught liar FEELS it — `exposure_anxiety` + `guilt` spike (`detected_exposure`/`detected_guilt`), GATED
     on holding the record so a betrayed target picks up neither. A betrayed target (no record) is a ledger
     no-op. Opt-in → legacy byte-identical.
   - **M-J.4.3 Secret lifecycle — ✅ IMPLEMENTED (`tests/test_moral_secret_lifecycle.py`).** Secrets are
     authored in the scenario (`initial_overrides.secrets`) and seeded into the ledger by `init_runtime`
     (inert without the overlay). `simulation._update_secrets` (post_effects phase): decays `salience`; a
     `secret_cued` reminder raises salience (gated to 0 for an inactive secret); `secret_exposed` fills
     `known_by` with the witnesses and EMPTIES `hidden_from` (publicly known → no longer hiding); an ACTIVE
     secret's salience weighs as `stress`. INACTIVATION (spec §3.4): active iff `hidden_from` non-empty OR
     `unresolvedness ≥ inactive_unresolved_floor` — once inactive, salience is neither raised nor weighs.
     Opt-in (ledger empty / no ledger_params → legacy byte-identical).
     **A3 — minor/serious guilt split (`tests/test_moral_guilt_weight.py`, spec §11):** rather than two guilt
     states, an ACTIVE secret RE-INJECTS guilt each tick by `secret_weight_to_guilt · moral_weight · salience`
     (in `_update_secrets`). A SERIOUS unconfessed wrong (high `moral_weight`) keeps guilt alive against decay
     → it lingers (the judge-validated 72h feel) while the base half-life stays minor-appropriate (18h); a
     minor wrong fades; confession/exposure inactivates the secret → the drip stops → relief. Opt-in.
   - **M-J.4.4 calibration grid + scoped corpus.** Two parts:
     - *Deterministic gates* — ✅ IMPLEMENTED (`tests/test_moral_gates.py`): **Gate A** (legacy byte-identical,
       via `test_tick_golden.py`); **Gate B** zero-gain behavioral equivalence (`eval.moral.zero_gain_overrides`:
       moral enabled but all gains 0 → same actions + same non-moral state/relation curves + no moral action +
       empty ledger); a couple of consolidated **Gate C** §9.2 invariants (outburst ≠ guilt alone; moral states
       bounded). Stability (§9.3) is asserted per-slice (`jury_margin > 0`; moral edges are feed-forward).
     - *Calibration grid + judged corpus* — ⏳ PENDING (LLM-judge / eval-harness work, §10): grid over the
       overlay half-lives/gains, and the labeled `M-J-MORAL-OVERLAY-*` categories within the 1400+1400 budget
       scored by the blind judge. All `moral_overlay.yaml` magnitudes remain PLACEHOLDERS until this runs.

   **Post-review corrections (2026-06-24 audit, `tests/test_moral_ledger_gaps.py`):**
   - `confess` now discharges `cognitive_load_from_lies` AND RESOLVES the target's LieRecord (a `ledger:
     {resolves: true}` block reduces debt/load) — spec §3.5 `lie_confessed`, previously unimplemented.
   - The ledger writes (`_update_ledger`/`_book_detection`/`_update_secrets`) were moved OUT of the selector
     `else` branch so they run on EVERY tick, including the SEEKING→BUSY ENGAGE branch (a lie/secret now
     decays and a detection lands even on an activity-start tick).
   - Ledger iteration is now sorted-by-id (deterministic) in `_update_ledger`/`_update_secrets`.
   - RESERVED fields (authored/serialized but not yet engine-driven, pending M-J.4.4): `LieRecord.
     {plausibility, witnesses, secret_id}`, `Secret.{exposure_risk, confession_threshold}` — documented in
     `engine/schema.py`. Coverage added: multi-target separate records, decay trajectory, `complexity`
     booking, the `unresolvedness ≥ floor` inactivation branch, multi-secret stress stacking.

## 13. Self-review checklist (to assert at each slice's Definition of Done)
Architecture: no LLM in loop ✦ no behavior-shaping literals in code ✦ all tunables in config ✦ synchronous
single-commit preserved ✦ no event→action scripting (potentials only) ✦ moral layer coupled to existing
states ✦ trace explains every moral outcome ✦ ledger read-only in `update`, written only in `post_effects`
✦ no RNG / deterministic potentials ✦ Jury-stable coupling matrix ✦ diagram (both forms) synced with code.

**Compatibility:**
- [ ] legacy/disabled mode preserves **byte-identical** goldens (Gate A)
- [ ] moral-enabled + zero gains preserves non-moral behavior (Gate B: same actions/curves, no moral
      action, no ledger writes beyond inert defaults)
- [ ] `trace_v2` / moral trace mode is explicit; legacy trace omits moral fields
- [ ] every new schema field (moral states, `suspicion`, `rumor_by`, ledger) has a deterministic default

**Latency:**
- [ ] one-tick moral latency documented (§1.1)
- [ ] ledger not mutated before `post_effects`
- [ ] no same-tick ledger mutation hidden in `potentials`

**Corpus:**
- [ ] `M-J-MORAL-OVERLAY-ONE-DAY` (short label `M-J-ONE-DAY-700`) = 700 deterministic moral-on cases,
      generated **within** the 1400 one-day budget (not on top)
- [ ] `M-J-MORAL-OVERLAY-MULTI-DAY` (short label `M-J-MULTI-DAY-700`) = 700 deterministic moral-on cases,
      generated **within** the 1400 multi-day budget (not on top)
- [ ] total generated corpus ≤ 1400 one-day + 1400 multi-day; existing non-moral corpora intact
- [ ] each overlay case has reproducible seed + case id + labeled overlay type/config/invariants/result

**Knowledge lifecycle:**
- [ ] `known_by` = confirmed truth; `rumor_by` = partial/unconfirmed; `suspicion` = pressure not knowledge
- [ ] confession/exposure/confiding update knowledge correctly (§3.4–3.6)
- [ ] inactive secrets and stale lies stop driving dynamics

**Trait semantics:**
- [ ] `empathy` is a separate trait (not aliased to `gratitude`)
- [ ] `threat_sensitivity` may still serve anxiety semantics
- [ ] trait de-dup map remains documented
- [ ] `honesty_humility` (lie-as-bad-habit) and `machiavellianism` (psychopathic, guilt-suppressing)
      kept as two separate knobs; differentiation documented in §2.3
- [ ] **machiavellian persona: guilt-no / anxiety-yes / cold-anger** — high-`machiavellianism` shows no
      `guilt` and no *moral* `frustration` (cool syndrome), but DOES show `exposure_anxiety`/`stress`
      and cold `anger` on exposure (NOT fearless — that's psychopathy, a future trait). Contrast vs a
      habitual liar (`honesty_humility` low) who shows guilt + moral frustration on the same event
- [ ] traits introduced per-slice (M-J.0 = empathy/guilt_proneness/shame_sensitivity/honesty_humility),
      not all nine at once

Coupling coverage + test/eval checklist: as enumerated in the original proposal, asserted via §6 edges and
§9 invariants.

---

## 14. Engine / Inn boundary (scope note)

**This document is engine-only.** `equilibrium-inn` must NOT implement moral equations. The Inn only:
consumes the engine's public surface, configures moral profiles/scenarios, renders moral traces, and
validates the observatory scenario. The Inn branch is handled **separately, after** this engine feature
has a stable public surface and a commit pin. No moral dynamics live in the Inn.
