# System wiring — what is connected to what (the whole topology)

> The single "what is wired to what" map. Every edge below is **declared in `calibration/defaults.yaml`
> or `engine/mapper.py`**; anything not listed is the neutral default (gain/coupling `0`, filter =
> identity) — the **sparse wiring** principle (spec §14). The *values* are calibration placeholders; the
> *topology* (which edges exist) is frozen design. Synchronized with the config + mapper.
> Per-subsystem internals: `mapper.md`, `relation_filter.md`/`affinity_filter.md`, `derived.md`,
> `update.md`, `potentials.md`, `action_selector.md`, `simulation.md`. Calibration loop: `calibration.md`.

## Signal flow (one tick, end to end)

```
 RawEvent(s) ─► MAPPER ─► tagged channels ─► FILTERS ─► gains ─►┌───────────────┐
   (M3)        (decompose)   (relational/    (relation→    │  STATES (11)   │── couplings ──┐
                              affinity/self)   affinity)    │  = integrators │◄──────────────┘
                                                            └──────┬─────────┘   (6 frozen edges)
                                                                   │ (post-commit state', step 5)
                                                                   ▼
                                                        DERIVED read-outs (M5) ── biases, urges, irritability
                                                                   │
                                              ┌────────────────────┼─────────────────────┐
                                              ▼                                           ▼
                                     POTENTIALS (M7)                                 URGES {boredom,fatigue}
                                     (state/derived × trait)                              │
                                              └──────────────► SELECTOR (M8) ◄────────────┘
                                                                   │ chosen action
                                                                   ▼
                                                   POST-EFFECTS ─► back into STATES (step 9)
```

> **M-MEM (multi-event per tick).** `RawEvent(s)` above is a LIST: a tick may carry several events. The
> MAPPER+FILTERS run **per event**; `simulation.tick` MERGES the results into the effective input, where a
> channel holds a **list** of inputs (several sources may fire the same channel), and `update` SUMS them.
> The per-source reactive signals (reaction_target, last_provocation_source) key on the **primary** event —
> the strongest provoker on the tick. A ≤1-event tick is byte-identical with the pre-M-MEM engine. See
> [`../m_mem_PLAN.md`](../m_mem_PLAN.md).

## 1. Mapper: event type → channels (engine/mapper.py)

| Event | Channels (class) |
|---|---|
| `food_given` | `food_nutrition`(self) · `preference_match`(affinity, target=item) · `repetition`(self) · `novelty`(self) |
| `insult` | `insult`(relational, source, −) |
| `help` | `help`(relational, source, +) |
| `command` | `command`(relational, source, authority param) — **MVP-active (GATE 3, implemented)** |
| `nightfall` | `night`(self) — the day/night signal → `sleep_pressure` (M7.5 Part B; world-supplied, like `activity`) |

Unknown events → no channels (no guessed inputs). `command` = MVP-active obedience (GATE 3, below);
`praise`/`promise_*`/`threat` etc. = stage 2.

## 2. Channel → state gains (input→state edges; signed)

```
food_nutrition ──(−0.50)──► hunger
preference_match ─(+0.40)─► satisfaction      preference_match ─(−0.30)─► frustration
insult ──(+0.35)──► anger                     insult ──(+0.20)──► frustration
repetition ─(+0.30)─► boredom                 novelty ──(−0.30)──► boredom
   relational deposits, booked on relations[source]:
insult ──(+0.25)──► resentment[src]           help ──(−0.15)──► resentment[src]
help ──(+0.20)──► trust[src]
   GATE 3 (implemented):
command ──(+0.20, ×low respect[src] via relation_filter)──► frustration   (+ transient command_pressure → obedience potentials, §6)
```

## 3. State → state couplings (THE 6 FROZEN EDGES, all +; spec §8)

```
   hunger ─(0.02)─┐
   fatigue ─(0.03)┼──► stress ◄─(0.03)── anger          ┌── ONLY FEEDBACK LOOP ──┐
                  │                        ▲             │  anger ⇄ stress (2-cycle)│
   boredom ─(0.04)─► frustration ─(0.05)─► anger ────────┴──────────────────────────┘
                                                          feedforward INTO the loop:
                                                          hunger,fatigue→stress; boredom→frustration→anger
   Stability (Jury, re-check on gain change): g(anger→stress)·g(stress→anger) < (1−dec_stress)(1−dec_anger)
```

## 4. Drifts (accumulators rise on their own)

`hunger +0.0010` · `fatigue +0.0015` · `boredom +0.0040` (idleness bores). Emotions drift 0 (decay to 0).
`duty +drift` — **authority drive state** (decay+drift; long half-life so `dt` unchanged; joins NO coupling).
Drift is `0` by default (sparse) — positive ONLY for an authority persona (Edda); others keep `duty ≡ 0`.
`sleep_pressure` — **sleep drive state** (decay; setpoint 0; NO drift; joins NO coupling). Raised by the
`night` channel (`nightfall`); discharged in SLEEP. `0` unless the world sends nightfall (M7.5 Part B).

## 5. State → derived read-outs (per tick, NOT state; engine/derived.py)

```
effective_self_control = self_control − 0.30·fatigue − 0.30·stress
irritability           = 0.50·stress + 0.40·frustration + 0.20·hunger
dissatisfaction        = 0.60·frustration − 0.50·satisfaction
urge_boredom           = 0.90·boredom − 0.50·fatigue        ◄ drive reads boredom DIRECTLY (not frustration)
urge_fatigue           = 1.00·fatigue
urge_command           = w·duty·nfc_factor                  ◄ AUTHORITY drive: reads the duty STATE in its 2nd
                         nfc_factor = 1 + k·(need_for_control − ref)   role; need_for_control = TEMPO modulator
                                                            (mirror of novelty_seeking → urge_boredom, D5)
affective_bias[src]    = 0.50·trust + 0.40·respect − 0.70·resentment    (per relation source)
```

## 6. State/derived × trait → reactive potentials (engine/potentials.py)

```
complain      = 0.70·dissatisfaction + 0.40·frustration + 0.15·hunger + 0.40·(dissatisfaction×pride)
outburst      = 1.20·(anger×(1−eff_self_control)) + 0.20·irritability − k·(command_pressure × respect[command.source])
                ◄ INHIBITORY (signed) edge: a respected commander's order suppresses venting → obedience is robust
                to ambient/residual anger (D11 Branic). Same term cooperate reads with +; here it carries −.
                Neutral by default (no order → 0; low respect → small; high respect → strong). Scoped to outburst only.
cold_response = 1.10·(anger×stoicism) + 0.20·frustration   ◄ prisoner-bias carrier (resentment[guard] amplifies
                the insult → anger↑ → cold_response↑). Crosses via a TEMP per-persona react.cold_response≈0.24
                for Cichy (the shared 0.50 collides with stoic Lutek at 0.40); decouples prisoner from burst.
                STOPGAP for undifferentiated insult→anger; real fix = pride→insult-anger (deferred milestone).
```
Invariant: every term has ≥1 state/derived/relation factor; traits only MODULATE (no `trait×trait`).

**Obedience (GATE 3, implemented).** `cooperate`/`refuse` are command-gated, per-source; `command_pressure`
is transient (this tick's command, `0` if no order). This REPLACED the old un-gated rows (`refuse = 0.80·
(frustration×nfc) + 0.50·resentment_max`, `cooperate = (none)`) — refuse no longer fires in a vacuum:
```
cooperate = command_pressure × respect[command.source]                          (gratitude may modulate)
refuse    = command_pressure × ( resentment[command.source]
                              + (1−respect[command.source]) × need_for_control
                              + frustration × need_for_control )
```
Invariant extends: `command_pressure` is a permitted gating factor (no order → 0, no obedience in a vacuum);
source-keyed (`resentment[command.source]`, NOT the `resentment_max` aggregate — resenting Wojsław must not
break obedience to Edda). traits only MODULATE. Ontology note: `refuse` = "won't obey an **order**";
resentment WITHOUT an order surfaces as `cold_response` (a cold reception), not `refuse` — see §D prisoner_bias.

## 7. Drives: state → proactive action (registry; engine/action_selector.py)

```
boredom ─(urge_boredom ≥ theta_start)─► seek_stimulus      fatigue ─(urge_fatigue ≥ theta_start)─► rest
duty ─(urge_command ≥ theta_start)─► command_other   ◄ INSTANTANEOUS (not seeking, not BUSY dwell): fires once
                                                       from IDLE → COOLDOWN; drive present for all, fires only
                                                       where duty>0 (authority). Other-directed: routed cross-agent (§10).
sleep_pressure ─(sleep_urge ≥ theta_start)─► sleep   ◄ enters SLEEP mode (M7.5 Part B). sleep_urge = w·sleep_pressure
                                                       + w·fatigue − arousal; fires only after nightfall (else 0).
```

## 8. Action → state post-effects (selector writes back; step 9 / BUSY per-tick)

```
outburst:      anger −0.30 (global discharge) ; resentment[target] +0.15 (booked on the provoker)
command_other: duty −Δ (discharge → the accrue/discharge arc) ; satisfaction +δ ("things are in hand")
               ◄ a PROACTIVE action's post-effect (the selector now books configured post_effects for
                 proactive starts too; seek_stimulus/rest carry none → unchanged)
seek_stimulus (BUSY/tick): boredom −0.05, satisfaction +0.03, fatigue +0.01
rest          (BUSY/tick): fatigue −0.05, satisfaction +0.01
sleep         (SLEEP/tick, M7.5 Part B): anger/stress/frustration ↓↓ → 0, satisfaction → 0, fatigue ↓↓,
              self_control ↑, hunger ↑(slow), sleep_pressure ↓↓ (discharge). trust/respect/resentment UNTOUCHED
              (slow causes persist). Wakes on end_when_below{fatigue,sleep_pressure} or a strong provocation.
```

## 9. Filters (per channel class; engine/relation_filter.py, affinity_filter.py)

```
relational channel (has source) ─► relation_filter: × (1 + bias_gain·polarity·affective_bias[src]) × social_exposure(public)
                                                       betrayal exception keys on trust (lands harder when trust high)
affinity channel  (has target)  ─► affinity_filter:  × valence (valence_gain=0 in MVP → identity)
self channel       (neither)    ─► identity (passes through unchanged)
```

## 10. Cross-agent routing (the ORCHESTRATOR, outside the pure engine; eval/orchestrator.py)

```
   for agent in sorted(ROSTER):  tick(agent, t, inbox[agent][t])     # each engine reads only its own snapshot
   PHASE ROUTE (after all ticked): for each agent that SELECTED command_other:
        target := pick(roster) (deterministic)
        enqueue command RawEvent(source=issuer) ─► inbox[target][t+1]      ◄ ONE-TICK DELAY (z⁻¹)
   tick t+1: target perceives the command ─► mapper → command_pressure → cooperate/refuse  (EXISTING, untouched)
```
- The engine stays a **pure per-agent function**; all cross-agent wiring lives in the orchestrator (the
  generalization of `eval/mock_world.py`). The one-tick delay preserves the synchronous / frozen-snapshot
  invariant ACROSS agents (no same-tick cross-dependency) → bit-for-bit determinism (sorted roster +
  deterministic target pick). **Back-edge OFF** (no subordinate→issuer feedback) → pure feedforward, no new loop.

## Invariants visible here
- **Sparse + frozen topology:** only the edges above exist; the rest are neutral defaults. Calibration
  tunes *values*, never adds edges.
- **One source of truth:** the input→state and state→state equations live only in `update`; this map is a
  *view*, not a second computation.
- **Synchronous:** couplings read the frozen start-of-tick snapshot, so equation order can't change the result.
