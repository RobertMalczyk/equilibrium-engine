# Plan — dt-invariant (continuous-time) parameterization

> Status: **S0–S4 IMPLEMENTED.** S0 spec §2.1 + S1 `resolution_factor` on `main` (PR #3). S2 (action
> per-tick rates) + S3 (count windows `÷Ts`) + S4 (free-dynamics convergence smoke test) on branch
> `dt-invariant-s2-s4` (PR open). Default path byte-identical throughout (golden green). Remaining
> beyond this plan: a fuller fine-`dt` validation (boundedness gate + G0 incident-count spot-check at a
> production fine `dt`) and any calibration re-fit if a fine `dt` becomes a shipped operating point.
> Goal: make `dt` (= sample time `Ts`) a pure **resolution** knob — every time-dependent constant is
> specified in **real-time units** and the per-tick coefficient is derived from `Ts` at load, so the
> continuous-time trajectory is preserved when `dt` changes (not just relabeled, as `time_scale` does).

## 1. Motivation

Today two things are true:
- **`time_scale`** scales every half-life by the same `k`, so `dt/τ` is constant → the discrete system
  is *relabeled* in time (bit-identical per tick-index, only seconds-per-tick change). It cannot
  *refine* resolution.
- **Half-lives → decay** is already exact and dt-aware (`decay = 2^(−Ts/τ)`). But several additive
  per-tick terms are stored as **per-tick magnitudes**, so holding `τ` (seconds) fixed and changing
  `dt` changes their accumulated effect → the "tick-anchored residual."

We want: hold all real-time constants fixed, change `dt`, and recover the **same continuous-time
behaviour** at finer/coarser resolution. That makes finer `dt` a legitimate, principled operating
point (smoother traces, more event-timing fidelity) instead of a different model.

## 2. The rule (per dynamical kind — NOT uniform ÷Ts)

Dividing every constant by `Ts` is wrong: decays are exponential in `Ts`, and one-shot events must not
scale. Each parameter is classified by its role and converted accordingly:

| kind | examples | real-time spec | per-tick coefficient |
|---|---|---|---|
| **leak / decay** | state half-lives → `decay`, relational memory | time constant τ (s) | `2^(−Ts/τ)` — exact, already done |
| **continuous rate** | `drifts`, `couplings`, `burst_extinction`, `idle_recovery`, per-tick action effects, sustained physiological inputs | rate **per second** | **× Ts** (Euler) |
| **event impulse** | `insult` / `help` / `command` / `food_given` deposits | deposit magnitude | **unchanged** (fires once; dt-independent) |
| **counter / window** | `seeking_timeout_ticks`, `burst_confirm_ticks`, refractory, action `cooldown`, `reactive_window` | duration (s) | `round(· / Ts)` |
| **dimensionless** | thresholds, clamps, `k_esc`, trait modulators, gains-on-states | — | **unchanged** |

Summary: **τ-type → exponential, rate-type → ×Ts, count-type → ÷Ts, impulse/threshold → invariant.**

## 3. Current-state audit (where each lives, what changes)

From `engine/update.py` the per-state update is:
```
new = decay·old + (1−decay)·setpoint        # leak  — OK (exact)
      + drift                                # RATE  — needs ×Ts (store per-second)
      + Σ gain·mod·input.value               # impulse for events / rate for sustained inputs
      + Σ coupling·(1+k_esc·y)·y             # RATE  — needs ×Ts
      + extinction·(0−x)                     # RATE  — needs ×Ts
      + active_effect / idle_recovery        # RATE  — needs ×Ts
```
Reclassification:
- **OK as-is (invariant):** `decay` (from half-lives), thresholds, clamps, `k_esc`, trait mods.
- **Becomes rate ×Ts:** `drifts`, `couplings`, `burst_extinction`, `idle_recovery`, action `per_tick`
  effects (`active_effect`), and any **sustained** physiological channel input (hunger/fatigue feed).
- **Stays impulse (invariant):** event-channel deposits (`insult`, `help`, `command`, `food_given`).
  → **Open design point:** channels must be tagged *impulse* vs *sustained*. Most forcing events are
    impulses; physiological feeds are sustained. Needs an explicit per-channel kind in config.
- **Becomes count ÷Ts:** `seeking_timeout_ticks`, `burst_confirm_ticks`, refractory windows, and any
  action `cooldown` / `reactive_window` currently expressed in ticks.

Where the conversion already half-exists: the **eval timescale path** (`eval/calibrated.py
timescale_overrides`) derives `drifts`, sleep discharge, and `seeking_timeout` from durations + `dt`.
That logic should be **subsumed** by the generic loader conversion so there is one mechanism, not two.

## 4. Design — centralize all Ts-conversion in the loader

- **`engine/update.py` stays unchanged**: it keeps consuming ready per-tick coefficients.
- **`engine/yaml_io.py` does every conversion** at load, given `Ts`, exactly as it already turns
  half-lives into `decay`. Config files carry **real-time** values + a declared **kind** per field
  (or kind is implied by a fixed table for known fields). One source of truth for discretization.
- `Ts` is derived as today: `Ts = min(half_life) / nyquist_factor` (× `time_scale` if used). `dt` and
  `time_scale` remain orthogonal: `time_scale` relabels, the new conversion *refines*.

### Byte-identical canonical guarantee
Re-express each current per-tick constant as a rate: `rate_per_second = value_per_tick / Ts_canonical`
(and counts as `seconds = ticks · Ts_canonical`). At the canonical `Ts` the loader then reproduces the
exact original per-tick numbers → **the golden trace is unchanged by construction.** Only *new* `dt`
values exercise the new path.

## 5. Honest caveats (must land in the spec)

1. **Leaks are exact; rate terms are Euler (O(Ts)).** dt-invariant in the limit; finite-`dt` error
   shrinks as `dt` decreases. (Optionally upgrade specific leak-to-target rates to exact later.)
2. **Nonlinear / threshold / latch logic is path-dependent.** `k_esc`, clamps, and the burst latch
   (integrate-and-fire, confirm-for-N-ticks, hysteresis) converge with finer `dt` but are **not
   bit-identical across `dt`**. Counts must be specced in seconds; the latch crossing still depends on
   the discrete path. So: smooth dynamics preserved by construction; discrete-event timing converges.
3. **Calibration sits on the canonical `dt`.** Finer `dt` is a *new operating point* → re-verify the
   boundedness / G0 corridor there before trusting incident counts.

## 6. Staged work (each stage independently reviewable; spec-first)

- **S0 — Spec.** Add §2 discretization subsection + the §3 table to `docs/` (and touch the affected
  subsystem diagrams). Declare every time-dependent field's unit + kind. **No code.** ← review gate.
- **S1 — Loader conversion, canonical-identical.** Implement per-kind conversion in `yaml_io`;
  re-express current constants as rates/durations so canonical `Ts` is byte-identical. Subsume the
  eval `timescale_overrides` derivation. Golden trace must match to the bit.
- **S2 — Channel kind (impulse vs sustained).** Tag channels; route impulse deposits (invariant) vs
  sustained inputs (×Ts). Verify against the canonical trace.
- **S3 — Counts in seconds.** Move `cooldown`/`timeout`/`confirm`/`refractory`/`reactive_window` to
  real-time, derive ticks via `round(/Ts)`.
- **S4 — Fine-dt validation.** Pick a finer `dt` (e.g. `time_scale` such that `dt≈15s`); show the
  smooth-state trajectories converge to the canonical ones (within Euler error), run the boundedness
  gate + a G0 spot-check at the new operating point; document residual latch-timing differences.

## 7. Definition of Done

- Spec + diagrams updated **before** the matching code (no drift).
- Canonical `dt` run is **byte-identical** to pre-change golden; full suite green; `ruff` clean.
- A documented, reproducible finer-`dt` run whose smooth states converge to canonical and whose
  boundedness gate passes.
- One conversion mechanism (loader); `update.py` equation unchanged; no per-tick numeric literals
  reintroduced.

## 8. Blast radius

- Default/canonical path: untouched by construction (golden, G2 parity, G0 corridor intact).
- New `dt` operating points: not golden-frozen → require the S4 spot-check.
- Performance: finer `dt` ⇒ proportionally more ticks (dt 120→15 ⇒ ~8× ticks/runtime/trace size).
- Public surface: `yaml_io` config schema gains real-time fields + kinds; `eval/calibrated.py`
  timescale path is simplified to feed the loader. Both are owner-side engine changes (this repo).
