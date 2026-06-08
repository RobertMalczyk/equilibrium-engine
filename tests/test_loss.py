"""Layer-1 calibration loss (loss.py) -- the loss must REACT to the right things (pole, shape,
range, ordering) and stay pure. No optimizer here (step 3). These check the objective is sound
BEFORE anything descends it.
"""

from engine.loss import LAYER1_WEIGHTS, loss, simulate
from engine.yaml_io import load_persona


def test_baseline_stable_in_range_with_timing_fuel():
    """The guards (stability/curve/regularization) are satisfied at the placeholders, but the
    timing ANCHOR is NOT yet met (anger cools too slowly) -- so the loss has real fuel to descend
    (it is no longer the degenerate 0 it was before the benchmark was enriched)."""
    b = loss()
    assert b.components["stability"] == 0.0
    assert b.components["regularization"] == 0.0
    assert b.components["curve"] == 0.0
    assert b.detail["stability"]["spectral_radius"] < 1.0
    assert b.components["timing"] > 0.0  # the anchor gives fuel
    assert b.total > 0.0


def test_anchor_gives_descendable_signal():
    """Moving SATISFACTION's half-life so its glow half-decays nearer the 45s anchor lowers the
    timing penalty -- the loss responds to the time constant the half-life actually steers (anger's
    half-life has ~no leverage; satisfaction's does -- the whole reason for the re-anchor)."""
    base_timing = loss(None).components["timing"]
    nearer = loss({"half_lives": {"satisfaction": 44}}).components["timing"]
    assert nearer < base_timing


def test_frozen_base_excludes_placeholders():
    """The Layer-2 base is ONLY the calibrated half-life (satisfaction); placeholders are excluded so a
    noise value never enters the Jury gate as if measured."""
    from engine.loss import frozen_base

    base = frozen_base()["half_lives"]
    assert base == {
        "satisfaction": 43.17
    }  # only the calibrated one (deterministic seed=1)
    assert "frustration" not in base and "anger" not in base


def test_layer2_stability_is_a_hard_reject():
    """Layer 2 tunes the only feedback loop, so a candidate can make it unstable: scaling the
    anger<->stress couplings up pushes the Jury 2-cycle out -> rejected (inf) BEFORE any run."""
    from engine.loss import loss_layer2

    bad = {
        "couplings.anger.stress": 0.12,
        "couplings.stress.anger": 0.10,
        "couplings.anger.frustration": 0.05,
        "gains.anger.insult": 0.35,
        "gains.frustration.insult": 0.20,
    }
    r = loss_layer2(bad)
    assert r.total == float("inf") and r.detail["rejected"] is True


def test_c1_reachability_holds_at_baseline():
    """C1 is phrased on WHETHER half-decay is reached, not on resentment's (unreachable) time:
    within the horizon anger's contribution halves, resentment's does NOT."""
    preds = {
        p["explanation"].split("[")[0]: p
        for p in loss(None).detail["predicates"]
        if p["component"] == "timing" and "reached" in p["explanation"]
    }
    assert all(p["satisfied"] for p in preds.values())


def test_stability_reacts_to_pole():
    # Pushing the anger/stress decays toward 1 breaks the Jury margin / unit circle.
    b = loss({"half_lives": {"anger": 10000, "stress": 10000}})
    assert b.components["stability"] > 0.0


def test_regularization_reacts_to_range_only():
    # resentment is out of its [80000,300000] band but NOT in the coupling loop -> stability clean.
    b = loss({"half_lives": {"resentment": 500000}})
    assert b.components["regularization"] > 0.0
    assert b.components["stability"] == 0.0
    assert b.components["curve"] == 0.0


def test_regularization_reacts_to_ordering():
    # trust below boredom violates the [boredom, trust] non-decreasing chain (memory must be slow).
    b = loss({"half_lives": {"trust": 100}})
    assert b.components["regularization"] > 0.0
    assert any(k.startswith("order:") for k in b.detail["regularization"])
    assert b.components["stability"] == 0.0


def test_curve_reacts_to_time_constant():
    # A short boredom half-life drops its idle equilibrium below the start -> boredom no longer
    # rises monotonically on idle_watch. Pure time-constant effect; the anger/stress loop is untouched.
    b = loss({"half_lives": {"boredom": 31}})
    assert b.components["curve"] > 0.0
    assert b.components["stability"] == 0.0


def test_behavior_ranking_computed_but_weight_zero():
    """Note 2: behavior/ranking are COMPUTED and LOGGED from the start (diagnostics) but carry
    weight 0 in layer 1 -- so they never enter the total here, yet a worsening contrast is visible."""
    assert LAYER1_WEIGHTS["behavior"] == 0.0 and LAYER1_WEIGHTS["ranking"] == 0.0
    b = loss()
    logged = {p["component"] for p in b.detail["predicates"]}
    assert "behavior" in logged and "ranking" in logged  # computed + logged
    assert (
        b.weighted["behavior"] == 0.0 and b.weighted["ranking"] == 0.0
    )  # not penalized


def test_loss_is_pure_deterministic():
    a, b = loss(), loss()
    assert a.total == b.total
    assert a.components == b.components


def test_simulate_is_param_pure_and_horizon_derives_nticks():
    # horizon is game-time; n_ticks = round(horizon/dt). Baseline dt = 3.0 -> 180s = 60 ticks.
    cfg, trace = simulate(None, "welf", "idle_watch", 180.0)
    assert len(trace.ticks) == round(180.0 / cfg.dt)
    # param injection re-derives dt from overridden half_lives (the simulate seam).
    base = load_persona("data/personas/welf.yaml", "calibration/defaults.yaml")
    over = load_persona(
        "data/personas/welf.yaml",
        "calibration/defaults.yaml",
        param_overrides={"half_lives": {"anger": 5}},
    )
    assert over.dt < base.dt  # faster fastest-state -> smaller dt
