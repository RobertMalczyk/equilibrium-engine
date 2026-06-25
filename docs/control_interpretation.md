# Control-theory interpretation of the state update

> How to read every Equilibrium-Engine state as a **bounded discrete first-order system**. This is a
> *reading* of the existing equations (`engine/update.py`), not a new mechanism — no runtime behavior
> depends on this document. It exists to stop a recurring misreading: that an event is a Dirac spike, or
> that the additive gains are continuous-time rates. Companion: `docs/diagrams/update.md` (the block
> diagram + parameter-units note), and the deterministic diagnostic `eval/state_response_report.py`.

## 1. The update is a leaky first-order integrator

Every global state evolves by the same recurrence (`update.compute`, one instance per state):

```
x[n+1] = a · x[n] + b · u[n] + drift + couplings          a = 2 ** (-dt / half_life),   clamp [0,1]
```

- `a` = `decay` ∈ (0,1): the per-tick retention. `a = 2**(-dt/half_life)` (`engine/yaml_io.py`), with
  `dt = min(half_life)/nyquist_factor`. The half-life is the time to lose half the value with no input.
- `b · u[n]` = a **gated event deposit**: `b` is the per-event gain, `u[n]` the (finite) event value on
  tick `n`. `drift` is a constant per-tick accumulation; `couplings` are `Σ coupling·y[n]` read from the
  **frozen** snapshot (start-of-tick `y`).
- The state is **bounded**: commit clamps to `[0,1]` (signed states to `[-1,1]`).

**Units (important):** only `a` is time-scaled (through `dt`/`half_life`). `b`, `drift`, `coupling`, and
the per-tick action effects are **per-tick / per-event** magnitudes; the implementation does **not**
multiply them by `dt`. See the units note in `docs/diagrams/update.md`. `time_scale` re-scales the decay
envelope, not these additive terms.

## 2. Transfer function (single input channel)

For one input `u → x`, taking the couplings/drift as separate, the discrete transfer function is

```
            b · z^-1
G_{u→x}(z) = ──────────────
            1 − a · z^-1
```

i.e. the deposit on tick `n` is observed from tick `n+1` onward (the update reads the frozen start-of-tick
state, so an event booked at `n` first appears in `x[n+1]`). The single pole is at `z = a`, **inside the
unit circle** for any finite positive half-life → bounded, stable, exponentially-decaying.

> **Same-tick observation convention.** `potentials.py` reads the *post-commit* state, so an event routed
> through `update` at tick `n` is visible to action selection within tick `n` via `x`'s committed value;
> the *ledger* (moral) path is deliberately one tick later (see `moral_tension_impl_spec.md` §1.1). The
> `z^-1` above is the state-to-state / next-observation convention; both are consistent — pick the one that
> matches the seam you are reasoning about.

## 3. Event = finite impulse · repeated event = step · NOT a Dirac delta

- **One-time event** (`u = [.., 0, U, 0, ..]`, a finite single-tick deposit): `x` jumps by `b·U` on the
  next observation, then decays as `b·U · a^k` — an **exponential tail** with half-life `half_life`. This
  is a *discrete finite impulse-like deposit*, **not** a continuous-time Dirac `D·δ(t)`, and the spike is
  never stored *as* a spike — only its bounded effect on `x`, which immediately starts leaking away.
- **Repeated / sustained event** (`u = U` every tick, a **step** input): `x` accumulates geometrically
  toward a bounded steady state and is then held by the clamp. The unconstrained step steady state is
  `x_inf = b·U / (1 − a)`.
- **Fast rise / slow fall** is therefore modeled by a **high finite event gain `b`** (big bounded jump)
  plus a **long half-life** (slow `a`-decay) — two ordinary parameters, no delta function.

## 4. Steady state & the clamp-reliance warning

For a constant **drift-only** input (no events, no couplings), the unconstrained fixed point is

```
x_inf = drift / (1 − decay)
```

evaluated **before** setpoints, couplings, action effects, and the clamp. If `x_inf` exceeds the
configured range (`> 1` for an unsigned state), the state would **rely on clamp saturation** to stay
bounded — usually a calibration smell (the drift is too strong for the leak, so the state pins at the
ceiling and loses its dynamic range). `eval/state_response_report.py` computes `decay`, `x_inf`, and this
flag for every state deterministically.

## 5. Loops and the anger ⇄ stress feedback

A single state is always stable (pole at `a < 1`). **Loops** are where stability must be checked: the only
core feedback loop is `anger ⇄ stress` (2-cycle, `docs/diagrams/update.md`). The linearized criterion
(Jury, `engine/stability.py`):

```
g(anger→stress) · g(stress→anger) < (1 − decay_stress) · (1 − decay_anger)
```

and the full coupling submatrix must have spectral radius < 1. A **stable but near-1 dominant pole**
produces a long emotional tail (slow return to calm) even though the system is technically bounded —
`anger_stress_loop_report` in `engine/stability.py` reports the Jury margin, the dominant
eigenvalue/pole, an effective tail-time estimate, and warns on knife-edge (very small) margins. The new
moral couplings (`moral_tension_impl_spec.md` §6) feed this same machinery; the two moral loops
(salience↔guilt↔exposure_risk and rumination↔stress↔fatigue) must pass the same check before calibration.

## 6. Why no true Dirac impulse is ever introduced

A real `δ(t)` is an unbounded, zero-width, infinite-height spike — it has no place in a clamped,
discrete-time, deterministic integrator. Events here are **finite values applied on exactly one tick**;
their effect on the state is a bounded jump that then leaks away. Modeling "a sudden shock" never requires
a delta and never requires a new ultra-fast persistent state (which would lower `min(half_life)`, shrink
`dt`, and re-time the whole simulation): use a **high event gain into an existing state**, or a
**transient event channel**, both of which stay finite and bounded.
