# RPG Persona Dynamics Engine — MVP specification (merged document)

> **One source of truth.** This document replaces and merges: `rpg_persona_dynamics_mvp_spec_for_claude.md`
> (the original sketch), `rpg_persona_dynamics_architektura_i_kontrakty.md` (contracts + dynamics) and
> `CLAUDE.md` (frozen decisions). On any conflict with any of them — **this document prevails**. The
> original spec remains only a source of example numeric coefficients.
>
> Scope principle: **less is more.** The MVP contains only what does something; everything else is named
> and deferred to stage 2 (section 13).

---

## 0. Guiding principle

Visible NPC behavior **emerges from the dynamics of internal states** (an analogy to a control system),
not from scripts. Every member is a **pure function** with explicit input/output; state mutates in one
place only. Three keywords: **frozen snapshot**, **synchronous update**, **filter per channel**.

> A persona = a static configuration of sensitivities, decays, couplings, preferences, relational
> filters and thresholds. Behavior emerges from the dynamics of those states, relational memory,
> history, feedback loops and threshold crossings — fully reproducible from the debug trace.

---

## 1. Architecture invariants (frozen)

- **Synchronous update.** All equations read a frozen snapshot of the state from the start of the tick;
  deltas computed together; commit together. Equation order **does not affect the result**.
- **Filter per channel, not per event.** One event decomposes into many channels; each routed by its
  class: relational → filter per source, affinity → per object, physiological → no filter.
- **One source of truth for the equations.** The `input→state` and `state→state` equations exist only in
  `update`. Descriptions elsewhere are descriptions, not a second application (double-counting risk).
- **Clamps.** `clamp01` after every state commit; `clamp_signed` [−1..1] for signed values.
- **Integrators with decay.** Every state is a one-pole low-pass filter; `decay` = the time constant.
  **Resonance/oscillation is an emergent property of a loop of ≥2 states**, not a property of a single input.
- **Loop stability.** The choice of feedback gains must keep the poles of the linearized loops inside the
  unit circle (unless a limit cycle is intended).
- **State mutates in one place** (`update.commit`) + the selector's small `post_effects` (section 6/7).
- **Generic element + neutral defaults** (full contract: section 14). All states are instances of **one**
  integrator; a "role" (emotion / accumulator / homeostat / memory) = a **parameter preset**, not a
  separate block type. Whatever an instance does not use → a neutral value (`drift=0`, `coupling=0`,
  filter = identity). Wiring is **sparse**, declared in config — not a dense matrix. Drive and relation
  are a core + a thin **capability via a uniform interface**, with no framework built ahead of need.

---

## 2. Tick and time

- **Tick rule (sampling theory):** `dt = min(half_life) / 10` — take the fastest relevant phenomenon
  (the shortest half-life, usually the fastest emotion) and sample ~10× faster (an engineering variant of
  Nyquist; the formal minimum is 2×, ~10× gives smooth curves and headroom).
- **Global `time_scale` (optional, default 1.0 = identity).** Multiplying **every** half-life by a common
  factor `k` is a pure clock reparametrization: `dt = min(k·half_life)/10 = k·dt`, so every per-tick
  `decay = 2**(-dt/half_life)` is **invariant** and the tick-by-tick trace is **bit-identical** — only the
  seconds a tick represents stretch by `k`. This turns the placeholder-fast seed emotions (anger half-life
  ≈30 s) into a believable day (`k≈80` → anger ≈40 min, an ~8 h waking day) without touching any relation,
  gain, threshold, or ordering. It is config (`tick.time_scale`), default 1.0 so the frozen golden/litmus
  path is unchanged; only the eval/story path opts in (`load_eval_persona(..., time_scale=k)`). The
  `dt = min(half_life)/10` invariant still holds exactly (half-lives are scaled, then `dt` is re-derived).
- **1 tick = `dt` seconds of game time.** Cooldowns, activity durations and event intervals are counted
  in ticks, interpreted in seconds via `dt`.
- **Reparameterization:** `decay = exp(−ln2 / half_life)`; half-lives are given in game-time units, the
  shortest sets `dt`. The tick is not picked by hand — it falls out of the fastest time constant.
- **Loop over all ticks** (a consequence of the rule: the fastest phenomenon changes slowly per tick, so
  the loop is cheap and accurate). The `decay**Δt` jump is only for very long game-time skips, as a later
  optimization.
- **Note:** revise `dt` when a phenomenon faster than the current fastest emotion is added (`dt` always
  drops to the fastest element).

---

## 3. Canonical types (shared vocabulary)

```text
AgentId    = str          # "player", "npc_marek", "faction_mages"
TargetId   = str          # object/topic/faction: "cabbage_soup", "honor"
Polarity   = positive | negative | neutral
InputClass = relational | affinity | self
Mode       = IDLE | SEEKING | BUSY | COOLDOWN   # SEEKING (M7 Step 2): looking for an activity, pre-engagement
```

```text
RawEvent:
  type, t, source: AgentId|None, target: AgentId|None,
  item: TargetId|None, topic: TargetId|None, faction: TargetId|None,
  intensity: float[0..1], context: dict   # public, forced, has_authority, ...

HistoryFeatures:
  repetition_score, novelty_score, same_event_count_recent/long,
  same_item_count_recent/long, time_since_last_same_event,
  recent_positive_contact, recent_negative_contact

SemanticInput:                              # ONE tagged channel
  name, value (float; preference_match [-1..1]),
  cls: InputClass, source: AgentId|None, target: TargetId|None, polarity
SemanticInputVector  = dict[str, SemanticInput]   # from the mapper (base)
EffectiveInputVector = dict[str, SemanticInput]    # after the filters

GlobalState [0..1]:  hunger fatigue boredom stress frustration anger satisfaction self_control
RelationState [0..1] (per source):  trust respect resentment
Relations   = dict[AgentId, RelationState]
AffinityMap = dict[TargetId, float[-1..1]]

Traits (immutable [0..1]):  reactivity patience base_self_control need_for_control pride
                            novelty_seeking threat_sensitivity trust_disposition gratitude stoicism

DerivedSnapshot:                            # computed every tick, NOT state
  affective_bias: dict[AgentId, float[-1..1]]
  irritability, effective_self_control, dissatisfaction: float[0..1]
  negative_bias:  dict[AgentId, float[0..1]]
  urge_boredom, urge_fatigue: float[0..1]   # proactive drives (section 8)

StateDelta:  global: dict[str,float],  relations: dict[AgentId, dict[str,float]]

PotentialVector [0..1 after clamp]:  complain outburst cold_response cooperate refuse
ActionId = neutral | positive_response | cooperate | complain | cold_response | refuse
         | outburst | hostile_action            # reactive (hostile = top range of outburst)
         | seek_stimulus | rest                  # proactive (activities with a duration)

ActionSelection:  action, score, kind: reactive|proactive|continue|idle,
                  interrupted: bool, post_effects: StateDelta, explanation

PersonaConfig:  id, traits, initial_global_state, initial_relations, affinities,
                half_lives, gains, thresholds, drives(registry), action_params
Scenario:       id, persona, initial_overrides, events: list[RawEvent]
PersonaRuntime: mutable{global_state, relations, mode, active_action, busy_target}
                immutable{traits, affinities, decay, gains, thresholds, drives}
                bookkeeping{history_log, cooldowns}
```

---

## 4. States (MVP = 11; + stage-2 decoupled drive states)

**Global (8, MVP):** hunger, fatigue, boredom, stress, frustration, anger, satisfaction, self_control.
**Relational, per source (3):** trust, respect, resentment.
**Stage-2 decoupled drive states (added later, each joins NO coupling → no new pole, dt unchanged):**
`duty` (the proactive-authority drive, §8) and `sleep_pressure` (the night/sleep drive, §8). They are
generic integrators (a role = a preset of parameters, not a new type) and sparse by default (drift 0 unless
a persona/world activates them), so the MVP litmus/goldens are unchanged.

Special roles: `boredom` and `fatigue` are **also drives** (section 8). `satisfaction` = the reward
channel. `stress` = an aggregating hub (hunger/fatigue → stress → irritability). `hunger` in the MVP is
only a modulator (the `seek_food` drive is deferred).

**Derived — per tick, NOT states:** effective_self_control (= self_control − the effect of
fatigue/stress), irritability, negative_bias (per source), affective_bias (per source), dissatisfaction,
urge_boredom (= f(boredom · novelty-tempo, − light fatigue brake)), urge_fatigue (directly from fatigue).
*A drive/urge is not a state* — the integrator of the boredom urge is the existing `boredom` (drive =
state in its second role, §8): the urge reads `boredom` **DIRECTLY**, not via `frustration`. **D5:** the
boredom term is modulated by `novelty_seeking` (`nov_factor = 1 + k·(novelty − ref)`, default identity) so
the time-to-seek from idle is ordered by the trait — a novelty-seeker acts on boredom sooner, a low-novelty
stoic later or never. (The fatigue brake is kept LIGHT: the `fatigue→rest` drive already diverts a tired NPC,
so a strong brake only made the boredom urge unreachable. Magnitudes are calibration placeholders.)

**Bookkeeping — NOT states:** mode (IDLE/SEEKING/BUSY/COOLDOWN/SLEEP), active_action + busy_target, cooldowns, log.

**Traits (config, filters — NOT states):** patience, pride, need_for_control, base_self_control,
novelty_seeking, stoicism, reactivity, threat_sensitivity, gratitude, trust_disposition.

**Decay dynamics (non-uniform):**
- hunger, fatigue — **accumulate** (accumulators), knocked down by eating/resting; not to zero.
- boredom, stress, frustration, anger, satisfaction — **decay to 0** with their own time constants.
- self_control — rests at `base_self_control`; a momentary drop is carried by the derived eff_self_control.
- trust, respect, resentment — **memory, not mood**: very slow decay toward neutrality, or none.

---

## 5. Input channels (frozen — ≈24) and filtering

The mapper decomposes one event into many tagged channels. The **class** tag decides the routing.

**Physiological / world (self, no filter):** `food_nutrition`→hunger↓ · `rest`→fatigue↓ ·
`pain`→stress↑ · `repetition`→boredom↑ · `novelty`→boredom↓ · `uncertainty`→stress↑ ·
`night`→sleep_pressure↑ (the `nightfall` signal, M7.5 Part B) · `weather`→frustration↑,stress↑ (an
environmental stressor, e.g. cold rain on a long watch — wears at the temper and erodes self-control a
touch, so the SAME later provocation can tip a rain-worn persona that a dry one would shrug; not a
provocation, opens no reactive reply). `social_exposure` = a context modifier (public amplifies the
relational channels).

**Affinity (target = object):** `preference_match` [−1..1] → satisfaction↑ / frustration↑.

**Relational (source = agent):** `insult`→anger↑,frustration↑,resentment↑ · `praise`→satisfaction↑,respect↑ ·
`help`→trust↑,resentment↓ · `harm`→anger↑,resentment↑,stress↑ · `gift`→satisfaction↑,trust↑ ·
`command` (merged with `request`, an authority parameter; **MVP-active**)→frustration↑ at low respect, **and a transient `command_pressure`** — the obedience signal `cooperate`/`refuse` read this tick (§8); `control_loss` (forced compliance) deferred ·
`ignore`→resentment↑ · `attention`→satisfaction↑ · `promise_kept`→trust↑,resentment↓ ·
`promise_broken`→trust↓,resentment↑,anger↑ (betrayal amplification) · `boundary_violation`→resentment↑,anger↑ ·
`care_signal`→trust↑ · `apology`→resentment↓ (rebuilds trust) · `competence_signal`→respect↑ ·
`repeated_failure`→respect↓,frustration↑ · `control_loss`→frustration↑,stress↑,resentment↑.

**Routing rule (dispatch, per channel):**
```text
if k.source: relation_filter(k, relations[k.source], derived_pre)   # affective_bias, betrayal exception
if k.target: affinity_filter(k, affinities[k.target], context)      # object valence, phobias (stage 2)
if not k.source and not k.target: identity                          # pass through unchanged
```
A channel may have both a source and a target (e.g. "forced to eat a spider") → both filters, order
relational→affinity. Relational effects of object channels (e.g. resentment) are booked on `relations[source]`.

**Shared per-entity resolver (`filters.py`).** Both stages above compute the *same* modulation shape —
*scale a signal by a per-entity value, identity unless populated* — so it lives once, in a small pure
kernel: `lookup(entity, table) → scalar` (`0` = neutral/unknown) and `factor(value, gain, sign) =
1 + gain·sign·value` (`1.0` = identity, the default when the gain is `0` or the entity is absent). The
relation stage passes `sign = polarity_sign(channel)`; the affinity stage passes `+1` and clamps its
result. `lookup` is the **seam** whose internals the **affinity FIELD** (next subsection) replaces
without moving a call site (the earlier discrete category→specific hierarchy idea is SUPERSEDED by the
field — nearness in the embedding space *is* the grouping). The resolver owns the per-entity gain ONLY —
NOT the appraisal gates (`command/kindness/bystander_pressure`, §8), which are a separate "what kind of
event is this" question. Diagram: `docs/diagrams/filters.md`.

**Affinity FIELD over an embedding space — the generalized `lookup` (staged; design of record:
`Ideas/affinity_field_unification.md`, private overlay).** Stop storing one valence row per entity:
place every entity — **object AND agent** — as a **coordinate in a small (~3D) vector space** (frozen
config; any embedding *generation* by a model is an OFFLINE perception-seam step cached to config, never
in the tick), define a **sparse set of authored anchors** (coordinate + valence), and resolve any
entity's valence as a **cosine-similarity-weighted blend of the anchors**:

```text
w_a        = exp( (cos(x_e, x_a) − 1) / tau )          # similarity kernel, tau = temperature
valence(e) = Σ_a w_a·v_a / (Σ_a w_a + w_0)             # kernel regression with a NEUTRAL PRIOR
```

- **Equation shape is topology — frozen now;** `tau` (similarity fall-off), `w_0` (the neutral-prior
  weight: an entity far from every anchor reads ~0, exactly the `lookup` "unknown = neutral" contract)
  and the overall gain are **calibration placeholders**. Coordinates, anchor placements and anchor
  **valences** are **authored** (they are personality/world design, not control gains).
- **Grouping is EMERGENT from the full 3D layout** (decided): no dimension is reserved as a hand-set
  "group vicinity" knob — clusters arise from coordinate placement alone (an unlabeled daisy placed near
  the "flowers" anchor reads `+`; a rose in a sub-region reads `++`; "dislikes animals but likes dogs" =
  a positive dog anchor inside a negative animal region). Generalization by similarity replaces both the
  flat table and any discrete IS-A tree — no enumeration, no type-`if`s.
- **Neutral default / bit-identical staging:** an **empty field (zero anchors) = identity** — the same
  neutral default as the dict lookup, so the swap ships inert and anchors are opt-in behaviour (the
  filter-unification migration discipline).
- **Feed-forward ONLY:** the field scales inputs, seeds state, or adds a prior; it introduces **no
  integrator and no loop** — the pole/Jury discipline is untouched (assert + test, including people
  option B below).
- **Debuggability is a requirement:** the resolver logs the contributing anchors + cosine weights
  ("−0.31: cos 0.8 from 'snakes'(−0.8), 0.3 from 'pets'(+0.5)") so the field stays as traceable as the
  table it replaces.
- **PEOPLE (the hard part — objects are a pure feed-forward gain, people carry dynamic relations).**
  Staged fork, decided: **(A) first — field as INITIAL CONDITION**: proximity to anchors *seeds* a
  stranger's trust/respect/resentment ("a new noble starts disliked"), then the normal dynamics take
  over; existing seeded personas unaffected → goldens hold. **(B) is the stated TARGET — field as a
  PERSISTENT PRIOR**: a standing feed-forward bias alongside the learned relation each tick ("an
  instinctive distaste for his kind that lingers even as I come to trust *him*"); implemented only after
  (A) validates. **(C) replacing the relation dims is REJECTED** — it would gut the core dynamics.
- **Implementation order:** (1) the field as the OBJECT resolver behind `filters.py::lookup` (empty =
  bit-identical; then a roses/flowers + dogs/animals proximity demo with tests) → (2) people (A) →
  (3) people (B). Composes with the deferred frequency axis: the field gives `gain(entity)`; frequency
  would make it `gain(entity, recent_rate)` — orthogonal.

**Degraded / deferred:** `ignored_preference` **is not a channel** — it is derived from `preference_match`
(negative) + `repetition` (no model of desires in the MVP). `threat` is **deferred to stage 2** with
`fear`. `request` is **merged** into `command`. The betrayal exception keys on `trust` in the MVP
(attachment = stage 2). Phobias (`preference_match` very negative → fear) = stage 2.

---

## 6. Member contracts (input / output / responsible for / does NOT do)

- **M0 yaml_io** — In: YAML paths. Out: validated PersonaConfig, Scenario. Parsing + schema validation +
  defaults + hard errors. NOT: dynamics logic.
- **M1 PersonaRuntime.init** — In: PersonaConfig + overrides. Out: PersonaRuntime (mode=IDLE, empty log,
  zero cooldowns, clamped overrides). NOT: processing events.
- **M2 history.analyze** — In: log + current event + t. Out: HistoryFeatures. Pure, deterministic; does
  NOT mutate the log/state; does NOT interpret semantics.
- **M3 mapper.map** — In: RawEvent + PersonaConfig + HistoryFeatures. Out: SemanticInputVector (tagged,
  base). Decomposition into channels + source/target/cls tags + `preference_match=affinity[object]` +
  repetition/novelty. Does NOT apply relational/affinity weights; "semantic and dumb".
- **M4 filters (relation→affinity)** — In: SemanticInputVector + Relations + AffinityMap + derived_pre +
  context. Out: EffectiveInputVector. relation_filter: affective_bias, amplification/damping of source
  channels, betrayal exception (on trust). affinity_filter: object valence. Each touches only the channels
  with its tag. Both call the shared per-entity resolver `filters.py` (`lookup` + `factor`, identity
  default; §5). Does NOT update state.
- **M5 derived.compute** — In: GlobalState + Relations + Traits (from one snapshot). Out: DerivedSnapshot
  (incl. urge_boredom, urge_fatigue). Pure; NOT a state. **Called 2×/tick** (`pre` after snapshot, `post`
  after update).
- **M6 update.compute ★** — In: snapshot + EffectiveInputVector + derived_pre + Traits + mode. Out:
  StateDelta. **The only place state evolves.** Computes synchronously: `new = clamp(decay*old + drift +
  Σ gain*input + Σ coupling*state_snapshot + BUSY_effects)`. Does NOT select an action; does NOT filter;
  does NOT commit.
- **M7 potentials.compute** — In: state' + relations' + Traits + derived_post + **command_pressure**
  (transient — this tick's `command` channel × authority, carrying `command.source`; `0` when no order).
  Out: reactive PotentialVector, **clamp [0..1]** (a shared scale with the thresholds). Does NOT know
  thresholds; does NOT select.
- **M8 selector.select** — In: potentials + urges + thresholds + mode + cooldowns + state' + traits. Out:
  ActionSelection (action, kind, interrupted, post_effects). **The shared selector of both paths +
  arbitration** (section 7/8). Returns one action; post_effects are deltas. Does NOT commit itself.
- **M9 simulation.run_scenario** — In: PersonaConfig + Scenario. Out: SimulationResult (trace + states +
  actions). The tick loop, commit + clamp, mode/cooldowns, debug.emit. **The only runtime mutator.**
- **Maux clamp/debug** — `clamp01`, `clamp_signed`; DebugTrace → dict/JSON/Markdown (the full set of
  intermediate tick results).

---

## 7. Dynamics — the canonical tick order

`derived_pre` = how the character **interprets** a stimulus (based on how it felt before).
`derived_post` = how it feels **after** the event → what it is inclined to do. Two roles, not duplication.

```text
TICK(t):
  1. snapshot = freeze(global_state, relations)                 # values from the start of the tick (FROZEN)
  2. derived_pre = derived(snapshot, traits)                    # bias, eff_self_control, urge_*, ...
  3. eff = ∅
     if event at t:
        feats = history.analyze(log, event, t)
        raw   = mapper.map(event, persona, feats)               # tagged channels
        eff   = affinity_filter(relation_filter(raw, snapshot.relations, derived_pre, ctx), affinities, ctx)
  4. delta = update.compute(snapshot, eff, derived_pre, traits, mode, recovering)   # SYNCHRONOUSLY
        # new = clamp( decay*old + drift + Σ gain*input + Σ coupling*state_snapshot
        #              + (when BUSY) activity effects: −drive relief, +fatigue cost,
        #                +reward·affinity→satisfaction, −urge expenditure
        #              + (when IDLE & unprovoked) idle_recovery: settle toward calm (stress/anger−), D11 )
        #   recovering = (mode==IDLE AND NOT recent_provocation): ambient homeostasis -- the character
        #   settles when nothing is happening. Non-seekers have no other intraday recovery path (they never
        #   engage a stress-relieving activity); not applied while active or provoked (burst litmus untouched).
  5. commit(delta); clamp → state', relations'
  6. derived_post = derived(state', traits)
  7. potentials = potentials.compute(state', relations', traits, derived_post, command_pressure)   # reactive, clamp [0..1]
     #   command_pressure = this tick's command channel (transient; 0 if no order) -> obedience potentials
     urges      = { boredom: derived_post.urge_boredom, fatigue: derived_post.urge_fatigue }
  8. sel = selector.select(...):                                # SHARED SELECTOR + ARBITRATION
        max_react = argmax{p ∈ potentials : p ≥ theta_react(p)} if recent_provocation else none
        #   recent_provocation = a PROVOKING event this tick OR a provoking event within reactive_window_ticks
        #   (D5 step 1c + D11). A reactive REPLY needs something to reply to; ambient idle drift must not fire
        #   a reaction at thin air, AND a BENIGN gesture must not either ("snaps at a meal", D11). An event
        #   provokes iff (1) it raises anger/frustration (insult, order, disliked dish), OR (2) it is a
        #   gesture from a RESENTED source (resentment[source] >= theta_provocation -- a kindness from someone
        #   you blame still galls). A liked meal / help from a non-resented source is NOT a provocation.
        if mode == BUSY:
            if  satisfaction ≥ theta_satiation OR fatigue ≥ theta_fatigue_end → END (→COOLDOWN)   # activity ends
            elif max_react ≥ theta_interrupt                       → INTERRUPT (→COOLDOWN), action=reactive
            elif max_react ≥ theta_react                           → reactive "in passing", activity CONTINUES
            else                                                   → continue the activity
        elif mode == COOLDOWN:
            if max_react ≥ theta_react → action=reactive           # a reaction works during cooldown too
            else                       → neutral/positive_response  # start blocked
        elif mode == SEEKING:                                      # M7 Step 2: looking for an activity
            if max_react ≥ theta_react → action=reactive (interrupt the search → IDLE)
            else                       → continue seeking (seek_stimulus; +frustration/tick, the looking cost)
        else (IDLE):
            if   max_react ≥ theta_react    → action=reactive       # the world has priority
            elif max(urges) ≥ theta_start   → START strongest drive: a SEEKING drive (seek_stimulus) → SEEKING
                                              (intent); a self-supplied drive (rest) → BUSY directly
            else                            → neutral/positive_response
  8b. M7 Step 2 ENGAGE/TIMEOUT (orchestrator, sees the event+clock):
        if mode==SEEKING and event.type=="activity" → ENGAGE: mode→BUSY, active_action=context.kind
                                                       (self_activity|external), engaged_novelty=context.novelty
        elif mode==SEEKING and (t − seeking_since) ≥ seeking_timeout_ticks → give up → IDLE
  9. commit(sel.post_effects); clamp → state''                  # reaction cost, mode change, cooldown
 10. log.append(event); cooldowns.tick(); COOLDOWN→IDLE when zero; debug.emit(...)
```

**Clamp:** states/relations `clamp01` (steps 5 and 9); signed `clamp_signed`; potentials `clamp01` (M7).
**Selection rule vs thresholds:** threshold = "is it in the running", argmax = "which of the admitted ones
is strongest" (`cold_response` 0.50 with potential 0.6 beats `outburst` 0.75 with potential 0.55 — by design).
**Suppression (outburst→cold_response):** keys on stoicism + respect + eff_self_control (no fear); a
`suppressed_anger` bump / delayed burst = **stage 2**.
**Gain modulator (`mod`):** an input→state gain MAY carry a trait modulator `mod = 1 + k·(trait − ref)`
(sparse; default `mod = 1` = identity; anchored at `ref` so a reference-trait persona keeps the calibrated
gain exactly). First instance: **pride → insult-anger** (wound-sensitivity) — a proud persona's insult
deposits *more* anger, a low-pride one *less*, so the differentiated sting EMERGES from a trait rather than
from a coincidence of stoicism on the output side. `k` is a **believability-strength** parameter: the
ORDERING (anger rises with pride) is behavior-authorized, but its MAGNITUDE has no sharp behavioral crossing
to pin it, so it is a **bounded placeholder pending Level-3 / LLM-comparative validation (§17)**, NOT a
min-margin-calibrated value. NOTE (measured): this does NOT retire the prisoner's temporary per-persona cold
threshold — the prisoner's resentful cold is intrinsically lower than some personas' ordinary public-insult
cold, so it is not globally separable; the two are independent problems.

---

## 8. Action layer — two paths, one selector

The two paths differ by their **trigger**; both fall into **one selector** and share the same state.

**Reactive (response to the world).** Trigger = event → per-channel evaluation → state jump → reaction
potential ≥ threshold → a short **expression**, usually aimed at the **source**. This is what produces
"the burst after the fifth soup".

**Proactive (a life of its own, integrate-and-fire).** Trigger = a drive **urge** that has grown to the
threshold on its own, with no event. A drive = a **state in its second role** (not a separate `action_drive`).
- **START ≠ END:** START when `urge ≥ theta_start` (IDLE, after cooldown); END when
  `satisfaction ≥ theta_satiation` **OR** `fatigue ≥ theta_fatigue_end`.
- **Duration = a consequence of the dynamics** (when it satiates/tires), not a parameter.
- BUSY: the drive's stimulus cut off, its relief, fatigue and satisfaction rising a little/tick, urge
  expenditure. After END: cooldown.

**Drives (registry in config; adding = data, not code).** MVP = two in tension: `boredom→seek_stimulus`,
`fatigue→rest` (boredom pushes, fatigue brakes; fatigue is also a brake on the boredom urge → the
"pacing around → sits down" transition is sharp and natural). The boredom urge = **directly from `boredom`**
(drive = state in its second role, §4), damped by `fatigue`; the fatigue urge directly from fatigue. The
`boredom→frustration` edge stays **allowed, but OFF the urge path**: its role is the reactive chain
`boredom→frustration→anger` ("chronic boredom irritates over time", stability below in §8), not the
proactive trigger — its strength is a calibration task. **Named, deferred:** `hunger→seek_food`,
`contact→seek_company`; curiosity folded into boredom.

> **Note — two outputs from one state (not a re-entanglement).** `boredom` deliberately feeds **two
> distinct paths**: `boredom → urge` (proactive, read directly by `urge_boredom`) **and**
> `boredom → frustration → anger/complain` (reactive, the 0.04 coupling). These are two separate outputs
> of one state into two paths — *not* the old "urge via frustration" entanglement, which is removed. The
> urge no longer depends on frustration; the reactive chain no longer gates the proactive START.

**Activity model (M7 Step 2) — the proactive path is CLOSED-LOOP and fallible.** A proactive START does
not self-supply relief; it enters **SEEKING** (the intent — "looking"), which **costs frustration** each
tick. The engine ENGAGES (→ BUSY) only when the **world confirms** via an `activity` event (a mode-control
signal carrying `kind` ∈ {`self_activity`, `external`} and `novelty`); if no confirmation arrives within
`seeking_timeout_ticks`, it **gives up** → IDLE (keeping the accrued frustration — the "looked, found
nothing" arc). Engaged relief is per-tick, with the boredom relief **scaled by the confirmed novelty**, and
two opposite stress effects by kind: **`self_activity` (leisure) RECOVERS stress**, **`external` (work)
slowly RAISES it** while relieving boredom (the "overwork" arc). The engine stays open-loop internally — the
loop closes in the game (or a mock-world runner); stress's two new INPUTS are anchored so the frozen Layer-2
`anger↔stress` poles are untouched. Params (`seeking` frustration/timeout, the two activities' per-tick,
novelty scaling) are calibration placeholders. Design: `Ideas/future_milestone_activity_model.md`.
Only a **seeking** drive (flagged in config) needs confirmation; a **self-supplied** drive (`rest`) goes
IDLE→BUSY directly. An activity ENDs on satiation / `fatigue_end` / a per-action **`end_when_below`** (the
need it serves is met — e.g. `rest` ends once `fatigue` is low, "rested", not "tired").

**Proactive authority — the `duty` drive + `command_other` (live multi-agency, FIRST SLICE).** Authority is a
proactive *other*-directed need, modeled as the **exact mirror of boredom→seek**: a new **`duty` state** (a
decoupled integrator — decay + a sparse **drift**, "the fort always needs running"; it joins **no coupling**,
so it moves no pole, and its **long half-life** leaves `dt = min(half_life)/10` unchanged) read in its second
role by **`urge_command = w·duty·nfc_factor`**, with **`need_for_control`** as the **tempo modulator**
(`nfc_factor = 1 + k·(need_for_control − ref)`, the `novelty_seeking→urge_boredom` precedent). The drive fires
**`command_other`**, a **self-supplied, INSTANTANEOUS** proactive action (not a `seeking` drive, not a BUSY
dwell): from IDLE it fires once, books a **post-effect that discharges `duty`** (+ a small `satisfaction`), and
goes to COOLDOWN (the cooldown rate-limits issuance). The authority contrast **EMERGES from the trait through
the dynamics** — a high-`need_for_control` persona accrues duty and directs the staff periodically, a low one
never crosses `theta_start` (the litmus form, not a special case). `duty`'s drift is `0` by default (sparse),
positive only for an authority persona, so non-authority personas keep `duty ≡ 0` and are behaviorally unchanged.

**Cross-agent routing (the orchestrator, NOT the engine).** `command_other` is *other*-directed, yet the pure
per-persona engine knows nothing of the cast — it merely selects "command". A **multi-agent orchestrator** (the
generalization of the mock-world runner — the spec keeps the engine a pure per-persona function, "the loop
closes in the game") owns the roster, picks a target **deterministically**, and translates each selected
`command_other` into an inbound **`command` event** (source = the issuer) delivered to that subordinate **on the
next tick (a one-tick delay)**. The subordinate resolves it through the **existing, untouched** obedience
pipeline (`command_pressure` → per-source `cooperate`/`refuse`). The one-tick delay preserves the
synchronous-update / single-frozen-snapshot invariant **across** agents (no same-tick cross-dependency) and
keeps the multi-agent run **bit-for-bit deterministic** (sorted roster + deterministic target pick). The
**back-edge is OFF** in this slice (a subordinate's refusal does not feed back to the issuer) → pure
feedforward, no new loop. Full multi-agency (the back-edge authority↔resentment loop, chains of command,
in-engine target policy) remains stage-2. Design + open decisions: `Ideas/stage2_multiagency_authority.md`.

**Night & sleep — fast-state reset, slow-cause persistence (M7.5 Part B).** The multi-day reset: a character
sleeps at night and wakes calmer, but the SLOW causes persist — *"sleep angry, wake calm, but the grudge
stays."* Topology = one new mode + one decoupled state, with **no trait/param specialization** (every persona
sleeps by the same generic mechanism; the personas stay STATIC — sleep mutates only the fast state vector for
a night, changing no trait, relation, or config parameter):
- a new state **`sleep_pressure`** (decoupled integrator — joins no coupling, so no pole; setpoint 0, no
  drift by default) raised by a world **`night`** channel: the **`nightfall`** event, a mode-control signal
  from the day/night cycle (like `activity` — "the loop closes in the world / a runner");
- a derived **`sleep_urge = w·sleep_pressure + w·fatigue − arousal`**, where **`arousal = w·stress +
  w·anger + w·frustration`** is a derived **blocker** (a wound-up character is slow to drop off — *delayed*
  onset, not prevention; `sleep_pressure`/`fatigue` eventually dominate). States only, no trait;
- a proactive **`sleep`** drive (urge `sleep_urge` ≥ `theta_start`) entering a new **`SLEEP`** mode (NOT
  `BUSY` — sleep changes the rules of reactivity). In `SLEEP`, per-tick effects (calibration placeholders)
  **strongly decay the FAST states** (`anger`/`stress`/`frustration` → 0; `satisfaction` → neutral), reduce
  `fatigue`, discharge `sleep_pressure`, recover `self_control`, and let `hunger` rise slowly. The **SLOW
  states are untouched** (`trust`/`respect`/`resentment` are not in the sleep per-tick) → **the grudge
  persists by construction**;
- **wake** naturally when rested (`end_when_below {fatigue, sleep_pressure}` → COOLDOWN→IDLE), or
  **wake-on-threat** — a provocation strong enough to clear `theta_interrupt` interrupts sleep and fires the
  reaction on waking; a mild stimulus never clears that high threshold, so the sleeper sleeps through small
  things and wakes to big ones, with **no special-cased stimulus tiers**.
Sparse/neutral by default: with no `nightfall`, `sleep_pressure ≡ 0` → `sleep_urge ≤ 0` → the drive never
fires, so single-day litmus/goldens are untouched. Design input: `Ideas/future_milestone_sleep_dynamics.md`.

**Action catalog** (shared selector; rule: the strongest candidate above its threshold wins):
- Proactive (activities): `seek_stimulus` (boredom relief, +satisfaction, +fatigue, cooldown);
  `rest` (−fatigue, slightly +satisfaction; interruptible); `command_other` (self-supplied, INSTANTANEOUS
  authority verb — fires from the `duty` drive, discharges `duty`, → COOLDOWN; routed cross-agent, above);
  `sleep` (self-supplied, fires from the `sleep_urge` drive → the `SLEEP` mode — strongly resets the FAST
  states while the SLOW relational memory persists; wakes when rested or on a strong stimulus; §8 night/sleep).
- Reactive (from the 11 states): `complain` (intensity from the potential — merges complain_light/strong);
  `outburst` (anger discharge, +resentment[source]; `hostile_action` = the top range, gate: very high
  outburst + low eff_self_control + low respect, no fear); `cold_response` (negative, composed; standalone
  in the MVP); `cooperate` / `refuse` (**obedience to an order — command-gated, source-keyed**; see the
  obedience terms below); `positive_response` (**a warm reply to an appraised kindness — gesture-gated,
  source-keyed**; see the kindness terms below); fallback `neutral`.
- **Stage 2:** `engage` (would stand on curiosity — its role is filled by `seek_stimulus` +
  positive_response/cooperate), `avoid` (would stand on fear/attachment — withdrawal is covered by `cold_response`).

**Arbitration = interrupt gated by influence.** "Influence" = the reaction potential **after the filter**
(the filter already damps trivial/indifferent stimuli). Two reactive thresholds: `theta_react` and the
higher `theta_interrupt`. Three bands in BUSY (section 7). **Invariant: state always updates** — we gate
only the action/mode choice, not the state change. Consequence: **a series of small pokes accumulates
state until it crosses `theta_interrupt`** (pestering eventually interrupts). In IDLE a reaction takes
priority over starting an activity. MVP: `theta_interrupt` constant per action (an engagement-dependent
variant = later tuning).

**Reward and learning.** satisfaction = the reward channel; `affinity[activity]` = the learned value;
learning (stage 2) raises affinity proportionally to reward. Separate **liking** (satisfaction/affinity)
from **wanting** (urge). Distinguish **offline calibration** (personality constants) from **online learning**.

**State→state coupling topology (explicit, frozen for the MVP).** The list of **allowed coupling edges**
in the `update` equation (`Σ coupling[x][y]·y_snapshot`); everything off the list = `0` (the neutral
default). The gain values are from calibration; the *topology* is frozen here:

```text
hunger      → stress
fatigue     → stress
boredom     → frustration
frustration → anger
stress      → anger
anger       → stress
```

- **Not couplings (these are derived in `derived`, §4–5):** the suppression of `urge_boredom` by `fatigue`
  (a component of the urge derived value, not a state→state edge) and `eff_self_control = self_control −
  f(fatigue, stress)`.
- **Ambient idle homeostasis (`idle_recovery`, D11) — NOT a coupling either.** A per-tick recovery toward
  calm (`idle_recovery[stress]`, `idle_recovery[anger]` < 0) applied in `update` ONLY when `mode==IDLE`,
  unprovoked (no provocation within `reactive_window_ticks`) AND not under an active **world stressor** (a
  sourceless `weather`/etc. within its window — you do not relax toward calm while cold and wet; this is what
  lets rain WEAR a persona down even though, having no source, it `opens no reactive reply`). It is the IDLE counterpart of the BUSY
  per-tick activity effects: seekers shed stress by engaging a `self_activity`; non-seekers, who never
  seek, otherwise have **no intraday path down** and sit chronically high → over-react to ordinary events
  (the D11 finding). Gated on *unprovoked*, so a confrontation does not self-soothe and the burst-vs-suppress
  litmus (provoked throughout) is bit-identical. Magnitudes are calibration placeholders, signed, sparse
  (absent state = 0). The whole block is scaled by an optional **reactivity modulator** (§14):
  `idle_factor = clamp01(1 + k·(reactivity − ref))`, clamped `[0,1]` so reactivity only *reduces* recovery
  — a high-reactivity persona (resentful prisoner, thin-skinned recruit) settles slower and keeps its edge;
  a calm one recovers at the full base rate. (The blind re-judge showed a *uniform* recovery over-relaxed
  exactly the high-reactivity cast — D11 round 2.) Recovery also stops at a **standing-grievance floor**
  (`idle_recovery_floor[stress] · resentment_max`): a deep resentment is itself a baseline stressor, so a
  resentful captive idles *wary*, not "at ease" — recovery never pulls stress below the floor (D11 round 3).
- **The only feedback loop** is `anger ↔ stress` (a 2-cycle); `boredom→frustration→anger` and
  `hunger/fatigue→stress` are **feedforward** edges into that loop, not cycles.
- **Stability (a mandatory re-check when gains change).** The linearized 2-cycle
  `[[decay_stress, g(anger→stress)],[g(stress→anger), decay_anger]]` must have poles inside the unit
  circle. The binding Jury criterion: `g(anger→stress)·g(stress→anger) < (1−decay_stress)·(1−decay_anger)`.
  The regime test (`tests/`) computes the spectral radius of the full 6-state submatrix and requires `< 1`.

**Reactive potentials — gated by state, traits only modulate.** `M7` computes only
`potential = clamp(Σ weight·term)`, where each **term** is a declared product of factors (like the
coupling topology: an explicit list, not a formula in code). **Invariant (validated at load):** every
term has ≥1 **state** factor (state / derived / relational aggregate); `state×trait` and `derived×trait`
are allowed, **`trait×trait` is forbidden** — otherwise personality alone (e.g. high stoicism) would fire
a reaction at zero emotion. A trait only **modulates** the state signal. Hence the emergent split of
suppression (§7): `anger×stoicism → cold_response`, `anger×(1−eff_self_control) → outburst`. A factor may
be complemented (`complement: (1−x)`, e.g. "low control").

Terms used in the MVP (placeholder, `calibration/defaults.yaml`): `frustration`, `hunger`,
`irritability`, `dissatisfaction`, `resentment_max`, `anger×stoicism`, `anger×(1−eff_self_control)`,
`frustration×need_for_control`, `dissatisfaction×pride`, plus the **obedience terms** below.

**Obedience (`cooperate`/`refuse`) — command-gated, source-keyed (MVP-active).** `command_pressure`
(transient, §5/§7: this tick's `command` channel × authority, carrying `command.source`; `0` when no
order) is a permitted **gating factor** alongside states — it *extends* the invariant without breaking it:
every obedience term carries `command_pressure` (→ **no order, no obedience response** — you can't refuse in
a vacuum) **and** a per-source relation factor, so a trait can never fire obedience alone (same spirit as
the `trait×trait` ban). The decision is **whether** to obey, not **what** to do (content is the game layer's,
§5). Reading the relation of the COMMAND's source (per-source, NOT the `resentment_max` aggregate —
resenting Wojsław must not break obedience to Edda):
- `cooperate = command_pressure × respect[command.source]` — "I comply because I respect THIS commander"
  (`gratitude` may modulate).
- `refuse = command_pressure × [ resentment[command.source] + (1−respect[command.source])×need_for_control
  + frustration×need_for_control ]` — "I refuse a commander I resent / don't respect; a frustrated
  controller refuses an order harder." Every term command-gated; `need_for_control` only **modulates**.

The split is **emergent**: the SAME command — `respect[source]` high → `cooperate` wins; `resentment[source]`
/ low respect → `refuse` wins — **within one persona, purely from the relation to the source** (the second
litmus). Calibrate it as its OWN sub-block AFTER the frozen anger loop, **monitoring the burst contrast**
(`command→frustration` shares the loop's `frustration`). Calibration note: `cooperate` has 1 term, `refuse`
has 3 (more "mass"), so the sub-block gate must verify the contrast is **positive in BOTH directions**
(`cooperate` clearly wins at the respected source, `refuse` clearly wins at the resented one), not merely
"`refuse` is weaker at the respected source" — same logic as the decoupling monitor.

**Obedience priority over venting — a respected order inhibits `outburst` (D11 / believability).** A recruit
carrying *residual* ambient anger (left by an off-screen provocation, not a fresh insult) could let `outburst`
out-argmax `cooperate` on a respected commander's order — the SAME order obeyed one tick and snapped-at the
next, reading as "dice, not temperament." Obedience to a **respected** commander is modeled as **robust to
ambient irritation**: the order itself *inhibits* venting. Realized with **no new selector logic and no new
term**, as a **signed (inhibitory) edge** — the existing `command_pressure × respect[command.source]` term
(the one `cooperate` reads with a positive weight) is wired into `outburst` with a **negative** weight (same
quantity, opposite sign; the system's first inhibitory potential edge — "signed feedback" in the diagram
sense). Neutral by default: no order → `command_pressure = 0` → no effect (the burst-soup litmus, command-less,
is bit-untouched); low respect → small effect (a barely-respected commander still draws a snap — robustness
scales WITH respect, as it should); high respect → strong suppression → after `clamp01` the flat argmax (§7)
naturally selects `cooperate` over the residual-anger `outburst`. **Scoped to `outburst` only** — a *curt*
`cold_response` to a respected order stays believable (a disciplined subordinate answering shortly is not
insubordination; cf. the blind judge's read of Halgrim). Magnitude is a **believability-strength placeholder**:
the ORDERING (a respected order suppresses venting) is behavior-authorized, but it has no sharp behavioral
crossing to pin the gain → a bounded placeholder pending Level-3 / LLM-comparative validation (§17), like the
pride→insult `mod`. Litmus-safe **by construction** (no-command and low-respect cases are untouched), so the
obedience and burst contrasts are preserved structurally, not gate-guarded.

**Kindness appraised → `positive_response`, and a kindness *inhibits* venting (Theme A / believability).**
The mirror image of the provocation appraisal (§7). A **pro-social gesture** (`food_given`/`help` — a
`gesture` tag in config, not a hardcoded type) that is appraised **non-negative** (its filtered inputs do
not net `anger`/`frustration` — the same `contrib` the provocation check computes, here `≤ 0`) from a
**non-resented** source (`resentment[source] < provocation_resentment` — the *same* threshold used
symmetrically) emits a transient **`kindness_pressure`** (this tick's appraised goodwill; `0` otherwise —
the exact counterpart of `command_pressure`, a permitted gating factor alongside states). It drives
**`positive_response = kindness_pressure × trust[source]`** — a warm reply that books a small **`+trust[source]`** goodwill (the mirror of `outburst`'s
`+resentment[source]`, so warmth *accumulates* over days as grudges do). The SAME `kindness_pressure` is
wired as a **signed (inhibitory) edge** into the hostile potentials (`outburst`/`cold_response`/`complain`)
with a **negative** weight — a kindness *filters down* the urge to lash out, so pre-loaded anger does not
discharge onto a kind giver (the "rage at the soup" artifact: anger armed above threshold, latched, that the
benign event's opening of the gate would otherwise release onto the giver). Realized with **no new selector
logic, no branch** — the identical signed-edge mechanism as obedience priority above. Neutral by default:
no gesture / resented source → `kindness_pressure = 0` → every hostile potential is bit-untouched (the
burst-soup and prisoner litmus, whose soup comes from a resented/bad-day source, are unchanged) and residual
venting on real provocations is unaffected; `positive_response` then sits at `0`, never selected. The
appraisal keeps Cichy intact **by construction** (jailer's soup → resented source → not kindness → still
galls). Magnitudes (the `kindness` weight, `react.positive_response`, the goodwill deposit, the inhibitory
gain) are **calibration placeholders**; only the ORDERING is authorized (kindness raises warmth and
suppresses venting). **Displaced aggression** — a high-anger burst landing on an innocent giver *despite*
the kindness — is deliberately OUT of scope here: it is a real future behaviour gated behind a high
`theta_displace` bar (`>> react.*`) and deferred to `Ideas/burst_saturation_design_note.md`, where the
durable-grudge runaway it would otherwise mint is also addressed.

**Target policy — a respected BYSTANDER does not catch displaced anger (the THIRD inhibitory edge).** A
reaction is normally aimed at the source that provoked it; but the engine carries **one global `anger`
pool**, so residual anger from provoker X could vent onto a DIFFERENT source Y who merely interacts next
(the `halgrim_068` flag: cold contempt at *respected* Edda when the anger is really Wojsław's). Fixed as a
per-source **filter** on the reaction — the mirror of the obedience and kindness edges. The runtime
remembers the current provoker (`last_provocation_source`); when this tick's event is NOT itself a
provocation and comes from a source S ≠ that provoker while residual anger still lingers (within
`reactive_window_ticks`), a transient **`bystander_pressure`** is emitted, and the term
`bystander_pressure × respect[S]` is read with a **negative** weight by `outburst`/`cold_response` — you do
not snap at, nor give cold contempt to, a *respected* bystander for someone else's offence. The damping
scales WITH respect (a stranger bystander still catches a little; a respected commander is spared), so the
obedience response to a respected order wins instead. Neutral **by construction**: a fresh provocation, the
provoker themselves, or no residual anger → `bystander_pressure = 0` → bit-identical (the burst / obedience /
prisoner litmus, all single-source, are untouched; the change only bites when a *second* source interacts
while anger from a *first* still lingers). This is one **instance of the general per-entity FILTER mechanic**
(`relation_filter`, `affinity_filter`, `gain_modulators`, and the obedience + kindness edges are the others,
all `identity`/`k=1` by default) — the milestone to unify them is `Ideas/filter_unification_milestone.md`
(HIGH priority). **Displaced aggression** — at very high anger the burst DOES land on the bystander ("kicking
the dog"), gated behind a high `theta_displace` — stays deferred to `Ideas/burst_saturation_design_note.md`.
Magnitudes are calibration placeholders; only the ORDERING (a respected bystander is spared) is authorized.

**Resentment without an order → `cold_response` (prisoner-bias), via a TEMPORARY per-persona threshold.**
`refuse` is obedience-only (above): it expresses resentment *when commanded*. The SAME resentment, *without*
a command, surfaces as a **cold reception** — and it needs **no new potential term**. The relational filter
already routes it: a resented source's insult is amplified (`resentment[src]` → `anger↑`), and `anger×stoicism`
lifts `cold_response`. So resentful Cichy's `cold_response` (≈0.28) already exceeds neutral's (≈0.20) — the
contrast is in the dynamics. What it does NOT clear is the shared `react.cold_response = 0.50`, and **a single
shared threshold cannot carry it**: stoic Lutek sits at `cold_response ≈0.40` from `anger×stoicism` alone (a
fresh insult he doesn't shrug — see root cause) and must read NEUTRAL, while resentful Cichy at ≈0.28 must
CROSS; `0.28 < 0.40` **inverts the ordering**, so no shared threshold separates them. (A per-source
`resentment[src]` term was considered and rejected: `potentials` read state′, so the insult's own
same-tick resentment deposit lifts Lutek too — it is not the clean "Lutek=0" separator it first appears.)

So GATE 3 gives **Cichy a per-persona `react.cold_response ≈ 0.24`, tagged TEMPORARY**. A private threshold
**DECOUPLES the prisoner from the burst litmus by construction** — Lutek/Halgrim/Wojsław keep `0.50`, so the
first litmus is untouched (structurally, not gate-guarded). Gate (max-penalty / min-margin): resentful Cichy
reads `cold_response` **every tick from the overture to window-end**; neutral Cichy + Lutek + the burst
contrast are unchanged (regression guards, slack by construction).

*This per-persona threshold is a STOPGAP. Root cause: `insult→anger` is **undifferentiated** across personas
(all ≈0.43) — nothing lets low-pride Lutek SHRUG an insult, so his "neutral" sits a hair under threshold. The
real fix — wiring `pride → insult-sensitivity` (high pride wounds more, low pride absorbs) so the insult axis
emerges from a trait at the anger layer — is a **deferred milestone that re-validates Layer 2**; when it
lands, Lutek drops to ≈0.30, the band widens, and the per-persona threshold retires.*

---

## 9. Tuning / calibration

- **Reparameterize:** decay ↔ half-life (section 2); gains as a steady-state effect. Set time and level,
  not raw numbers.
- **Calibrate in layers, not the whole matrix at once:** (1) time scales from half-lives; (2) single
  blocks in isolation; (3) local loops one at a time, with a stability penalty; (4) progressive joining
  with the earlier layers frozen; (5) a global fine-tune within narrow bounds. Personas: first the shared
  structure, then a small set of per-persona traits + contrast verification.
- **LAYERS ARE COUPLED (a first-class lesson — clean layer sequentiality is an idealization).** "Which
  phenomenon belongs to which layer is **DISCOVERED, not assumed up front.**" This recurs every layer, in
  four concrete forms found in practice:
  1. **via a shared loop:** tuning anger's half-life shrank the burst peak (layer 1 ↔ behavior).
  2. **via layer-assignment:** anger cooldown is a GAIN-layer property, not a half-life one — its half-life
     has ~no leverage; the `stress→anger`/`frustration→anger` couplings dominate it (known_divergences D6).
  3. **via a hard physical bound:** a strong-AND-stable anger↔stress loop needs shorter anger/stress
     half-lives (the Jury bound `(1−dec_stress)(1−dec_anger)` shrinks as the decays approach 1), so the loop
     gains and those half-lives are **one sub-problem** (D7 → resolved by co-freezing the two half-lives).
  4. **via `dt`:** `dt = min(half_life)/10`, so calibrating the shortest half-life **rescales every
     tick-based timing metric** — timing anchors are revisable within ±dt-drift, **not points** (calibrating
     anger shifted the frozen satisfaction anchor 45 → ~48 s).
  Consequence: earlier layers are *temporarily fixed but **renegotiable***. If a later layer cannot meet a
  contract at the frozen earlier values, that is the signal to RE-OPEN the earlier layer / reconsider the
  anchor — not to grind out a compromise.
- **Gradient-free optimizers** (CMA-ES / Optuna) — thresholds and clamps are non-differentiable. Loss =
  behavior_loss + ranking_loss (persona contrasts) + curve_loss (curve shape) + stability_loss
  (|pole|>1) + regularization_loss (parameter ranges). Sensitivity analysis first (Sobol) to freeze the
  irrelevant ones.
- **Targets = behavioral acceptance criteria + property tests**, not a labeled dataset. Believability is
  checked secondarily (a human/LLM judge) on scenarios on the side.
- **Memory-filter library** (from the notes): a shared pool `short/medium/long/streak/novelty` (different
  time constants), an emotion = a learned combination of weights — an operationalization of the principle
  "state = integrator with decay".
- **Sources for the mapper (the front seam, offline):** Social Chemistry 101 (norms → semantic inputs),
  GoEmotions / DailyDialog / EmpatheticDialogues (tone), LIGHT (action inventory). An LLM offline
  generates scenarios → a human picks 30–50 → the benchmark.
  - **FUTURE STREAM (distinct from the dynamics layers):** the emotion corpora (GoEmotions / DailyDialog /
    EmpatheticDialogues) calibrate the **mapper FRONT SEAM** — the text→channel *gain* (a hard measurement
    of text→emotion). This is a separate concern from the time-constant / gain layers (which tune the
    *dynamics*, not text parsing) **and** from Validation Level 3 (§17, which scores believability of the
    contracts, never the text seam). Keep the three uses apart.

---

## 10. Tests

Golden trace (trace regression), property and persona-contrast tests (`proud_noble` > `humble_monk` on
anger; repetition → boredom rise), regime tests (no runaway in a neighborhood of the parameters; pole
stability), bit-for-bit determinism. A `suppressed_anger`/resentment loop test (stage 2): from deep
bitterness, recovery events genuinely bring it down. **The litmus test:** not "different anger numbers",
but that two personas in the same scenario **play differently** in visible actions.

---

## 11. LLM — optional, outside the MVP

The LLM is an **optional layer outside the MVP**; **the engine never depends on an LLM in the loop**.
Wired in only through two seams: **perception** (free player text → input events) and **expression**
(action events → text). **The LLM never mutates state** — state is changed only by `update` from events.
Without an LLM both seams have a deterministic fallback (structured events on input, templated text on
output). The ambient mode (asynchronicity of background lines) returns together with the LLM.

---

## 12. Directive: block diagrams

Every subsystem keeps a maintained diagram in **two forms** (control: summing junctions, integrators,
gains, comparators, flip-flop, signed feedback; and functional: the cycle in domain language), **before**
implementation and in sync with the code. They serve as specification and as a review tool (loop
stability, feedback signs, where START and where END).

**A diagram is a REQUIRED OUTPUT ARTIFACT, not an element of a chat reply.**

- **Location/format:** one versioned file `docs/diagrams/<subsystem>.md` per subsystem, **both** forms in
  the same file. ASCII art drawn only in chat = **does not exist**; without a file in the repo a subsystem
  has no diagram.
- **Definition of Done:** a subsystem is not "done" without an accompanying, synchronized diagram in both
  forms. No diagram = subsystem not done.
- **Synchronization:** changing a subsystem's structure = updating the diagram **together** with the code
  (the same rule as "spec first, then code"). A diagram detached from the code is worse than none.
- Every diagram must make the subsystem's **invariants** visible (e.g. for the selector: "state ALWAYS
  updates, arbitration gates only the action/mode choice").

---

## 13. Stage-2 scope (deliberately deferred)

States: `fear` (threat reactions + avoidance), `suppressed_anger` (suppression with a delayed burst),
`attachment` + `fear_of` (relationship depth, the romance arc, intimidation by a person), `comfort` +
`safety`. Channels/actions: `threat`, phobias (preference→fear), the `engage`/`avoid` actions.
Mechanisms: online affinity learning, multi-character content in scenarios (the structure is ready —
Relations per source — the MVP used only `player`; the **FIRST SLICE of live multi-agency is now implemented**
— the `duty`→`command_other` authority verb + a deterministic one-tick cross-agent router, §8; what remains
stage-2 is the **back-edge** authority↔resentment loop, chains of command, and in-engine target policy),
**humor as reappraisal** (an affective filter
dependent on a `humor`/`wit` trait, which *shifts part of the negative valence — especially `insult` —
into `satisfaction`*: an insult lands more weakly **and** improves the mood; in the MVP we reproduce only
the external effect — no burst — via stoicism + self_control, without rewriting the valence). `curiosity`
only if novelty earns an axis beyond boredom. `familiarity` — cut. The **affinity FIELD** (object+agent
valence generalization, previously deferred here as "phobias / affinity learning substrate") is now
SPECIFIED in §5 and staged: object resolver → people-(A) seed → people-(B) prior. Each addition = one
integrator/channel/action with no structural change.

---

## 14. The generic element and the extension contract

**Principle (how we build layers).** One generic element, parameter-driven, with neutral defaults —
**not** per-role blocks, **not** a framework ahead of need, **not** a dense coupling matrix.

- **State = an instance of one integrator:** `new_x = clamp(decay_x·old_x + drift_x + Σ gain·mod·input + Σ coupling[x][y]·y)`.
  The role is a preset: emotion `setpoint 0, drift 0, fast decay`; accumulator (hunger/fatigue) `drift>0`;
  homeostat (self_control) `setpoint=base`; memory (relation) `decay≈1`. "Does not use drift" = `drift=0`,
  not separate logic. This is **less** code (one function + a 11-row table), not more.
- **Neutral default everywhere:** a missing coupling/input edge = `0`; an inapplicable filter stage =
  identity. Adding something = flipping a default from neutral to active, uniformly.
- **Sparse wiring in config:** the set of allowed edges (`coupling`, `gain`) is declared, the rest absent.
  The optimizer does not fill the full matrix (consistent with Sobol → freeze the irrelevant ones, §9).
- **Gain modulators (sparse, trait × input-gain):** an input→state gain edge MAY be scaled by a trait via
  `mod = 1 + k·(trait − ref)` (a proud persona feels an insult more, a thick-skinned one less). Neutral
  default = no modulator = identity (`mod = 1`); anchored at `ref` so a reference-trait persona keeps the
  calibrated gain exactly (the Layer-2 freeze stays valid — only the per-persona *spread* is new). Generic
  and reusable — any `(state, channel)` edge, declared sparsely in config (later: gratitude×help,
  threat_sensitivity×threat) — no per-edge code.
- **Filters = a uniform pipeline of identity stages** (the dispatch from section 5 is its form: a self
  channel passes through an identity stage, it is not an exception carved out with an `if`). The per-entity
  modulation each stage applies is **one shared kernel** (`filters.py`: `factor = 1 + gain·sign·value`
  over a `lookup(entity, table)` with a neutral default) — a single generic element, identity unless a
  config entry populates it, exactly like the integrator and the gain modulators. Its `lookup` is the
  designated seam for the entity-generalization: the **cosine affinity FIELD over an embedding space,
  now specified in §5** (the discrete category→specific hierarchy is superseded by it — nearness is the
  grouping); swapping the lookup internals moves no call site and an
  empty table / empty field stays bit-identical. Trait-keyed modulators (gain modulators above) are a *different* axis
  and stay separate — no framework forced across the two.
- **Drive and relation = core + a thin capability via a uniform interface** (drive: urge read + thresholds
  + binding to an action; relation: a dimension per `AgentId` + affective bias). They pass through a
  uniform interface so as not to be a special `if` — but **formalizing the capability (mixins/plugins) is
  deferred** until a third drive- or relation-like entity appears and asks for it itself.

**Extension contract** (uniform, because the core is one — this turns "it can be extended" into a procedure):

- **A new state (integrator instance):** semantics + range; role settings (`setpoint`, `drift`,
  `half_life`/`decay`) — **and recompute `dt = min(half_life)/10`** if the state is faster than the current
  fastest emotion; feeding channels + gains; signed couplings + a **stability re-check (poles in the
  circle)**; parameter bounds + a place in the layered calibration order; property/contrast tests.
- **A new channel:** class (relational/affinity/physiological) → routing; `source`/`target` tags; which
  states it drives + gains; the mapper rule (raw event → channel); filter behavior (or identity).
- **A new action:** the path. **Reactive:** which states the potential is computed from, the
  `theta_react`/`theta_interrupt` thresholds, the direction (at the source), the ledger of effects on
  state and relation. **Proactive:** which urge triggers it, the start threshold, the end condition, the
  per-tick BUSY effects, the cooldown. Integration with the selector is **automatic** if the action keeps
  the uniform potential/urge interface.
- **A new drive (capability):** which existing state is its integrator; the urge-read function; the
  satisfying action it binds to; start/end thresholds; an entry in the **drive registry** in config
  (adding = data, not code).

**Inventory of tuned values (no literals in engine code — everything from config with a default):**
half-lives/decay, drifts, setpoints, input→state gains, gain modulators (sparse trait×gain: trait, ref, k),
state→state couplings (sparse), potential and
urge read weights, thresholds (`theta_react`, `theta_interrupt`, `theta_start`, `theta_satiation`,
`theta_fatigue_end`, action thresholds), action parameters (per-tick relief/cost/reward, cooldown),
affinities. *Values* are in config; *topology* (the list of allowed edges) too — the code holds only the
generic shape of the equations.

---

## 15. Remaining decisions (preparation for calibration) + module map

**Frozen (separate files):** the trait list + the 8-persona cast + the relation graph →
`rpg_persona_dynamics_persony.md`; the scenario benchmark with comparative predicates →
`rpg_persona_dynamics_scenariusze.md`. The tuning loop → §16 below. **Remaining (values from
calibration, not decisions):** concrete half-lives (→ `dt`), gains, thresholds, the ranges of the learned
parameters. **To be built:** the shared action-selector diagram; the harness **code** (the simulator as a
pure function + a metric extractor + a predicate evaluator + an optimizer).

**MVP demo (the litmus test):** the same soup, three situations — (A) good day, trusting, hungry →
grumbling/neutral; (B) tired, bored, resentful → a burst; (C) calm, loyal → boredom rises, no burst.
Proves "dynamics, not a `soup=anger` rule".

| Member | Repo module |
|---|---|
| Types / schema | `schema.py` |
| Loader | `yaml_io.py` |
| History | `history.py` |
| Mapper | `mapper.py` |
| Filters | `relation_filter.py`, `affinity_filter.py` (shared kernel: `filters.py`) |
| Derived (+ urge) | `derived.py` |
| Update (synchronous) | `update.py` |
| Reactive potentials | `potentials.py` |
| Selector (2 paths + arbitration) | `action_selector.py` |
| Orchestrator (loop, mode) | `simulation.py` |
| Debug / clamp | `debug.py`, `clamp.py` |
| Calibration (loop, loss) | `calibration.py` |
| Metrics + predicates | `metrics.py`, `expectations.py` |
| Personas / scenarios (data) | `personas/*.yaml`, `scenarios/*.yaml` |

---

## 16. Calibration harness

A **closed** loop — the human steps in only once, offline. Built around the scenarios
(`rpg_persona_dynamics_scenariusze.md`) and the cast (`rpg_persona_dynamics_persony.md`).

1. **The simulator = a pure function of parameters:** `simulate(params, persona, scenario) → trace`. It
   follows from the invariants (pure functions, bit-for-bit determinism) — which is why it suits an
   automaton.
2. **Metric extractor:** `trace → metrics` (the library described in the scenarios file).
3. **Expectation evaluator (DSL):** boolean / comparative / ordering / threshold / shape predicates; each
   → `0` or a penalty ∝ the margin of violation. Comparative ones require **several personas through the
   same scenario**.
4. **Loss:** `behavior + ranking + curve + stability(|pole|>1) + regularization`, aggregated over scenarios.
5. **Gradient-free optimizer** (CMA-ES / Optuna) → new `params` → back to 1. No human.
6. **Layers = automaton stages** (§9): the same harness in stages, **freezing** earlier parameters;
   **Sobol** first prunes the irrelevant ones.
7. **Golden trace** = regression: an approved scenario trace as a snapshot.

**Requires building:** the predicate DSL, the metric library, `Scenario`/`Persona` as **pure data**
(already in the §3 types), and a **multi-target event** (one event → perpetrator / target / witness on the
relation graph). **The human's role:** curation only (an LLM generates candidates → the human picks
30–50) + acceptance thresholds — **authorship, not running/judging**. **`dt` note:** the fastest persona
(Lutek) sets `dt` for the whole simulation.

---

## 17. Validation Level 3 — snapshot validation against ground truth (FUTURE WORK)

Concretizes the §9 "believability checked secondarily" line. **After** the dynamics layers (time
constants, gains); not part of the MVP. A **three-tier validation pyramid**:

1. **Golden trace + property tests** — the engine *computes* correctly (bit-exact, deterministic).
2. **Predicate benchmark** (anchor + orderings, §16) — behavior meets the **designed** contracts.
3. **THIS — snapshot validation** — are the designed contracts **believable against reality**?

**It VALIDATES, never TRAINS.** The model is frozen; external data only **scores** it — it never reaches
in to retune. An observer (Kalman/Luenberger) that *corrects* the model from data would be **learning** —
**forbidden**. We take the **observability QUESTION** from control theory, **not** the observer MECHANISM.

- **Validate CONTRASTS, not absolute levels.** "A is more agitated than B in this scene", never "A = 0.8".
  In a contrast the source's absolute error **cancels**, so an LLM as a **comparative** judge is sound; as
  an **absolute** judge it is false precision.
- **Observability constraint (literally a control-theory observability problem).** A **single snapshot is
  non-observable** w.r.t. the dynamics: with different dynamics, trajectories **cross**, so "A > B" holds at
  one instant and fails at another, and one snapshot cannot tell which. Restore observability the control
  way — **add a second time point**: validate on **PAIRS of snapshots** (earlier/later) or on **DECAY-RATE**
  comparisons (phase-invariant). Validate **phase-anchored** contrasts (at peak, or decay rate), never
  random-moment levels.
- **One matrix, two questions.** Observability is computed from the **same linearized matrix** used for
  stability (§8); use it to **DESIGN which snapshots to collect**, before collecting them.
- **Two-knobs feature (not a compromise).** *Contrast* (grounded in reality, validated) and *dynamics/tempo*
  (designed, subordinate to the time-scale anchor) are **independent axes** — contrast is
  time-scale-invariant, so tempo is freely chosen without breaking relative believability. Consequence: a
  society = a few grounded **TYPES** (validated contrasts) + one designed global **TEMPO** → **many personas
  from few parameters**.
- **Provenance + separation.** Snapshots need **external** provenance (annotation / source text / real
  data); **generation is kept separate from evaluation** (the LLM never both authors and grades). A level-3
  **failure is DIAGNOSTIC** ("which layer? the expression seam?"), **not** automatically "the half-lives are
  wrong" — a snapshot measures a **LEVEL** (gain/expression-dependent), not a half-life.
