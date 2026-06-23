"""M-J.2 repair & rumination (third moral vertical slice).

Builds on M-J.0/.1. Adds `repair_drive` + `rumination` states and the `apologize` action. Asserts the
TOPOLOGY (not magic numbers): on the SAME scenario an EMPATHIC guilt-prone persona APOLOGIZES (makes
amends) while a DETACHED (low-empathy) guilt-prone persona merely CONFESSES; rumination builds from guilt
as a bounded leaky integrator that couples to stress/fatigue (the moral burden replayed). Magnitudes are
calibration placeholders from the opt-in overlay; only the ORDERING/contrast is checked.

The `confide` safe-vs-gossip split (needs a confidant target + gossip_tendency) is deliberately deferred.
"""

from __future__ import annotations

from pathlib import Path

from engine.schema import MORAL_STATES
from engine.simulation import run_scenario
from engine.stability import jury_margin
from engine.yaml_io import load_persona, load_scenario
from eval.moral import moral_overrides
from eval.observe import action_counts, first_tick_with_action, trajectory

ROOT = Path(__file__).resolve().parents[1]
DEFAULTS = ROOT / "calibration" / "defaults.yaml"
HALGRIM = ROOT / "data" / "personas" / "halgrim.yaml"
SCENARIO = ROOT / "data" / "scenarios" / "moral_probe.yaml"

# Guilt-prone + honest (so no lying); empathy is the M-J.2 axis under test.
EMPATHIC = {"guilt_proneness": 0.8, "honesty_humility": 0.9, "empathy": 0.9}
DETACHED = {"guilt_proneness": 0.8, "honesty_humility": 0.9, "empathy": 0.05}


def _run(traits):
    cfg = load_persona(HALGRIM, DEFAULTS, param_overrides=moral_overrides(traits))
    return run_scenario(cfg, load_scenario(SCENARIO), n_ticks=16)[1]


def test_repair_and_rumination_states_are_opt_in():
    legacy = load_persona(HALGRIM, DEFAULTS)
    for s in ("repair_drive", "rumination"):
        assert s in MORAL_STATES
        assert s not in legacy.initial_global_state
    moral = load_persona(HALGRIM, DEFAULTS, param_overrides=moral_overrides(EMPATHIC))
    for s in ("repair_drive", "rumination"):
        assert s in moral.initial_global_state


def test_empathic_apologizes_detached_confesses():
    """The litmus: empathy decides MAKE AMENDS vs merely OWN UP -- same guilt, same scenario."""
    emp = action_counts(_run(EMPATHIC))
    det = action_counts(_run(DETACHED))
    assert ("apologize" in emp) and ("apologize" not in det)
    assert ("confess" in det) and ("confess" not in emp)


def test_apologize_relieves_guilt_and_repair_drive():
    tr = _run(EMPATHIC)
    t = first_tick_with_action(tr, "apologize")
    assert t is not None
    guilt = trajectory(tr, "guilt")
    repair = trajectory(tr, "repair_drive")
    # making amends discharges BOTH the guilt and the urge to repair (post_effects relief)
    assert guilt[t] < guilt[t - 1]
    assert repair[t] < repair[t - 1]


def test_rumination_builds_from_guilt_and_is_bounded():
    rum = trajectory(_run(DETACHED), "rumination")
    assert rum[0] == 0.0
    assert (
        rum[-1] > 0.0
    )  # guilt feeds rumination -> it accumulates ("can't stop replaying it")
    assert all(0.0 <= v <= 1.0 for v in rum)  # bounded leaky integrator, not a runaway


def test_repair_drive_builds_from_guilt():
    # the DETACHED persona never apologizes, so its repair_drive accumulates monotonically from guilt
    rep = trajectory(_run(DETACHED), "repair_drive")
    assert rep[0] == 0.0
    assert rep[-1] > rep[3]
    assert all(0.0 <= v <= 1.0 for v in rep)


def test_moral2_couplings_keep_anger_stress_stable():
    cfg = load_persona(HALGRIM, DEFAULTS, param_overrides=moral_overrides(EMPATHIC))
    # repair_drive/rumination are fed FORWARD from guilt (no return edge into the 2-cycle) -> unchanged
    assert jury_margin(cfg.decay, cfg.couplings) > 0.0
