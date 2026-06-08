# Block diagram — multi-agent orchestrator / cross-agent router (eval/orchestrator.py)

> Maintained in two forms (spec §12): **control** (the cross-agent loop with an explicit unit delay,
> summing/route junctions) and **functional** (the two-phase cycle in domain language). Synchronized with
> `eval/orchestrator.py`. This is the **live-multi-agency FIRST SLICE** (spec §8 / §13): it makes one NPC's
> proactive `command_other` become another NPC's inbound `command` event. It is the generalization of the
> single-agent `eval/mock_world.py` reactive injector.
>
> **Boundary invariant:** the per-persona **engine stays a pure function** (`tick(runtime, t, event)`); it
> never reaches into another runtime. ALL cross-agent wiring lives HERE, outside the engine — exactly the
> seam `simulation.py` draws ("the loop closes in the game / a mock-world runner").

## I/O
`In:` a ROSTER `{agent_id → PersonaRuntime}` + per-agent inboxes (world events) + a deterministic
target-picker. `Out:` per-agent `DebugTrace`s, with each issuer's `command_other` realized as a routed
`command` event in the chosen subordinate's next-tick inbox.

## Functional form (the two-phase cycle)

```
  tick t:
    PHASE READ  — for agent in sorted(ROSTER):           # sorted = deterministic iteration
        tick(agent, t, inbox[agent].pop(t))              # each engine reads ONLY its own frozen snapshot
        if agent.selection.action == "command_other":    # an authority verb fired
            collect (issuer = agent)                      # NOT delivered yet (frozen)

    PHASE ROUTE — after ALL agents have ticked:
        for each collected issuer:
            target := pick_target(roster, issuer)         # deterministic (scripted / round-robin / seeded)
            enqueue command RawEvent(source=issuer, has_authority) ─► inbox[target][t+1]   # ONE-TICK DELAY

  tick t+1:
    target perceives the command  ─►  mapper → command_pressure → cooperate / refuse   (EXISTING pipeline,
                                       per-source: respect[issuer] → cooperate, resentment[issuer] → refuse)
    => the issuer's authority is now VISIBLE as the subordinate obeying or balking.

  BACK-EDGE: OFF in this slice. The subordinate's cooperate/refuse does NOT feed back to the issuer
             → the cross-agent path is pure FEEDFORWARD (command → obedience), no new loop.
```

## Control form (route junctions + the unit delay)

```
   ISSUER (Edda)                                     SUBORDINATE (target), at t+1
   -------------                                     ----------------------------
   duty ─►urge_command─►[≥θ_start]─► command_other      inbox[target][t+1]
                                        │                      │
                                        ▼ (PHASE ROUTE)        ▼  (EXISTING, untouched)
                          ┌─ pick_target (deterministic) ─┐    command_pressure ─┬─►(×)respect[issuer] ─► cooperate
                          │ emit command(src=issuer)      │    (=cmd value)      ├─►(×)resentment[issuer]─►┐
                          │ enqueue ─► inbox[target][t+1] ─┼── z⁻¹ (one-tick) ──► │                         Σ─► refuse
                          └────────────────────────────────┘  delay              ├─►(×)(1−respect)·nfc ───►┤
                                                                                  └─►(−k)──────────────► outburst (D11)

   (·) BACK-EDGE (OPTIONAL, OFF here):  subordinate.refuse/cold ──╳──► issuer  (would be a t+2 event;
        enabling it closes the authority↔resentment loop → a Jury-class stability concern; deferred stage-2)
```

## Invariants made visible
- **Pure engine, cross-agent wiring outside it.** The router only adds *inbound* events to inboxes; running
  one agent with no issuers in the roster is **exactly** today's single-agent behavior.
- **Determinism (project pillar):** sorted-roster iteration + deterministic target pick + the one-tick delay
  ⇒ no same-tick cross-agent dependency ⇒ bit-for-bit reproducible.
- **Synchronous-update invariant holds ACROSS agents:** because a command issued at `t` lands at `t+1`, no
  agent's within-tick state depends on another agent's same-tick output — the per-agent frozen snapshot is
  never read mid-flight. Phase order (READ then ROUTE) is the cross-agent analogue of freeze-then-commit.
- **No new loop (slice 1):** back-edge OFF ⇒ feedforward only. The only loop in play is the issuer's own
  self-limiting `duty → command_other → duty-relief` relaxation cycle (the boredom→seek class), intra-agent.
