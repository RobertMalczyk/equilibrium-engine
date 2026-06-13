# Burst & saturation — two positive loops, one safety mechanism

> Spec: §1 (loop-stability invariant, saturation-bounded exception), §4 (relief-seeking urge term),
> §8 (burst & saturation subsection, loop inventory), §14 (coupling escalation factors).
> Design of record: `Ideas/burst_saturation_design_note.md` (private overlay repo).
> Status: IMPLEMENTED (M20, merged `3dcf4a3`), inert by default; M20.1 calibration in progress.
> The latched-provoker refractory edge (4th inhibitory edge) is added here (M20.1 topology stage,
> §3.5 of `burst_calibration_plan.md`). All magnitudes are calibration placeholders; neutral defaults
> (`0` / disabled) keep today's behaviour bit-identical.

## 1. Control form

### 1a. Loop inventory + the escalation nonlinearity

```text
            LOOP 1 (in-engine, anger <-> stress 2-cycle, POSITIVE,
                    with state-dependent ESCALATION on both edges)
            ┌──────────────────────────────────────────────────────────┐
            │       g·(1 + k_esc·stress)      ◄── the declared          │
            │   ┌────────────[×]◄──────────┐      NONLINEARITY:         │
            ▼   ▼                          │      edge strengthens      │
 inputs ──►(+)─►[∫ anger ]──┐         [∫ stress ]◄──(+)◄── hunger·g     │
 (insult,       decay_a     │          decay_s       ▲ ◄── fatigue·g    │
  frustr.·g)                │ g·(1 + k_esc·anger)    │ ◄── SEEKING stress cost (can't-find, NEW) ◄─┐
                            └────────[×]────────────►│                                             │
                                                     │                                             │
   Linear loop gain is FIXED by g, decay → poles never depend on inputs. The k_esc factor          │
   makes the LOCAL gain grow with the operating point: many coinciding drives lift the             │
   operating point → local gain crosses the Jury bound → spiral → clamp ceiling → BURST.           │
   k_esc = 0 (default) ⇒ exactly today's frozen Layer-2 linear loop.                               │
                                                                                                   │
   LOOP 2 (closes THROUGH THE WORLD, sign = environmental) — TWO return paths:                     │
   ┌── stress ──► [Σ urge_boredom] = w_b·boredom·nov + w_s·stress − w_f·fatigue   (w_s NEW)        │
   │                   │ ≥ theta_start                                                             │
   │                   ▼                                                                           │
   │              [SEEKING mode] ── world confirms ──► BUSY self_activity ──► stress −/tick        │
   │                   │                               (rich world: loop NEGATIVE — relief)        │
   │                   ├── no confirmation: +stress/tick ──────────────────────────────────────────┘
   │                   │   (barren world, return path 1: direct)
   │                   └── no confirmation: +frustration/tick ──► anger ──► stress
   │                       (return path 2: through the frustration chain — exists the moment
   └────────────────────    the urge reads stress; both paths SUM into the barren-world loop gain)
```

### 1b. The burst latch (integrate-and-fire at the loop level)

```text
                 ┌────────────────────────────────────────────────────────────┐
                 │              BURST LATCH (flip-flop, in runtime,           │
                 │              emitted in the debug trace like `mode`)       │
 anger  ──►[≥ theta_burst_enter.anger ]──┐                                    │
                                         ├─[AND]─[for burst_confirm_ticks]──► SET
 stress ──►[≥ theta_burst_enter.stress]──┘   (the LOOP plateau is the         │
                 │                            signature; a single-state       │
                 │                            spike must NOT arm it)          │
 anger  ──►[≤ theta_burst_exit]─────────────────────────────────────────────► RESET
                 │                            (hysteresis: exit < enter)      │
                 └───────────────┬────────────────────────────────────────────┘
                                 │ latched?
                                 ▼
              ┌───────────────────────────────────────────────────┐
              │ EXTINCTION term in update (while latched, any     │
              │ mode):  anger, stress += rate · (0 − x)           │  slow relaxation, ~"an hour"
              │ Boundedness: extinction dominates the ESCALATED   │
              │ coupling outside the saturated region.            │
              └───────────────────────────────────────────────────┘
                                 │ latched?
                                 ▼
              ┌───────────────────────────────────────────────────┐
              │ GATE EXTENSION (selector, §7 step 8):             │
              │   provoker (FIRST eruption arms latch): ordinary  │
              │     react.* thresholds + gate                     │
              │   provoker (RE-provokes WHILE LATCHED): refractory │
              │     edge — refractory_pressure × resentment[src]  │
              │     read NEGATIVE by outburst (4th inhibitory     │
              │     edge) -> no fresh max outburst; the spent      │
              │     fury yields to cold_response (sustained cold   │
              │     contempt / numbed withdrawal). Source-scoped   │
              │     to last_provocation_source; a NEW provoker     │
              │     still gets a full ordinary reaction.           │
              │   bystander: while LATCHED and                    │
              │     anger ≥ theta_displace (>> react.*),          │
              │     ANY SOURCED event this tick opens the         │
              │     reactive gate (a kind gesture included);      │
              │     sourceless (weather) never does —             │
              │     you cannot kick the rain.                     │
              │   displaced discharge target = the tick's event   │
              │     source; books resentment TRANSIENT/discounted │
              │     (no durable grudge on the innocent)           │
              │   DISPLACED only if: not itself a provocation     │
              │     (direct replies book full cost), HOSTILE      │
              │     (books +resentment; warm replies never        │
              │     tagged), target != remembered provoker        │
              │   while the gate is open, kindness_pressure is    │
              │     SUPPRESSED -> fury past the bar no longer     │
              │     hears the kindness; below the bar appraisal   │
              │     wins unchanged (theta_displace = THE dial)    │
              └───────────────────────────────────────────────────┘

 [0,1] clamp = the saturation ceiling: when the escalated loop goes locally unstable (rare input
 coincidence), the trajectory runs to the clamp, PLATEAUS, and the latch + extinction bring it back.
 Stability test for this regime = BOUNDEDNESS (trajectory returns), NOT poles.
```

## 2. Functional form (domain language)

```text
 An ordinary day: small annoyances come and go; the anger–stress loop is damped (Jury-stable)
 and everything decays back to calm.                       ── the nominal band, unchanged

 A bad day stacks up: he is tired AND hungry AND was mocked AND has been pacing the yard
 looking for ANYTHING to do and finding nothing (the looking itself wears him down — NEW).
        │
        ▼
 The angrier and more wound-up he gets, the harder each thing feeds the next (escalation) —
 too many drives at once and the temper loop stops damping and SPIRALS    ── escalation is real
        │
        ▼
 Fury peaks and HOLDS — white-knuckle, pinned at the top while the pressure lasts   ── plateau
        │                                                    (the burst latch is now SET)
        ├── the actual offender speaks (the FIRST time, which armed the latch) → the discharge
        │   lands on HIM (ordinary thresholds)
        │
        ├── the actual offender keeps mocking him WHILE the latch holds → he does NOT erupt afresh
        │   at each new taunt; the spent fury yields to sustained cold contempt / numbed withdrawal
        │   (the refractory edge — one episode, not seven identical explosions)
        │
        ├── an innocent — even kind Marta with her soup — happens to be there, and his fury is
        │   over the displacement bar → he SNAPS AT HER ("kicking the dog"), but it is rendered
        │   as displacement, and he does NOT come to hate her — no durable grudge is booked
        │
        ▼
 The pressure eases → the burst EXTINGUISHES itself over the next hour — he comes down slowly,
 spent, not reset                                            ── spike → hold → slow cool
        │
        ▼
 The latch releases; the loop is damped again; ordinary life resumes.
```

## 3. Loop signs & stability summary

| Loop | Path | Sign | Stability discipline |
|---|---|---|---|
| 1 | anger ⇄ stress (in-engine 2-cycle, `k_esc`-escalated) | + | Jury/poles in the nominal band (`k_esc` anchored at 0 reproduces frozen Layer-2); **boundedness/return** in the declared saturated regime |
| 2 | stress → urge → SEEKING → world → stress (return paths: direct stress cost AND frustration→anger→stress) | environmental: − (rich world, relief) / + (barren world, fruitless looking; both return paths sum) | closes through the world (no new in-engine edge); its positive branch lifts Loop 1's operating point |

Verification plan: measure the input co-occurrence distribution from real corpus runs; guarantee
linear stability for the measured frequent combinations (typically pairs) **at their operating
points** (the escalated local gain, not just the k_esc=0 gain); accept ≥3-way coincidences as the
burst trigger — bounded by saturation + the latch, by construction.

## 4. New config (all placeholders, neutral defaults)

| Param | Home | Neutral default |
|---|---|---|
| `action_params.seek_stimulus.per_tick.stress` | seeking cost (Loop 2 forward edge; per-tick while SEEKING, not at give-up) | `0` |
| `derived_weights.urge_boredom.stress` | relief-seeking (Loop 2 return edge) | `0` |
| `coupling_escalation.anger.stress`, `coupling_escalation.stress.anger` (`k_esc`) | the escalation nonlinearity (§14) | `0` (linear) |
| `theta_burst_enter.anger`, `theta_burst_enter.stress`, `theta_burst_exit`, `burst_confirm_ticks` | latch | disabled |
| `burst_extinction_rate` (or half-life) | extinction while latched | — |
| `theta_displace` | bystander gate extension (>> `react.*`, requires latch SET) | disabled |
| displaced-discharge relational discount | transient booking on the innocent | full discount |

## 5. Acceptance gates (each stage bit-identical before its params go live)

| Gate | Check |
|---|---|
| G0 ship inert | all defaults neutral → full suite + goldens byte-identical |
| G1 Loop 2 edges | with w_s/stress-cost enabled in a RICH mock world: stress descends (negative branch); in a BARREN world: monotone wind-up to the Loop-1 operating shift (positive branch); litmus untouched |
| G2 escalation | property test: with k_esc>0, low-state response identical to linear within tolerance; high coincident drive → local gain crosses Jury bound (computed, not assumed) |
| G3 boundedness | trajectory-returns property test: coincident drive → ceiling plateau → drive eases → state falls below `theta_burst_exit` within T and stays down (no re-ignition) |
| G4 latch discrimination | a single-state spike (ordinary insult burst) does NOT arm the latch; the litmus burst-vs-suppress contrast bit-identical |
| G5 displacement | latched + anger ≥ theta_displace + kind sourced event → displaced discharge, rendered AS displacement, bystander resentment delta ≈ transient (no durable grudge); below theta_displace → `positive_response` unchanged; sourceless weather never a target |
| G6 input co-occurrence | measured pair/triple frequency report from the 700-corpus runs, BEFORE calibrating k_esc (which combinations to guarantee is data-driven) |
| G7 latched-provoker refractory | while latched, repeated provocation from the SAME source yields ONE outburst then cold_response/numbed (not N fresh outbursts); unlatched and different-source paths bit-identical; with the edge inert (default) every path bit-identical |
