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
    assert fine.coupling_escalation == base.coupling_escalation
    # LEVEL thresholds unchanged; COUNT thresholds ('*_ticks') scale with R (S3).
    for k, v in base.thresholds.items():
        if str(k).endswith("_ticks"):
            assert fine.thresholds[k] == max(1, round(v * 2.0))
        else:
            assert fine.thresholds[k] == v


def test_refine_scales_action_per_tick_and_cooldowns():
    """S2: action per-tick effects are rates (×1/R). S3: per-action cooldown is a count (×R)."""
    base = _cfg()
    fine = _cfg(2.0)
    for action, ap in base.action_params.items():
        fap = fine.action_params[action]
        for s, v in dict(ap.get("per_tick", {})).items():
            assert abs(float(fap["per_tick"][s]) - float(v) / 2.0) < 1e-12
        if "cooldown" in ap:
            assert fap["cooldown"] == max(1, round(float(ap["cooldown"]) * 2.0))


def test_realtime_convergence_free_dynamics():
    """S4 (smoke): with the half-lives held fixed, a finer dt traces the SAME real-time trajectory.
    Free relaxation (no events, so no impulse-timing confound) over one fixed game-time horizon: the
    final smooth states at R=4 match R=1 within Euler tolerance, and stay bounded."""
    from engine.schema import Scenario
    from engine.simulation import run_scenario

    init = {
        "global_state": {"anger": 0.6, "stress": 0.5, "fatigue": 0.4, "hunger": 0.3}
    }

    def final_state(R, n_ticks):
        cfg = _cfg(R)
        sc = Scenario(id="relax", persona="wojslaw", initial_overrides=init, events=())
        _, tr = run_scenario(cfg, sc, n_ticks=n_ticks)
        return tr.ticks[-1].state_after_post.global_state, cfg.dt

    g1, dt1 = final_state(1.0, 60)  # 60 ticks of game-time
    g4, dt4 = final_state(4.0, 240)  # same game-time at 4× resolution
    assert abs(dt1 - 4.0 * dt4) < 1e-9  # same horizon in seconds
    for s in ("anger", "stress", "fatigue", "hunger"):
        assert 0.0 <= g1[s] <= 1.0 and 0.0 <= g4[s] <= 1.0
        assert (
            abs(g1[s] - g4[s]) < 2e-2
        )  # converges (leak exact; rate terms Euler O(Ts))


def test_invalid_resolution_factor_rejected():
    import pytest

    with pytest.raises(ValueError):
        _cfg(0.0)
