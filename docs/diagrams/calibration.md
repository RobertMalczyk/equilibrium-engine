# Block diagram — calibration loop (M4 step 3, the optimizer)

> **Diagram CLASS note (spec §12).** This is **not** a dynamics subsystem — there are no states,
> integrators, or signed state→state couplings here. It is a **closed optimization loop**, so it gets
> a **control/optimization-flow** diagram, not the integrator/summing-junction notation used by
> `update.md` / `action_selector.md`. Both forms still apply: a **functional** tuning cycle and a
> **control view** (candidate ↔ cost feedback, optimizer as the controller, loss as the cost signal).
> Synchronized with `engine/calibration.py`.
>
> **Invariants made visible:**
> - The **plant is pure/deterministic** (`loss` → `simulate` → `metrics` → `expectations`); the
>   **optimizer is the only impure, stateful part** (CMA-ES covariance + RNG seed). cma/SALib never
>   leak into `loss`/`simulate`/engine (same rule as numpy).
> - The loop is **parameterized by a FREE-SET**; **layer 1** is its first instance (free = `half_lives`).
> - It **never overwrites `defaults.yaml`** — it emits `calibrated_layer1.yaml` with provenance, for
>   deliberate human promotion (spec §16: human curates, doesn't run).

## Functional form (the tuning cycle)

```
                   param_bounds (half_lives ranges + ordering)         [config = data]
                                   │
                                   ▼
   (0) SCREEN  ── Morris elementary effects (SALib) ──► mu*[param] ──► FREEZE inert params
        |  ~traj·(D+1) loss() calls (cheap; captures interactions)         │  (active free-set ⊂ half_lives)
        ▼                                                                  ▼
   (1) PROPOSE ── CMA-ES proposes a candidate (normalized [0,1]^D, mapped to bounds) ◄──────────┐
                                   │                                                             │
                                   ▼                                                             │
   (2) EVALUATE ── loss(params) [PURE plant] ──► LossBreakdown{total, components, weighted}      │
                     simulate→metrics→expectations over the benchmark                            │
                                   │                                                             │
                                   ▼                                                             │
   (3) cost = weighted total ─────────────────────────────► CMA-ES updates mean+covariance ─────┘
                                                              (until maxiter / convergence)
                                   │
                                   ▼ best candidate
   (4) ACCEPT ── layer-1 success = weighted loss ↓  AND  monitored (weight-0) behavior/ranking
                  did NOT degrade sharply  ──►  pass? write : reject
                                   │
                                   ▼
   (5) EMIT  calibrated_layer1.yaml  { values + RUN METADATA: seed, frozen params (Morris),
             per-component breakdown baseline-vs-best, input-config provenance }      ──► (human promotes)
```

## Control view (candidate ↔ cost feedback)

```
        ┌───────────────────────── OPTIMIZER (controller; impure: covariance + seed) ─────────────────────┐
        │  CMA-ES: maintains a search distribution over the active half_lives (normalized)                 │
        └───────────────┬───────────────────────────────────────────────────────────▲────────────────────┘
                        │ candidate params θ                                          │ cost J(θ)  (scalar to minimize)
                        ▼                                                             │
        ┌───────────────────────────── PLANT (pure, deterministic) ──────────────────┴────────────────────┐
        │  θ ─► simulate(θ) ─► trace ─► metrics ─► expectations(predicates) ─► loss components ─► weighted J │
        │      (param-injection: override half_lives, RE-DERIVE dt/decay; game-time horizon)                 │
        └────────────────────────────────────────────────────────────────────────────────────────────────┘

   Reference / setpoint:   J* = 0  (all weighted predicates satisfied).  Error driven down by the controller.
   Constraints:            range + ordering are SOFT, inside regularization_loss (declarative, in config).
                           If the optimizer "cheats" (keeps violating), the knob is the stability/
                           regularization WEIGHT, NOT reparameterization (keep structure in the loss).
   Fuel (layer 1):         the time-scale ANCHOR (satisfaction glow half-decay ≈ 45 s, wiring.md/§8 of
                           the config) makes baseline J > 0, so run_layer1 actually MOVES a half-life
                           (satisfaction 35→44) to meet it — accepted (behavior/ranking intact). The
                           anger-cooldown target is a LATER (gain) layer (known_divergences D6).
```

## Layering (spec §9) — the free-set is the only thing that changes per layer

| Layer | Free-set | Weighted components | Frozen |
|---|---|---|---|
| **1 (here)** | `half_lives` | stability, curve/timing, regularization | gains, couplings, thresholds, traits |
| 2 (later) | single blocks (gains in isolation) | + behavior | half_lives (now fixed), the rest |
| 3 (later) | local loops, couplings | + ranking | earlier layers |
| … | progressive, freezing earlier layers | global fine-tune last | — |

Same loop, different free-set/weights. `behavior`/`ranking` are **computed and logged from layer 1**
(diagnostics), penalized only from the layer that owns them.

## Determinism
`loss`/`simulate` are bit-for-bit deterministic. The **optimizer is not** (CMA-ES RNG) — it is seeded
for reproducibility, and the seed is recorded in `calibrated_layer1.yaml`. Determinism guarantees apply
to the plant, not the search.
