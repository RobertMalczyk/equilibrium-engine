"""`tick.resolution_factor` (default 1.0) -- the dt-REFINEMENT knob (spec section 2.1).

Locks the two guarantees: (1) at the default it is an exact no-op (canonical config byte-identical);
(2) refining by R shrinks dt by R with half-lives held FIXED, and scales every continuous-RATE
coefficient by 1/R so the per-second rate is preserved, while leaks (half_lives/decay), event gains,
and dimensionless thresholds are untouched.
"""

from pathlib import Path

from engine.yaml_io import load_persona

ROOT = Path(__file__).resolve().parents[1]
DEFAULTS = ROOT / "calibration" / "defaults.yaml"


def _cfg(resolution_factor=None):
    ov = (
        {"tick": {"resolution_factor": resolution_factor}}
        if resolution_factor is not None
        else None
    )
    return load_persona(
        ROOT / "data" / "personas" / "wojslaw.yaml", DEFAULTS, param_overrides=ov
    )


def test_default_is_exact_noop():
    base = _cfg()
    explicit = _cfg(1.0)
    assert explicit.dt == base.dt
    assert explicit.drifts == base.drifts
    assert explicit.couplings == base.couplings
    assert explicit.burst_extinction == base.burst_extinction
    assert explicit.idle_recovery == base.idle_recovery
    assert explicit.decay == base.decay


def test_refine_shrinks_dt_and_scales_rates():
    base = _cfg()
    fine = _cfg(2.0)

    # dt halves; half-lives (hence the leak time constants) are unchanged.
    assert abs(fine.dt - base.dt / 2.0) < 1e-12
    assert fine.half_lives == base.half_lives

    # continuous-rate coefficients halve (per-second rate preserved).
    for k, v in base.drifts.items():
        assert abs(fine.drifts[k] - v / 2.0) < 1e-12
    for s, edges in base.couplings.items():
        for o, g in edges.items():
            assert abs(fine.couplings[s][o] - g / 2.0) < 1e-12
    for s, v in base.burst_extinction.items():
        assert abs(fine.burst_extinction[s] - v / 2.0) < 1e-12
    for s, v in base.idle_recovery.items():
        assert abs(fine.idle_recovery[s] - v / 2.0) < 1e-12

    # impulses / dimensionless are NOT scaled.
    assert fine.gains == base.gains
    assert fine.thresholds == base.thresholds
    assert fine.coupling_escalation == base.coupling_escalation


def test_invalid_resolution_factor_rejected():
    import pytest

    with pytest.raises(ValueError):
        _cfg(0.0)
