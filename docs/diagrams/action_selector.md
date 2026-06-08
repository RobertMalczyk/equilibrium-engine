# Block diagram — shared action selector (M8)

> Maintained in two forms (spec §12): **control** (summing junctions, comparators, mode flip-flop,
> signed feedback) and **functional** (the cycle in domain language).
> Synchronized with `engine/action_selector.py` + `engine/simulation.py` (mode transitions).
> Top rule (§7): **threshold = "is it in the running", argmax = "which of the admitted ones is
> strongest"**. Invariant: **state ALWAYS updates** (tick steps 4–5); arbitration gates only the
> action/mode choice — hence a series of small pokes accumulates state until it crosses `theta_interrupt`.

## Member inputs / outputs

```
IN:  potentials (reactive, [0..1])       <- M7 potentials.compute
     urges {boredom, fatigue} ([0..1])   <- derived_post (M5)
     global_state' ([0..1])              <- after commit (step 5)
     mode, active_action                 <- runtime (prev mode)
     thresholds, drives                  <- config (placeholders from calibration)
OUT: ActionSelection{action, score, kind, interrupted, post_effects, explanation}
     (mode/cooldown follow from (prev_mode, kind, interrupted) in simulation._apply_transition)
```

## Functional form (the cycle in domain language)

```
potentials ──► [recent_provocation? else none] ──► [gate per action: p ≥ theta_react(p)] ──► argmax ──► max_react (or none)
               # recent_provocation = event this tick OR within reactive_window_ticks (D5 step 1c): a reply needs a provocation
urges      ──► [gate: max(urge) ≥ theta_start] ──────────────────► proactive candidate (NOT provocation-gated)

                       ┌──────────────── ARBITRATION by mode ───────────────┐
   mode = BUSY:        │ satisfaction ≥ theta_satiation OR fatigue ≥ th_fat  │→ END  → COOLDOWN  (kind=proactive)
                       │ elif max_react ≥ theta_interrupt                    │→ INTERRUPT → COOLDOWN (reactive, interrupted)
                       │ elif max_react ≥ theta_react                        │→ reactive "in passing", activity CONTINUES
                       │ else                                               │→ continue (kind=continue)
   mode = COOLDOWN:    │ max_react ≥ theta_react ? reactive : neutral        │  (start blocked)
   mode = IDLE:        │ max_react ≥ theta_react      → reactive (world first)│
                       │ elif max(urges) ≥ theta_start→ START proactive:       │
                       │     seeking drive  → SEEKING ; self-supplied → BUSY ; │
                       │     INSTANTANEOUS (command_other) → fire once→COOLDOWN│
                       │ else                         → neutral/positive_resp.│
                       └──────────────────────────────────────────────────────┘
                                              │
                                              ▼
                       post_effects (reaction cost) ──► commit (step 9) ──► mode transition
```

**Reaction cost (post_effects, M2).** A reactive action books two kinds of delta: a **global** one
(e.g. `outburst: anger −0.30`, discharge) and a **relational one on the reaction's TARGET** —
`reaction_target = source` of this tick's event (e.g. `outburst: resentment[source] +0.15`). The
relational delta exists only when `source_relations` is in config **and** `reaction_target ≠ None`;
otherwise neutral (`{}`). This is the "reaction aimed at the source" from §8: an outburst deepens
resentment toward whoever provoked it.

## Control form (summing junctions / comparators / flip-flop)

```
   p_complain ─►(−)─►┐          theta_react.complain
   p_outburst ─►(−)─►│          ...                     ┌── argmax(p ≥ θ) ──► max_react ──► [theta_interrupt] ─► R_interrupt
   p_cold     ─►(−)─►│  comparators per action ────────►┤
   p_coop     ─►(−)─►│                                   └── (max_react ≥ theta_react) ─────► R_react
   p_refuse   ─►(−)─►┘

   urge_boredom ─►(−)─►┐ theta_start
   urge_fatigue ─►(−)─►┤ ──► max(urge) ≥ theta_start ─► R_start
   urge_command ─►(−)─►┘ (authority drive; fires command_other, an INSTANTANEOUS proactive → COOLDOWN)

   END = (satisfaction ≥ theta_satiation) OR (fatigue ≥ theta_fatigue_end)

   ┌─────────────── MODE FLIP-FLOP (FF: IDLE / SEEKING / BUSY / COOLDOWN) ────────┐
   │  IDLE  --R_react-->            IDLE   (reaction, the world has priority)      │
   │  IDLE  --R_start (seeking)-->  SEEKING (M7 S2: the seek INTENT, not BUSY)     │
   │  IDLE  --R_start (self-sup.)-> BUSY    (rest)                                 │
   │  IDLE  --R_start (instant.)--> COOLDOWN(command_other: fire once, book        │
   │                                         post_effects; cooldown rate-limits)   │
   │  SEEKING --activity confirm--> BUSY    (ENGAGE: kind+novelty)                 │
   │  SEEKING --timeout-->          IDLE    (give up; keep frustration)            │
   │  SEEKING --reactive-->         IDLE    (a provocation interrupts the search)  │
   │  BUSY  --END-->                COOLDOWN(cooldown := action.cooldown)          │
   │  BUSY  --R_interrupt-->        COOLDOWN(interrupt + reaction)                 │
   │  BUSY  --R_react & !interrupt->BUSY   (reactive "in passing")                 │
   │  BUSY  --else-->               BUSY   (continue)                              │
   │  IDLE  --START sleep (sleep_urge≥θ_start)--> SLEEP (M7.5 Part B: the night reset) │
   │  SLEEP --end_when_below{fatigue,sleep_pressure}--> COOLDOWN (rested -> wake)     │
   │  SLEEP --max_react ≥ theta_interrupt-->        COOLDOWN + reactive (wake-on-threat)│
   │  SLEEP --else-->                SLEEP  (sleep on; mild stimulus ignored)         │
   │  COOLDOWN --(counter=0)-->      IDLE                                           │
   └─────────────────────────────────────────────────────────────────────────────┘

   Feedback (signs): potentials and urge are computed from the post-update state (step 7),
   so gating does NOT block accumulation — the accumulation loop is outside the selector,
   in update (M6). This realizes "pestering eventually interrupts".

   Source of the boredom urge: urge_boredom = f(boredom, −fatigue) — it reads the `boredom`
   state DIRECTLY (drive = state in its second role, §4/§8), NOT via `frustration`. Hence the
   proactive START ("a bored character seeks stimulus") is not wired onto the reactive
   frustration→complain path; the boredom→frustration edge lives separately (the
   boredom→frustration→anger chain in update).
```

## Threshold map (placeholders — `calibration/defaults.yaml`)

| Spec symbol         | Config key                       | Role |
|---------------------|----------------------------------|------|
| `theta_react(action)` | `thresholds["react.<action>"]`   | reactive "in the running" |
| `theta_interrupt`   | `thresholds["interrupt.<action>"]`| interrupt an activity in BUSY |
| `theta_start`       | `thresholds["urge_start"]`       | START of a proactive activity |
| `theta_satiation`   | `thresholds["satiation"]`        | END of an activity (satiation) |
| `theta_fatigue_end` | `thresholds["fatigue_end"]`      | END of an activity (fatigue) |

Two personas in the same scenario play differently because the same thresholds act on a **different
state** (different traits → different potentials/urge), not because they have different `if`s.
