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
- [ ] `M-J-MORAL-OVERLAY-ONE-DAY` = 700 deterministic moral-on cases, generated **within** the 1400
      one-day budget (not on top)
- [ ] `M-J-MORAL-OVERLAY-MULTI-DAY` = 700 deterministic moral-on cases, generated **within** the 1400
      multi-day budget (not on top)
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

Coupling coverage + test/eval checklist: as enumerated in the original proposal, asserted via §6 edges and
§9 invariants.

---

## 14. Engine / Inn boundary (scope note)

**This document is engine-only.** `equilibrium-inn` must NOT implement moral equations. The Inn only:
consumes the engine's public surface, configures moral profiles/scenarios, renders moral traces, and
validates the observatory scenario. The Inn branch is handled **separately, after** this engine feature
has a stable public surface and a commit pin. No moral dynamics live in the Inn.
