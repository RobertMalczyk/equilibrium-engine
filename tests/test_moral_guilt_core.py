"""M-J.0 guilt-core slice (the first moral vertical slice).

Asserts the TOPOLOGY (not magic numbers, per CLAUDE.md): the moral layer is opt-in and inert by default
(byte-identical), guilt is a finite-deposit / slow-decay leaky integrator (not a Dirac spike), and the
litmus persona-contrast holds -- a guilt-prone persona confesses, a low-guilt one stays silent on the SAME
scenario. Magnitudes come from the opt-in overlay (calibration placeholders); only the ORDERING is checked.
"""

from __future__ import annotations

from pathlib import Path

from engine.schema import MORAL_POTENTIALS, MORAL_STATES
from engine.simulation import run_scenario
from engine.stability import jury_margin
from engine.yaml_io import load_persona, load_scenario
from eval.moral import moral_overrides
from eval.observe import action_counts, first_tick_with_action, trajectory

ROOT = Path(__file__).resolve().parents[1]
DEFAULTS = ROOT / "calibration" / "defaults.yaml"
HALGRIM = ROOT / "data" / "personas" / "halgrim.yaml"
SCENARIO = ROOT / "data" / "scenarios" / "moral_probe.yaml"


def _moral_cfg(guilt_proneness: float):
    return load_persona(
        HALGRIM,
        DEFAULTS,
        param_overrides=moral_overrides({"guilt_proneness": guilt_proneness}),
    )


def _legacy_cfg():
    return load_persona(HALGRIM, DEFAULTS)


# --- opt-in / inertness (Gate A) ----------------------------------------------------


def test_moral_layer_is_opt_in_absent_by_default():
    """Without the overlay a persona carries NONE of the moral states/actions (so legacy traces stay
    byte-identical -- the golden suite proves the bytes; here we assert the absence directly)."""
    cfg = _legacy_cfg()
    for s in MORAL_STATES:
        assert s not in cfg.initial_global_state
        assert s not in cfg.half_lives
    _, tr = run_scenario(cfg, load_scenario(SCENARIO), n_ticks=4)
    # the moral cues (wrongdoing/probe) decompose to nothing without overlay gains -> no moral state appears
    for tk in tr.ticks:
        for s in MORAL_STATES:
            assert s not in tk.state_after_post.global_state
        for a in MORAL_POTENTIALS:
            assert a not in tk.potentials


def test_moral_overlay_enables_states_and_actions():
    cfg = _moral_cfg(0.8)
    for s in MORAL_STATES:
        assert s in cfg.initial_global_state
        assert s in cfg.half_lives
    # moral half-lives are long -> dt (set by the fastest state) is unchanged
    assert cfg.half_lives["guilt"] >= 1800.0
    assert cfg.half_lives["exposure_anxiety"] >= 1800.0


# --- guilt as a finite-deposit, slow-decay integrator (NOT a Dirac) -----------------


def test_guilt_is_finite_deposit_and_slow_decay():
    cfg = _moral_cfg(0.8)
    _, tr = run_scenario(cfg, load_scenario(SCENARIO), n_ticks=16)
    g = trajectory(tr, "guilt")
    # rises by a BOUNDED amount on the wrongdoing ticks (finite deposit, never an unbounded spike)
    assert 0.0 < g[0] <= 1.0
    assert g[2] > g[0]  # accumulates across the three wrongdoing reminders
    assert all(0.0 <= v <= 1.0 for v in g)  # bounded everywhere (clamped, not a delta)
    # slow decay: long half-life => between events guilt barely moves per tick (stays within a hair)
    tail = g[4:]  # after the confess discharge, no more wrongdoing -> only slow leak
    assert all(abs(b - a) < 0.02 for a, b in zip(tail, tail[1:]))


def test_exposure_anxiety_rises_from_probe():
    cfg = _moral_cfg(0.2)
    _, tr = run_scenario(cfg, load_scenario(SCENARIO), n_ticks=16)
    e = trajectory(tr, "exposure_anxiety")
    assert e[2] == 0.0  # no probe yet (t0-2 are wrongdoing)
    assert e[-1] > e[3]  # builds once probing starts
    assert all(0.0 <= v <= 1.0 for v in e)


# --- the litmus: persona-contrast from guilt_proneness alone ------------------------


def test_guilt_prone_confesses_low_guilt_stays_silent():
    sc = load_scenario(SCENARIO)
    _, hi = run_scenario(_moral_cfg(0.8), sc, n_ticks=16)
    _, lo = run_scenario(_moral_cfg(0.2), sc, n_ticks=16)

    hi_confess = first_tick_with_action(hi, "confess")
    lo_confess = first_tick_with_action(lo, "confess")

    # guilt-prone OWNS UP; low-guilt does not -> "confesses earlier" (finite tick < never)
    assert hi_confess is not None, "guilt-prone persona should confess"
    assert lo_confess is None, "low-guilt persona should not confess on this scenario"
    # the low-guilt persona instead keeps concealing (exposure-driven)
    assert "remain_silent" in action_counts(lo)
    # SAME scenario, one trait differs -> different visible action (the litmus)
    assert set(action_counts(hi)) != set(action_counts(lo)) or hi_confess != lo_confess


def test_confess_relieves_guilt():
    cfg = _moral_cfg(0.8)
    _, tr = run_scenario(cfg, load_scenario(SCENARIO), n_ticks=16)
    t_confess = first_tick_with_action(tr, "confess")
    assert t_confess is not None
    g = trajectory(tr, "guilt")
    # owning up discharges guilt (post_effects relief): guilt is lower right after the confession
    assert g[t_confess] < g[t_confess - 1]


# --- stability: the moral couplings don't destabilize the core anger<->stress loop --


def test_moral_couplings_keep_anger_stress_stable():
    cfg = _moral_cfg(0.8)
    # guilt/exposure_anxiety feed stress/anger feed-FORWARD (no return edge) -> the 2-cycle is unchanged
    assert jury_margin(cfg.decay, cfg.couplings) > 0.0
