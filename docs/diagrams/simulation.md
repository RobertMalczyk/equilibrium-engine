# Block diagram — simulation (M9, the tick orchestrator)

> Two forms (spec §12): **control** (the snapshot-freeze + mode flip-flop + write-back loop) and
> **functional** (the canonical 10-step tick cycle). Synchronized with `engine/simulation.py`.
> **Invariants made visible:**
> - **The ONLY runtime mutator.** Every other member is a pure function; state changes here and only here
>   (two commits: step 5 update-delta, step 9 post-effects).
> - **Frozen snapshot ⇒ synchronous update.** Everything in a tick reads the start-of-tick snapshot, so
>   equation order can't change the result. `derived` runs twice (pre = interpret, post = inclined-to-do).

## Canonical tick cycle (functional)

```
TICK(t):
  1. snapshot   = freeze(global_state, relations, mode)        # FROZEN reference for the whole tick
  2. derived_pre = derived(snapshot)                            # how it INTERPRETS a stimulus
  3. if event@t: raw = mapper(event, history); eff = affinity_filter(relation_filter(raw, snapshot, derived_pre))
  3b. is_provocation = event raises anger/frustration OR gesture from resented source (resentment>=theta)  # D11
      recent_provocation = is_provocation OR last_provocation_t within reactive_window_ticks   # D5-1c + D11 gate
      recovering = (mode==IDLE AND NOT recent_provocation)                       # D11 ambient idle homeostasis
  4. delta      = update(snapshot, eff, derived_pre, mode, recovering)  # the ONLY state equations
  5. commit(delta); clamp ─────────────────────────────► state', relations'      ◄── 1st write-back
  6. derived_post = derived(state')                            # what it is INCLINED to do
  7. potentials = potentials(state', derived_post);  urges = {boredom,fatigue} from derived_post
  8. sel        = selector(potentials, urges, mode, cooldowns) # shared selector + arbitration
  9. commit(sel.post_effects); clamp; mode/cooldown transition ► state''          ◄── 2nd write-back
 10. log.append(event); cooldowns.tick(); COOLDOWN→IDLE @0; debug.emit(tick)
```

## Control form (freeze → compute → write-back, with the mode flip-flop)

```
        ┌───────────────────────────── frozen snapshot (step 1) ─────────────────────────────┐
        │                                                                                     │
        ▼                                                                                     │
   [derived_pre]→[mapper+filters]→[UPDATE: Σ gain·input + Σ coupling·snapshot + drift + busy]  │ reads snapshot,
        (the only place state evolves)                          │                             │ never the in-progress
                                                                ▼                             │ value (synchronous)
                                                  commit+clamp ► state' ─►[derived_post]─►[potentials/urges]
                                                                                  │
                                                                                  ▼
                                                                            [SELECTOR] ─► action + post_effects
                                                                                  │
                                                                  commit+clamp ◄──┘ (write-back, step 9)
                                                                                  │
   ┌──────────── MODE FF (transition in simulation._apply_transition + tick) ─────────────────┐
   │  IDLE --reactive-->IDLE     IDLE --urge>=theta_start-->SEEKING   (M7 Step 2: intent, NOT BUSY)
   │  SEEKING --activity event-->BUSY (ENGAGE: kind+novelty)   SEEKING --timeout-->IDLE (give up)
   │  SEEKING --reactive-->IDLE (a provocation interrupts the search)   SEEKING --continue-->SEEKING (+frustration)
   │  BUSY --END/interrupt-->COOLDOWN   BUSY --in-passing/continue-->BUSY   COOLDOWN --(counter=0)-->IDLE
   └────────────────────────────────────────────────────────────────────────────────────────────┘
```

## I/O
`In:` PersonaConfig + Scenario (+ optional n_ticks). `Out:` (PersonaRuntime, DebugTrace). Mutates the
runtime; emits one TickTrace per tick (the bit-exact golden/debug contract). dt derived from half_lives.
