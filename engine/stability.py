"""stability -- linearized coupling-loop pole analysis (spec sections 1, 8).

OFFLINE analysis only (the stability TEST and the calibration LOSS); NOT imported by the tick
loop. numpy is permitted HERE for the same reason as in the tests -- it never touches
simulation/update, so the bit-for-bit determinism of the runtime is unaffected.

Single source of truth for the stability criterion: the test and the loss MUST compute the
identical value, so the math lives here once (no two drifting copies that could disagree).
"""

from __future__ import annotations

import math

import numpy as np

# States that participate in the coupling subgraph (spec section 8).
LOOP_STATES: tuple[str, ...] = (
    "hunger",
    "fatigue",
    "boredom",
    "stress",
    "frustration",
    "anger",
)


def linearized_matrix(decay: dict[str, float], couplings: dict[str, dict[str, float]]):
    """Per-tick Jacobian of the coupling subgraph: diagonal = decay, off-diagonal = couplings."""
    idx = {s: i for i, s in enumerate(LOOP_STATES)}
    n = len(LOOP_STATES)
    m = np.zeros((n, n))
    for i, s in enumerate(LOOP_STATES):
        m[i, i] = decay[s]
    for s, edges in couplings.items():
        if s not in idx:
            continue
        for y, g in edges.items():
            if y in idx:
                m[idx[s], idx[y]] += g
    return m


def spectral_radius(
    decay: dict[str, float], couplings: dict[str, dict[str, float]]
) -> float:
    """Max |eigenvalue| of the linearized loop. Stable iff < 1 (poles inside the unit circle)."""
    m = linearized_matrix(decay, couplings)
    return float(max(abs(ev) for ev in np.linalg.eigvals(m)))


def jury_margin(
    decay: dict[str, float], couplings: dict[str, dict[str, float]]
) -> float:
    """Binding 2-cycle (anger<->stress) criterion, spec section 8: returns
    ``(1-decay_stress)*(1-decay_anger) - g(anger->stress)*g(stress->anger)``.
    Positive = stable margin; <= 0 = violated."""
    g_as = couplings["stress"]["anger"]  # anger -> stress
    g_sa = couplings["anger"]["stress"]  # stress -> anger
    bound = (1.0 - decay["stress"]) * (1.0 - decay["anger"])
    return bound - g_as * g_sa


# --- State-response interpretation (control_interpretation.md) ----------------------
# Deterministic, OFFLINE read of a single state as a bounded first-order leaky integrator
# ``x[n+1] = decay*x[n] + gain*event[n] + drift`` (decay = 2**(-dt/half_life)). No engine
# state is touched; these are pure functions over config numbers, used by tests and the
# eval/state_response_report.py markdown generator. NOT a Dirac delta: ``event`` is a finite
# single-tick deposit, ``gain`` its per-event magnitude.


def decay_from(half_life: float, dt: float) -> float:
    """The engine's per-tick retention, ``decay = 2**(-dt/half_life)`` (single source: yaml_io)."""
    return 2.0 ** (-dt / half_life)


def impulse_response(decay: float, gain: float = 1.0, n: int = 8) -> list[float]:
    """Samples of x to a unit finite event at tick 0 (deposit observed from the next tick):
    ``[gain, gain*decay, gain*decay**2, ...]`` -- the bounded exponential tail, NOT a Dirac spike."""
    return [gain * decay**k for k in range(n)]


def steady_state_drift(decay: float, drift: float) -> float:
    """Unconstrained drift-only fixed point ``x_inf = drift/(1-decay)`` (before couplings/clamp)."""
    if decay >= 1.0:
        return math.inf if drift > 0 else (-math.inf if drift < 0 else 0.0)
    return drift / (1.0 - decay)


def exceeds_clamp(x_inf: float, lo: float = 0.0, hi: float = 1.0) -> bool:
    """True iff the unconstrained drift steady state would fall outside the clamp range
    (i.e. the state relies on clamp saturation to stay bounded)."""
    return x_inf < lo or x_inf > hi


def state_response(
    name: str,
    half_life: float,
    dt: float,
    drift: float = 0.0,
    gain: float = 1.0,
    n: int = 8,
    lo: float = 0.0,
    hi: float = 1.0,
) -> dict:
    """One state's response record: decay, unit-impulse samples, drift steady state, clamp-reliance flag."""
    decay = decay_from(half_life, dt)
    x_inf = steady_state_drift(decay, drift)
    saturates = exceeds_clamp(x_inf, lo, hi)
    return {
        "state": name,
        "half_life": half_life,
        "dt": dt,
        "decay": decay,
        "drift": drift,
        "impulse_response": impulse_response(decay, gain, n),
        "x_inf_drift": x_inf,
        "relies_on_clamp": saturates,
        "warning": (
            f"drift steady state x_inf={x_inf:.3f} exceeds clamp [{lo},{hi}] -- "
            "relies on clamp saturation"
            if saturates
            else ""
        ),
    }


def state_response_report(config, n: int = 8) -> list[dict]:
    """A state_response record for every global state of a loaded PersonaConfig. Deterministic;
    reads only config numbers (decay/half_life/dt/drift). Event input is a finite unit deposit."""
    from engine.schema import GLOBAL_STATES

    out = []
    for s in GLOBAL_STATES:
        out.append(
            state_response(
                name=s,
                half_life=config.half_lives[s],
                dt=config.dt,
                drift=config.drifts.get(s, 0.0),
                gain=1.0,
                n=n,
            )
        )
    return out


def anger_stress_loop_report(
    decay: dict[str, float],
    couplings: dict[str, dict[str, float]],
    dt: float | None = None,
    knife_edge_ratio: float = 0.1,
) -> dict:
    """Stability report for the anger<->stress feedback loop (the engine's one core 2-cycle).

    Reports the Jury margin, the dominant pole/eigenvalue of the local 2x2 subsystem, an effective
    decay-horizon (tail half-time) estimate, and a knife-edge warning when the margin is a small
    fraction of its stability bound. A stable-but-near-1 dominant pole means a LONG emotional tail
    even though the loop is bounded."""
    g_as = couplings["stress"]["anger"]  # anger -> stress
    g_sa = couplings["anger"]["stress"]  # stress -> anger
    bound = (1.0 - decay["stress"]) * (1.0 - decay["anger"])
    margin = bound - g_as * g_sa

    # 2x2 local Jacobian [[decay_stress, g(anger->stress)], [g(stress->anger), decay_anger]].
    m = np.array([[decay["stress"], g_as], [g_sa, decay["anger"]]], dtype=float)
    eigs = np.linalg.eigvals(m)
    dominant = max(eigs, key=abs)
    rho = float(abs(dominant))

    # Effective tail: ticks for the dominant mode to halve (rho**k = 1/2). Only meaningful when stable.
    if 0.0 < rho < 1.0:
        tail_ticks = math.log(0.5) / math.log(rho)
    else:
        tail_ticks = math.inf
    tail_seconds = (
        tail_ticks * dt if (dt is not None and math.isfinite(tail_ticks)) else None
    )

    stable = rho < 1.0 and margin > 0.0
    knife_edge = stable and bound > 0.0 and (margin / bound) < knife_edge_ratio

    warnings = []
    if not stable:
        warnings.append("UNSTABLE: dominant pole >= 1 or Jury margin <= 0")
    if knife_edge:
        warnings.append(
            f"knife-edge stability: Jury margin {margin:.4g} is only "
            f"{margin / bound:.1%} of its bound -- small gain changes could destabilize"
        )
    if stable and rho > 0.97:
        warnings.append(
            f"near-unit dominant pole rho={rho:.4f}: stable but expect a LONG emotional tail"
        )

    return {
        "loop": "anger<->stress",
        "jury_margin": margin,
        "jury_bound": bound,
        "margin_ratio": (margin / bound) if bound > 0.0 else float("nan"),
        "dominant_eigenvalue": complex(dominant),
        "dominant_pole": rho,
        "tail_half_time_ticks": tail_ticks,
        "tail_half_time_seconds": tail_seconds,
        "stable": stable,
        "knife_edge": knife_edge,
        "warnings": warnings,
    }
