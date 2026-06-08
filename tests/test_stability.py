"""Regime / stability test (spec sections 1, 8): linearized coupling loop poles inside the
unit circle. The math lives in engine/stability.py (single source of truth shared with the
calibration loss); this test just asserts the criterion on the shipped config.
"""

from engine.stability import jury_margin, spectral_radius
from engine.yaml_io import load_persona


def test_coupling_poles_inside_unit_circle():
    cfg = load_persona("data/personas/halgrim.yaml", "calibration/defaults.yaml")
    radius = spectral_radius(cfg.decay, cfg.couplings)
    assert radius < 1.0, f"spectral radius {radius} >= 1 (unstable coupling loop)"


def test_jury_criterion_anger_stress():
    """The binding 2-cycle criterion stated in spec section 8."""
    cfg = load_persona("data/personas/halgrim.yaml", "calibration/defaults.yaml")
    assert jury_margin(cfg.decay, cfg.couplings) > 0.0
