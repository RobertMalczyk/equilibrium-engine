"""Clamp helpers (Mpom).

The ONLY place state values are bounded. ``clamp01`` for unsigned states/potentials,
``clamp_signed`` for signed values (affinity, affective_bias). The bounds here are the
*definitional* type ranges from spec section 3 ([0,1] and [-1,1]), not tunable engine
parameters -- they carry no calibration meaning.
"""

UNSIGNED_LOW = 0.0
UNSIGNED_HIGH = 1.0
SIGNED_LOW = -1.0
SIGNED_HIGH = 1.0


def clamp01(x: float) -> float:
    """Clamp ``x`` into the unsigned state range [0, 1]."""
    if x < UNSIGNED_LOW:
        return UNSIGNED_LOW
    if x > UNSIGNED_HIGH:
        return UNSIGNED_HIGH
    return x


def clamp_signed(x: float) -> float:
    """Clamp ``x`` into the signed range [-1, 1]."""
    if x < SIGNED_LOW:
        return SIGNED_LOW
    if x > SIGNED_HIGH:
        return SIGNED_HIGH
    return x
