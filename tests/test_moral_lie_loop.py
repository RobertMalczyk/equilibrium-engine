"""M-J.1 lie loop (second moral vertical slice).

Builds on M-J.0. Adds `cognitive_load_from_lies` + actions `lie`/`deflect`. Asserts the TOPOLOGY (not
magic numbers): on the SAME probing scenario a habitual liar (low honesty_humility, low guilt_proneness)
LIES while a guilt-prone honest persona CONFESSES; lying deposits a finite, bounded cognitive load that
couples to stress/fatigue (the self-tightening noose) and SELF-LIMITS (no runaway). Magnitudes are
calibration placeholders from the opt-in overlay; only the ORDERING/contrast is checked.

LieRecord ledger + cross-agent lie DETECTION are deliberately deferred (documented in the impl spec) --
this slice is the liar's internal cognitive-load loop only.
"""

from __future__ import annotations

from pathlib import Path

from engine.schema import MORAL_STATES
from engine.simulation import run_scenario
from engine.yaml_io import load_persona, load_scenario
from eval.moral import moral_overrides
from eval.observe import action_counts, first_tick_with_action, trajectory

ROOT = Path(__file__).resolve().parents[1]
DEFAULTS = ROOT / "calibration" / "defaults.yaml"
HALGRIM = ROOT / "data" / "personas" / "halgrim.yaml"
SCENARIO = ROOT / "data" / "scenarios" / "moral_probe.yaml"

LIAR = {"guilt_proneness": 0.2, "honesty_humility": 0.1}
HONEST = {"guilt_proneness": 0.8, "honesty_humility": 0.9}


def _run(traits):
    cfg = load_persona(HALGRIM, DEFAULTS, param_overrides=moral_overrides(traits))
    return run_scenario(cfg, load_scenario(SCENARIO), n_ticks=16)[1]


def test_cognitive_load_state_is_opt_in():
    legacy = load_persona(HALGRIM, DEFAULTS)
    assert "cognitive_load_from_lies" in MORAL_STATES
    assert "cognitive_load_from_lies" not in legacy.initial_global_state
    moral = load_persona(HALGRIM, DEFAULTS, param_overrides=moral_overrides(LIAR))
    assert "cognitive_load_from_lies" in moral.initial_global_state


def test_habitual_liar_lies_not_confesses():
    tr = _run(LIAR)
    assert first_tick_with_action(tr, "lie") is not None, (
        "a habitual liar should lie under probing"
    )
    assert first_tick_with_action(tr, "confess") is None, (
        "a habitual liar should not confess"
    )


def test_guilty_honest_confesses_not_lies():
    tr = _run(HONEST)
    assert first_tick_with_action(tr, "confess") is not None
    assert first_tick_with_action(tr, "lie") is None, (
        "a scrupulous, guilt-prone persona should not lie"
    )


def test_lie_vs_confess_is_a_contrast():
    """Same scenario, traits differ -> different visible moral action (the litmus)."""
    liar, honest = action_counts(_run(LIAR)), action_counts(_run(HONEST))
    assert ("lie" in liar) and ("lie" not in honest)
    assert ("confess" in honest) and ("confess" not in liar)


def test_lying_deposits_bounded_cognitive_load_coupled_to_stress():
    tr = _run(LIAR)
    load = trajectory(tr, "cognitive_load_from_lies")
    stress = trajectory(tr, "stress")
    t_lie = first_tick_with_action(tr, "lie")
    assert t_lie is not None
    # the lie deposits a FINITE load (bounded, not a Dirac spike); zero before the first lie
    assert load[t_lie - 1] == 0.0
    assert load[t_lie] > load[t_lie - 1]
    assert all(
        0.0 <= v <= 1.0 for v in load
    )  # bounded everywhere (self-limiting noose, no runaway)
    # the load couples into stress: a liar's stress keeps climbing across the interrogation
    assert stress[-1] > stress[0]
    assert all(0.0 <= v <= 1.0 for v in stress)


def test_honest_persona_carries_no_lie_load():
    load = trajectory(_run(HONEST), "cognitive_load_from_lies")
    assert all(v == 0.0 for v in load)  # never lies -> never accrues lie-burden
