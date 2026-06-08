"""stability -- linearized coupling-loop pole analysis (spec sections 1, 8).

OFFLINE analysis only (the stability TEST and the calibration LOSS); NOT imported by the tick
loop. numpy is permitted HERE for the same reason as in the tests -- it never touches
simulation/update, so the bit-for-bit determinism of the runtime is unaffected.

Single source of truth for the stability criterion: the test and the loss MUST compute the
identical value, so the math lives here once (no two drifting copies that could disagree).
"""

from __future__ import annotations

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
