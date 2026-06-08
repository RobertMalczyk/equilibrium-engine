# Block diagram — derived (M5, combinational read-outs)

> Maintained in two forms (spec §12): **control** (summing junctions, gains, clamps — no integrator)
> and **functional** (the read-outs in domain language). Synchronized with `engine/derived.py`.
> **Invariants made visible:**
> - **Pure / combinational — NOT state.** No memory, no integrator; a function of one snapshot only.
> - **Called 2×/tick:** `pre` (after the snapshot — how the character *interprets* a stimulus) and
>   `post` (after the update — what it is *inclined to do*). Same function, two inputs.
> - **Weights from config** (neutral default 0); a missing weight contributes nothing.
> - **No traits here.** These read-outs are state-derived; trait *modulation* lives in `potentials` (M7).

## Member inputs / outputs

```
IN:  global_state ([0..1]), relations (per source), config.derived_weights
OUT: DerivedSnapshot{
        effective_self_control, irritability, dissatisfaction : [0..1]
        urge_boredom, urge_fatigue, urge_command              : [0..1]   # proactive drives (§8)
        arousal, sleep_urge                                   : [0..1]   # night/sleep (M7.5 Part B)
        affective_bias : dict[src, [-1..1]]
        negative_bias  : dict[src, [0..1]]
     }
```

## Functional form (the read-outs)

```
effective_self_control = clamp01( self_control − w·fatigue − w·stress )      # a momentary dip, not a state
irritability           = clamp01( w·stress + w·frustration + w·hunger )
dissatisfaction        = clamp01( w·frustration − w·satisfaction )

urge_boredom           = clamp01( w_b·boredom·nov_factor − w_f·fatigue )   # ★ drive = boredom in its 2nd role
                         nov_factor = 1 + k·(novelty_seeking − ref)        # D5: per-persona TEMPO (default 1)
urge_fatigue           = clamp01( w·fatigue )
urge_command           = clamp01( w_d·duty·nfc_factor )                    # ★ AUTHORITY drive = duty in its 2nd role
                         nfc_factor = 1 + k·(need_for_control − ref)       # TEMPO (mirror of urge_boredom; default 1)
arousal                = clamp01( w·stress + w·anger + w·frustration )     # ★ sleep BLOCKER (wound-up => slow to sleep)
sleep_urge             = clamp01( w·sleep_pressure + w·fatigue − arousal ) # ★ SLEEP drive = sleep_pressure in its 2nd role
                                                                           # (M7.5 Part B; high arousal delays onset)

for each source src:
    affective_bias[src] = clamp_signed( w_t·trust + w_r·respect − w_res·resentment )
    negative_bias[src]  = clamp01( −affective_bias[src] )
```

## Control form (summing junctions / gains / clamp — no integrator)

```
   boredom ──►[w_b]──►[×nov_factor]──►(+)                    # nov_factor = 1+k·(novelty_seeking−ref): D5 TEMPO
                                       │
   fatigue ──►[w_f]──────────────────►(−)──►[clamp01]──► urge_boredom   # ★ reads boredom DIRECTLY; light brake
                                       ▲
                                       └─ (no frustration term — the old "urge via frustration" edge is removed)

   fatigue ──►[w]────────►[clamp01]────► urge_fatigue

   self_control ─►(+)
   fatigue ─►[w]─►(−)
   stress  ─►[w]─►(−)──►[clamp01]──► effective_self_control

   stress,frustration,hunger ─►[w·]─►(Σ)─►[clamp01]─► irritability
   frustration(+), satisfaction(−) ─►[w·]─►(Σ)─►[clamp01]─► dissatisfaction

   per source src:
     trust(+),respect(+),resentment(−) ─►[w·]─►(Σ)─►[clamp_signed]─► affective_bias[src] ─►(−)─►[clamp01]─► negative_bias[src]
```

## The boredom-urge fix (M3b) + the D5 tempo edge

`urge_boredom = clamp01(w_b·boredom·nov_factor − w_f·fatigue)` — the urge reads the **boredom state
directly** (drive = state in its second role, spec §4/§8), no `frustration` term. This is the proactive
output of `boredom`; the reactive output (`boredom → frustration → anger/complain`, the 0.04 coupling)
lives in `update` (see update.md). **D5:** `nov_factor = 1 + k·(novelty_seeking − ref)` (default identity)
modulates the boredom term, so the idle time-to-seek is ordered by `novelty_seeking` — a novelty-seeker acts
on boredom sooner, a low-novelty stoic later or never. The fatigue brake is kept LIGHT (the `fatigue→rest`
drive already diverts a tired NPC; a strong brake made the urge unreachable from idle — the D5 bug).
Coefficients `w_b`, `w_f`, `k`, `ref` are config placeholders (`derived_weights.urge_boredom`) owned by
calibration — only the *shape* is fixed here, not the magnitudes.
