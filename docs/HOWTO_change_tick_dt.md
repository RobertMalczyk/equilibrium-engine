# HOW-TO: change the engine tick (`dt`) safely

Audience: an engineer/agent modifying the tick rate. **Read this before touching anything time-related.**
Authoritative source: spec §2 + §2.1 (`docs/rpg_persona_dynamics_spec_v1.md`). Conversion lives in
`engine/yaml_io.py`; `engine/update.py` is unchanged by tick changes.

## TL;DR

`dt` (seconds per tick) is **derived, never set by hand**:

```
dt = min(half_life) × time_scale ÷ (nyquist_factor × resolution_factor)
decay = 2 ** (−dt / half_life)        # recomputed at load
```

Change the tick **only** through the two `tick:` config knobs below. Do **not** edit `dt`,
`nyquist_factor`, individual half-lives, or per-tick numbers to retime anything.

## The two knobs (different meanings — pick the right one)

| knob | default | what it does | trace effect |
|------|---------|--------------|--------------|
| **`time_scale`** (k) | `1.0` | scales **every** half-life by k → `dt` scales by k | **bit-identical per tick-index**; only seconds-per-tick stretch (a pure clock *relabel*) |
| **`resolution_factor`** (R) | `1.0` | shrinks `dt` by R with half-lives **held fixed**; the loader auto-scales rate-type coeffs (`×1/R`) and count windows (`×R`) | **refines** sampling — same real-time trajectory, smoother (convergent, not bit-identical) |

- Use **`time_scale`** to stretch/compress the *world clock* (e.g. fast seed emotions → a believable
  day: anger half-life 30 s × 80 ≈ 40 min). Behaviour is identical, just slower/faster wall-clock.
- Use **`resolution_factor`** to get *more ticks per real second* (finer integration, smoother traces,
  better event-timing fidelity) **without** changing the real-time dynamics.
- They are orthogonal and compose.

## How to set them

```python
# per run (no file edit) — the calibration override seam:
from engine.yaml_io import load_persona
cfg = load_persona("data/personas/halgrim.yaml", "calibration/defaults.yaml",
                   param_overrides={"tick": {"resolution_factor": 8}})   # 8× finer dt
# or {"time_scale": 40}, or both.
```

Or edit the `tick:` block in `calibration/defaults.yaml`. A scenario may also carry `tick.time_scale`.

## Pick a target dt

```
time_scale_or_R such that:  dt_target = min(half_life) × time_scale ÷ (nyquist_factor × R)
```
With the base config (`min half_life = 30 s`, `nyquist_factor = 10`, so base `dt = 3 s`):
to **refine** to `dt = 0.375 s` set `resolution_factor = 8`; to **stretch** to `dt = 120 s` set
`time_scale = 40`. To both stretch to a believable day *and* refine, set `time_scale = 40` and
`resolution_factor = 8` → `dt = 15 s`.

## ✅ Safe vs ⛔ never

✅ **Safe:** any `time_scale > 0`, any `resolution_factor > 0`. All `Ts`-conversion is centralized in
the loader and classified by kind (leak → exact `2^(−Ts/τ)`; rate → `×Ts`; count → `÷Ts`;
event-impulse/threshold/`k_esc` → invariant). `update.py` is untouched.

⛔ **Never, for retiming:**
- **Don't edit `dt` directly** — it's derived and baked into `decay`; a raw edit desyncs decay from the
  inputs.
- **Don't change `nyquist_factor`** to change pace — it sets numerical *resolution*, so the trace stops
  being identical, and below ~10 the loop can go unstable (it violates `dt = min(half_life)/nyquist`).
- **Don't hand-scale half-lives or per-tick numbers** (`drifts`, `couplings`, `*_ticks`, `cooldown`,
  action `per_tick`) for pacing — the loader already converts these; doing it by hand double-scales and
  breaks the per-second rate.

## Caveats you must respect

1. **Leaks are exact; rate terms are forward Euler (`O(Ts)`).** `resolution_factor` is real-time-faithful
   *in the limit* — error shrinks as `dt` shrinks, it is not zero at coarse `dt`.
2. **Nonlinear / threshold / latch logic is path-dependent.** `k_esc` escalation, clamps, and the burst
   latch (integrate-and-fire, confirm-for-N-ticks, hysteresis) **converge** across `dt` but are **not
   bit-identical**. Don't expect identical burst *timing* at different `dt`.
3. **Calibration sits at the canonical `dt`.** A finer/stretched `dt` you intend to *ship* is a **new
   operating point** — re-verify the boundedness gate + a G0 incident-count spot-check there before
   trusting any incident/outburst counts.

## Verify after ANY tick-related change

```bash
ruff check . && ruff format --check .
pytest -q                                  # full suite green
pytest tests/test_tick_golden.py           # golden BYTE-IDENTICAL at default → canonical unchanged
pytest tests/test_resolution_factor.py     # the knob's no-op + scaling contract
```
- The golden test passing proves the **default path is unchanged** (the knobs default to identity and
  the scaling block is guarded by `if resolution_factor != 1.0:`).
- For a finer `dt` you actually plan to use, additionally run a **free-dynamics convergence check**
  (see `test_realtime_convergence_free_dynamics`) and the eval boundedness gate at that `dt`.

## Where it lives

- Spec: `docs/rpg_persona_dynamics_spec_v1.md` §2 + §2.1.
- Conversion: `engine/yaml_io.py` (the guarded `resolution_factor` / `time_scale` block).
- Diagram: `docs/diagrams/update.md` (per-term discretization note).
- Tests: `tests/test_resolution_factor.py`, `tests/test_time_scale.py`, `tests/test_tick_golden.py`.

## Process

`main` is branch-protected: **open a PR, let CI pass, a maintainer merges. Never self-merge.** If your
change adds a new shipped `dt`, note the boundedness/G0 re-verification in the PR.
