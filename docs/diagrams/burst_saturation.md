# Burst & saturation — two positive loops, one safety mechanism

> Spec: §1 (loop-stability invariant, saturation-bounded exception), §4 (relief-seeking urge term),
> §8 (burst & saturation subsection, loop inventory). Design of record:
> `Ideas/burst_saturation_design_note.md` (private overlay repo).
> Status: SPEC/DIAGRAM ONLY — implementation pending. All magnitudes are calibration placeholders;
> neutral defaults (`0` / disabled) keep today's behaviour bit-identical.

## 1. Control form

### 1a. Loop inventory

```text
                 LOOP 1 (in-engine, anger <-> stress 2-cycle, POSITIVE)
                 ┌──────────────────────────────────────────────┐
                 │            g(stress->anger)                  │
                 │   ┌──────────────[×]<───────────────┐        │
                 ▼   ▼                                 │        │
 inputs ──►(+)──►[∫ anger ]──┐                    [∫ stress ]◄──(+)◄── hunger·g
 (insult,        decay_a     │ g(anger->stress)    decay_s       ▲  ◄── fatigue·g
  frustration·g)             └─────────[×]─────────────────────► │  ◄── SEEKING stress cost   ◄─┐
                                                                 │      (can't-find, NEW)       │
                                                                 │                              │
   LOOP 2 (closes THROUGH THE WORLD, sign = environmental)       │                              │
   ┌─────────────────────────────────────────────────────────────┘                              │
   │ stress                                                                                     │
   ▼                                                                                            │
 [Σ urge_boredom] = w_b·boredom·nov_factor + w_s·stress − w_f·fatigue        (w_s NEW, 0=neutral)
   │                                                                                            │
   ▼ ≥ theta_start                                                                              │
 [SEEKING mode] ──world confirms──► BUSY self_activity ──► stress −/tick   (loop NEGATIVE: relief)
   │
   └──no confirmation──► +stress/tick, +frustration/tick ───────────────────────────────────────┘
                                                           (loop POSITIVE: barren world winds up)
```

### 1b. The burst latch (integrate-and-fire at the loop level)

```text
                 ┌───────────────────────────────────────────────────────────┐
                 │                    BURST LATCH (flip-flop)                 │
 anger ──►[≥ theta_burst_enter]──[for burst_confirm_ticks]──► SET            │
                 │                                                           │
 anger ──►[≤ theta_burst_exit]───────────────────────────────► RESET         │
                 │              (hysteresis: exit < enter)                   │
                 └───────────────┬───────────────────────────────────────────┘
                                 │ latched?
                                 ▼
              ┌──────────────────────────────────────────────┐
              │ EXTINCTION term in update (while latched):   │
              │   anger, stress += extinction_rate · (0 − x) │   slow relaxation, "an hour"
              └──────────────────────────────────────────────┘
                                 │ latched?
                                 ▼
              ┌──────────────────────────────────────────────┐
              │ TARGET WIDENING (selector):                  │
              │   provoker:  fire at react.* (unchanged)     │
              │   bystander: fire only if anger ≥            │
              │              theta_displace  (>> react.*)    │
              │   displaced discharge books resentment       │
              │   TRANSIENT / discounted (no durable grudge) │
              └──────────────────────────────────────────────┘

 [0,1] clamp = the saturation ceiling: when the loop goes linearly unstable (rare input
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
 Too many drives hit at once → the temper loop stops damping and SPIRALS    ── escalation is real
        │
        ▼
 Fury peaks and HOLDS — white-knuckle, pinned at the top while the pressure lasts   ── plateau
        │                                                    (the burst latch is now SET)
        ├── the actual offender speaks → the discharge lands on HIM (ordinary thresholds)
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
| 1 | anger ⇄ stress (in-engine 2-cycle) | + | Jury/poles in the nominal band; **boundedness/return** in the declared saturated regime |
| 2 | stress → urge → SEEKING → world → stress | environmental: − (rich world, relief) / + (barren world, fruitless looking) | closes through the world (no new in-engine edge); its positive branch feeds Loop 1's operating point |

Verification plan: measure the input co-occurrence distribution from real corpus runs; guarantee
linear stability for the measured frequent combinations (typically pairs); accept ≥3-way coincidences
as the burst trigger — bounded by saturation + the latch, by construction.

## 4. New config (all placeholders, neutral defaults)

| Param | Home | Neutral default |
|---|---|---|
| `action_params.seek_stimulus.per_tick.stress` | seeking cost (Loop 2 forward edge) | `0` |
| `derived_weights.urge_boredom.stress` | relief-seeking (Loop 2 return edge) | `0` |
| `theta_burst_enter`, `theta_burst_exit`, `burst_confirm_ticks` | latch | disabled |
| `burst_extinction_rate` (or half-life) | extinction while latched | — |
| `theta_displace` | bystander discharge bar (>> `react.*`) | disabled |
| displaced-discharge relational discount | transient booking on the innocent | full discount |
