"""Calibration loop (calibration.py, M4 step 3) -- the IMPURE optimizer half.

We can't assert bit-exact optimizer output (CMA-ES RNG), so we test PROPERTIES: Morris screening
is deterministic given a seed and separates sensitive from inert params; the objective is a pure
adapter of loss.total; CMA-ES genuinely DESCENDS from a perturbed start; acceptance rejects a
degraded behavioral contrast; and run_layer1 emits provenance metadata without touching defaults.

(Baseline layer-1 loss is already 0 -- the seed benchmark is thin, §16 -- so the loop is validated
by descent from a PERTURBED point, not from baseline.)
"""

from types import SimpleNamespace

import pytest

# Calibration tooling needs the optional [calibration] extras (CMA-ES + SALib); skip cleanly
# without them, mirroring tests/test_diagnostics.py's matplotlib guard. These tests are @slow too.
pytest.importorskip("cma")
pytest.importorskip("SALib")

from engine.calibration import (  # noqa: E402
    DEFAULTS,
    _bounds,
    accept,
    freeze_inert,
    objective_total,
    optimize,
    run_layer1,
    screen_morris,
)
from engine.loss import loss
from engine.yaml_io import load_persona


@pytest.mark.slow
def test_morris_screen_is_deterministic_and_discriminating():
    a = screen_morris(n_trajectories=4, seed=1)
    b = screen_morris(n_trajectories=4, seed=1)
    assert a == b  # seeded -> reproducible
    keys, *_ = _bounds()
    assert set(a) == set(keys)  # every free param scored
    assert max(a.values()) > 0.0  # the loss is not flat over the box


def test_freeze_inert_splits_active_from_frozen():
    sens = {"a": 1.0, "b": 0.5, "c": 0.0, "d": 0.01}
    active, frozen = freeze_inert(sens, rel_threshold=0.05)
    assert "a" in active and "b" in active
    assert "c" in frozen and "d" in frozen  # below 5% of the max -> frozen


def test_objective_is_pure_adapter_of_loss():
    cfg = load_persona("data/personas/halgrim.yaml", "calibration/defaults.yaml")
    assert objective_total(cfg.half_lives) == loss(None).total


@pytest.mark.slow
def test_cma_descends_from_perturbed_start():
    # boredom=60 breaks the idle-boredom rise (curve) and the ordering chain -> loss > 0.
    opt = optimize(
        ["boredom", "stress"], x0_half_lives={"boredom": 60}, seed=1, maxiter=15
    )
    assert opt.start_total > 0.0
    assert opt.best_total < opt.start_total  # the optimizer actually reduced the loss
    # and respects the box bounds
    keys, lo, hi, _ = _bounds()
    for k in ("boredom", "stress"):
        assert lo[k] - 1e-9 <= opt.best_half_lives[k] <= hi[k] + 1e-9


def test_accept_rejects_degraded_behavior():
    base = SimpleNamespace(total=0.0, components={"behavior": 0.0, "ranking": 0.0})
    # loss not increased but a behavioral contrast got much worse -> reject (note A)
    degraded = SimpleNamespace(total=0.0, components={"behavior": 0.3, "ranking": 0.0})
    ok, reasons = accept(base, degraded)
    assert not ok and reasons["behavior_not_degraded"] is False
    # loss down, monitors flat -> accept
    good = SimpleNamespace(total=0.0, components={"behavior": 0.0, "ranking": 0.0})
    assert accept(base, good)[0] is True


def test_loss_layer2_decoupling_monitor_fires():
    """Gutting the anger<->stress loop to the floor (the 5-param 'hollow contrast' point) wins margin but
    makes anger inert -> the decoupling monitor (peak_anger floor) fires. This is the safety net that
    blocked the write before the half-lives were co-freed."""
    from engine.loss import loss_layer2

    gutted = {
        "couplings.anger.stress": 0.0159,
        "couplings.stress.anger": 0.0124,
        "couplings.anger.frustration": 0.0585,
        "gains.anger.insult": 0.397,
        "gains.frustration.insult": 0.394,
        "half_lives.anger": 30.0,
        "half_lives.stress": 70.0,
    }
    assert loss_layer2(gutted).components["decoupling"] > 0.0


@pytest.mark.slow
def test_run_layer2_runs_and_reports_gate(tmp_path):
    """run_layer2 reports the renegotiation-gate flags and only writes on success (no best-of-bad)."""
    from engine.calibration import run_layer2

    out = tmp_path / "calibrated_layer2.yaml"
    r = run_layer2(seeds=(1,), maxiter=6, out_path=out)
    assert {
        "contrast_repaired",
        "cooldown_met",
        "margin_ok",
        "decoupling_ok",
        "tension_irreducible",
        "success",
    } <= set(r["flags"])
    assert out.exists() == r["written"] == r["flags"]["success"]


@pytest.mark.slow
def test_run_layer1_emits_metadata_and_leaves_defaults_untouched(tmp_path):
    before = DEFAULTS.read_bytes()
    out = tmp_path / "calibrated_layer1.yaml"
    rep = run_layer1(seed=2, n_trajectories=3, maxiter=2, out_path=out)

    assert out.exists()
    for key in (
        "seed",
        "active",
        "frozen",
        "morris_mu_star",
        "baseline",
        "best",
        "input_config",
        "calibrated_half_lives",
        "accepted",
        "acceptance_reasons",
    ):
        assert key in rep
    assert rep["seed"] == 2
    assert "defaults_sha256" in rep["input_config"]  # provenance, not bare numbers
    assert DEFAULTS.read_bytes() == before  # never overwrites defaults.yaml
