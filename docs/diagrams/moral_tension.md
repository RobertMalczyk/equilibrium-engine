# Block diagram — moral tension (M-J subsystem)

> Maintained in two forms (CLAUDE.md §"block diagrams"): **control** (integrators, summing junctions,
> gains, signed feedback, comparators) and **functional** (the cycle in domain language). Synchronized
> with the spec `moral_tension_impl_spec.md` and (once implemented) `engine/update.py` /
> `engine/potentials.py` / `engine/simulation.py`.
>
> **Status: M-J.0 (guilt core) + M-J.1 (lie loop) + M-J.2 (`repair_drive`/`rumination`/`apologize` +
> `confide` safe-vs-gossip split + `apologize` relational `reparation`) + M-J.3 (accusation core:
> `perceived_injustice`/`avoidance_drive`, the opt-in `suspicion` relation dim, `accusation` cue, the
> grievance switch `perceived_injustice→anger(+)`/`→guilt(−)`, `blame_other`/`avoid`, and the
> `suspicion_raised`→`suspicion_cue` pressure-without-truth cue, and **M-J.3.3** the public-accusation
> WITNESS FAN-OUT + `false_accusation_discovered` accuser-remorse cue, built on the merged **M-MEM**
> multi-event tick) IMPLEMENTED as an opt-in overlay; M-J.4 is topology-only (the `LieRecord` ledger and lie
> detection remain deferred).** Per
> "topology now, constants from calibration" every gain/half-life is a **named config placeholder**, not a
> chosen number. The full moral topology (all of M-J.0–.4) is drawn here so calibration tunes a fixed
> structure; the ★ nodes/edges are wired and litmus-proven (`tests/test_moral_guilt_core.py`,
> `calibration/moral_overlay.yaml`), the rest stay drawn-but-unwired until their slice lands.
>
> **Invariants made visible:**
> - Every moral state is the *same* generic leaky integrator (spec §14) — `update.compute` already
>   iterates `GLOBAL_STATES`; no new block type.
> - **Events are finite single-tick deposits, NOT Dirac impulses** (`docs/control_interpretation.md`).
>   Fast rise = high finite event gain; slow aftermath = long half-life.
> - The `MoralLedger` is **read-only in `update`**, mutated only in `post_effects` (the one sanctioned
>   second mutation site). No moral equation writes `global_state` outside `update`.
> - `moral_tension` is a **derived read-only observable**, never a stored/integrated state.
> - Two positive loops (★salience↔guilt↔exposure_risk, rumination↔stress↔fatigue) must pass the Jury /
>   spectral check (`engine/stability.py`) before calibration — same gate as the anger⇄stress loop.

## Member I/O (where the subsystem sits in the tick)

```
Tick order (unchanged): freeze → derived_pre → perception(mapper→filters) → gating → UPDATE →
                        commit+clamp → derived_post → potentials → selector → POST_EFFECTS → bookkeeping
IN:  moral cue channels (direct_question, accusation, lie_committed, secret_cued, …)  <- mapper
     MoralLedger (secrets/lies)        <- frozen into Snapshot, READ-ONLY here
     relations{trust,respect,resentment,suspicion}, traits{empathy,guilt_proneness,…}
OUT: moral global-state deltas (guilt, exposure_anxiety, …)   <- UPDATE (leaky integrators)
     ledger writes + action bookings   <- POST_EFFECTS only
     moral_tension (derived observable) <- read off the committed state vector (no mutation)
```

---

## Functional form (the cycle in domain language)

```
A WRONG / SECRET / LIE happens
        │  (finite event deposits — never a Dirac spike)
        ▼
  ┌─────────────────────── the moral state vector (7 leaky integrators) ───────────────────────┐
  │  ★guilt ............ violated own frame: lie/harm/betrayal/broken-promise/kept-secret       │
  │  ★exposure_anxiety . afraid of being found out: question/accusation/suspicion/witness       │
  │   repair_drive ..... want to make it right: rises with guilt + trusted-target + opportunity  │
  │   avoidance_drive .. want to dodge person/topic/consequence: rises with exposure_anxiety     │
  │   rumination ....... can't stop replaying it: rises with guilt + unresolved + failed-repair  │
  │   cognitive_load ... burden of maintaining the lie: rises with each lie + probing            │
  │   perceived_injustice "this is unfair" — converts guilt → anger/resentment                   │
  └───────────────────────────────────────────────────────────────────────────────────────────┘
        │                                   │                              │
   pulls toward                       pulls toward                   pulls toward
   CONFESS / REPAIR                   CONCEAL / AVOID                DEFEND / ANGER
   (guilt, repair_drive,              (exposure_anxiety,            (perceived_injustice
    trust/closeness)                   avoidance_drive,              vs guilt)
        │                              source_threat, cog_load)          │
        └──────────────► moral_tension = HOW HARD these pull AGAINST each other ◄────┘
                          (derived; high only when opposing pulls are BOTH strong)
        │
        ▼  the existing argmax selector resolves the conflict into ONE visible action
   confess · apologize · repair   |   lie · deflect · remain_silent · avoid   |   refuse/anger(feeds burst)
        │
        ▼  booked in POST_EFFECTS → relieves guilt/cog_load/exposure_anxiety, writes the ledger,
           updates suspicion/trust on the relevant relation rows → next tick the cues change.

Nightly sleep relieves the FAST states (stress) but the SLOW moral states persist
(serious guilt 72h survives the sleep reset) → "he slept it off but still feels bad."
```

---

## Control form (integrators / summing junctions / signed feedback)

```
LEGEND:  [Σg·u] finite event-gain deposit   (+)/(−) signed coupling   ∫ one-pole leaky integrator
         decay = 2**(−dt/half_life)         clamp [0,1]               ★ = M-J.0 implemented-first slice

  EVENTS (finite single-tick deposits, mapper channels)            COUPLINGS (sparse, spec §6; signs shown)
  ───────────────────────────────────────────────                 ──────────────────────────────────────
  lie_committed,harm_done,betrayal,promise_broken ─►[Σg]─►(+)         ┌──────────────────────────────────┐
  secret_kept_from_trusted,witnessed_own_harm     ─►[Σg]─►(+)         │  ★guilt ──(+)──► repair_drive     │
                                                       │             │  ★guilt ──(+)──► rumination        │
                                            ┌──────────▼─────────┐   │  ★guilt ──(+)──► stress            │
                                  ★guilt ──►│ ∫ decay(guilt_hl)  │──►│  ★guilt ──(−,empathy-gated)► anger │ damps outburst
                                  relief◄───│ confess/repair/apol│   │  perceived_injustice ──(−)► guilt │ "felt justified"
                                  (−)       └────────────────────┘   └──────────────────────────────────┘
  direct_question,accusation,suspicion_raised ─►[Σg]─►(+)             ┌──────────────────────────────────┐
  secret_cued,secret_exposed,authority_probe,    [stronger for       │  ★exposure_anxiety ─(+)► stress   │
  witness_present                                 accusation]        │  ★exposure_anxiety ─(+)► avoidance_drive
                                            ┌──────────▼─────────┐   │  suspicion[src] ─(+,src-present)► exposure_anxiety
                       ★exposure_anxiety ──►│ ∫ decay(exa_hl,60m)│──►│  cognitive_load ─(+)► stress      │
                       relief◄──────────────│ confess/forgiven/  │   │  rumination ─(+)► stress, fatigue │
                       (−)                  │ threat_removed     │   │  rumination ─(+)► cognitive_load  │
                                            └────────────────────┘   │  perceived_injustice ─(+)► anger, resentment[src]
                                                                     └──────────────────────────────────┘
  (repair_drive, avoidance_drive, rumination, cognitive_load_from_lies, perceived_injustice:
   each the SAME ∫ leaky integrator with its own long half-life and event/coupling fan-in — omitted
   for space; edges enumerated in spec §5/§6.)

  ── TWO POSITIVE LOOPS THAT MUST BE Jury/spectral-CHECKED BEFORE CALIBRATION ──────────────────────────
   ★(1) secret.salience ─(+)─► guilt ─(+)─► exposure_risk ─(+)─► secret.salience
        broken by SATURATING couplings f_guilt,f_expo (1+k·x/(1+x)) so salience can't pin at 1.0 (review R4)
    (2) rumination ─(+)─► stress ─(+)─► (worse lying) ─(+)─► exposure_risk ─(+)─► stress ─(+)─► rumination
        must be net-contractive (Σ loop gain < 1) OR carry an extinction term (reuse burst_extinction)
   Criterion (engine/stability.py): spectral radius of the moral+core submatrix < 1; per-loop Jury margin > 0.
   NOTE: moral couplings DEFAULT 0 → at zero gain the loops are inert and existing goldens are byte-identical.

  ── DERIVED OBSERVABLE (read-only; NOT an integrator, NOT stored) ─────────────────────────────────────
   P_confess  = w1·guilt + w2·repair_drive + w3·trust[target]                    (pull: own up)
   P_conceal  = w4·exposure_anxiety + w5·avoidance_drive
              + w6·source_threat(target) + w7·cognitive_load_from_lies           (pull: hide)
   P_defend   = w8·perceived_injustice                                           (pull: it's unfair)
   moral_tension = clamp01( g_mt · CONFLICT(P_confess, P_conceal)                 # high only when BOTH high
                          + g_inj · P_defend · guilt )                            # injustice fighting guilt
        CONFLICT(a,b) = 2ab/(a+b+ε)   (harmonic-style: ≈0 if either pull ≈0; large only when both large)
   → NOT fear, NOT guilt, NOT stress: it is the bounded magnitude of incompatible internal pulls.

  ── ACTION POTENTIALS (deterministic; bias the selector, NEVER if-then scripts; spec §7) ──────────────
   confess   ↑ guilt, repair_drive, trust[target], (cog_load if burden too high)   ↓ exposure_anxiety, source_threat, perceived_injustice, suspicion
   lie       ↑ exposure_anxiety, source_threat, suspicion, machiavellianism        ↓ guilt, repair_drive, trust, (cog_load if too hard)
   deflect   ↑ exposure_anxiety, cog_load, moderate suspicion, moral_tension        (inhibited by lie_skill)
   remain_silent ↑ exposure_anxiety, moral_tension, cog_load (can't choose)
   avoid     ↑ avoidance_drive, exposure_anxiety, source_threat, suspicion
   repair/apologize ↑ guilt, repair_drive, trust/closeness, empathy               ↓ exposure_anxiety, source_threat, perceived_injustice
   confide   ↑ guilt × trust[confidant] × (1−gossip_tendency)   ↓ rumination (safe unburden); gossip_tendency ↑ probe→exposure_anxiety (the leak)
   apologize also books RELATIONAL reparation: ↑ trust[target], ↓ resentment[target] (the loop closes through the relationship)
   selector = argmax over in-play actions vs thresholds.react.* — NO RNG, NO sampled probability.
   outburst stays on the EXISTING burst latch (anger,stress); moral states only FEED anger/stress, never a new burst gate.
```

## Role presets (same integrator, different parameters — spec §14, §11)

| State | role | half-life (placeholder) | drift | M-J slice |
|---|---|---|---|---|
| guilt | slow moral memory | minor 18h / serious 72h | 0 | ★ M-J.0 |
| exposure_anxiety | medium anxiety | 60min | 0 | ★ M-J.0 |
| repair_drive | slow motive | 24h | 0 | M-J.2 |
| avoidance_drive | medium motive | ~ exposure | 0 | M-J.2/.3 |
| rumination | slow replay | derived from guilt/unresolved | 0 | M-J.2 |
| cognitive_load_from_lies | medium load | 6h | 0 | M-J.1 |
| perceived_injustice | slow grievance | (relation-memory scale) | 0 | M-J.3 |
| suspicion (relation dim) | per-source memory | weak 48h / evidence 14d | 0 | M-J.3 |

## START vs END (review hooks)

- **START (cue):** a finite event deposit on the tick a moral cue lands (read off the frozen snapshot).
- **END (resolution):** the action booked in `post_effects` that relieves the driving states and writes
  the ledger — the loop closes through the *world* (changed cues next tick), not inside `update`.
- **Feedback signs:** all moral→stress/anxiety couplings are `+` (load), guilt→anger is `−` (remorse
  damps the outburst), perceived_injustice→anger is `+` and injustice→guilt is `−` (the grievance switch).
- **The one-tick latency** (spec §1.1): ledger changes from `post_effects(T)` are visible to selection at
  `T+1`; same-tick reflexes only via existing global-state couplings on the update path.

> **Definition of Done (per CLAUDE.md):** this diagram is updated TOGETHER with the code of each slice.
> M-J.0 implements only the ★ nodes/edges; the rest stay drawn-but-unwired (gains default 0) until their
> slice lands. A diagram detached from the code is worse than none.
