"""M-J.3 accusation / scapegoat (fourth moral vertical slice; accused+accuser only -- witness fan-out is
the deferred M-MEM).

Adds `perceived_injustice` + `avoidance_drive` states, the `suspicion` relation dim, and the `accusation`
cue. Asserts the TOPOLOGY (not magnitudes): under the SAME accusation a SENSITIVE persona
(injustice_sensitivity high) reads it as UNFAIR -> perceived_injustice builds, couples to anger and to
resentment[accuser], FLIPS the guilt switch (perceived_injustice -> guilt(-): "felt justified"), and the
persona BLAMES the accuser back (blame_other), casting suspicion on them; an AVOIDANT persona
(conflict_avoidance high) instead AVOIDS the confrontation (avoid). One trait cluster differs -> different
visible action and a divergent grievance signature (the litmus). Magnitudes are calibration placeholders.
"""

from __future__ import annotations

from pathlib import Path

from engine.schema import MORAL_RELATION_DIMS, MORAL_STATES, RELATION_DIMS
from engine.simulation import run_scenario
from engine.stability import jury_margin
from engine.yaml_io import load_persona, load_scenario
from eval.moral import moral_overrides
from eval.observe import action_counts, relation_trajectory, trajectory

ROOT = Path(__file__).resolve().parents[1]
DEFAULTS = ROOT / "calibration" / "defaults.yaml"
HALGRIM = ROOT / "data" / "personas" / "halgrim.yaml"
SCENARIO = ROOT / "data" / "scenarios" / "moral_accusation.yaml"

# The grievance switch is the axis: a SENSITIVE accuser-blamer vs an AVOIDANT dodger, same accusation.
SENSITIVE = {
    "injustice_sensitivity": 0.9,
    "conflict_avoidance": 0.1,
    "guilt_proneness": 0.5,
}
AVOIDANT = {
    "injustice_sensitivity": 0.1,
    "conflict_avoidance": 0.9,
    "guilt_proneness": 0.5,
}


def _run(traits, n=14):
    cfg = load_persona(HALGRIM, DEFAULTS, param_overrides=moral_overrides(traits))
    return run_scenario(cfg, load_scenario(SCENARIO), n_ticks=n)[1]


# --- opt-in plumbing -------------------------------------------------------------------


def test_accusation_states_and_suspicion_dim_are_opt_in():
    assert {"perceived_injustice", "avoidance_drive"} <= MORAL_STATES
    assert "suspicion" in RELATION_DIMS and "suspicion" in MORAL_RELATION_DIMS
    legacy = load_persona(HALGRIM, DEFAULTS)
    for s in ("perceived_injustice", "avoidance_drive"):
        assert s not in legacy.initial_global_state
    # a legacy relation row never carries suspicion (byte-identical); a moral persona's decay does.
    assert "suspicion" not in legacy.decay
    moral = load_persona(HALGRIM, DEFAULTS, param_overrides=moral_overrides(SENSITIVE))
    assert "suspicion" in moral.decay


# --- the grievance / avoid-vs-blame litmus ---------------------------------------------


def test_sensitive_blames_avoidant_avoids():
    """The litmus: the response traits decide DEFEND-AND-BLAME vs DODGE, same accusation."""
    sens = action_counts(_run(SENSITIVE))
    avoid = action_counts(_run(AVOIDANT))
    assert ("blame_other" in sens) and ("blame_other" not in avoid)
    assert ("avoid" in avoid) and ("avoid" not in sens)


def test_accusation_builds_perceived_injustice_for_the_sensitive():
    inj_s = trajectory(_run(SENSITIVE), "perceived_injustice")
    inj_a = trajectory(_run(AVOIDANT), "perceived_injustice")
    assert inj_s[0] == 0.0
    assert inj_s[-1] > 0.0  # the unfair accusation accumulates as grievance
    assert all(0.0 <= v <= 1.0 for v in inj_s)  # bounded integrator, not a runaway
    assert inj_s[-1] > inj_a[-1]  # the sensitive persona feels it far more


def test_grievance_switch_suppresses_guilt():
    """perceived_injustice -> guilt(-): the more unfair it feels, the less guilt it leaves ('I was
    justified'). Same guilt seed, so the sensitive (high-injustice) run ends with LESS guilt."""
    guilt_s = trajectory(_run(SENSITIVE), "guilt")
    guilt_a = trajectory(_run(AVOIDANT), "guilt")
    assert guilt_s[-1] < guilt_a[-1]


def test_blame_casts_suspicion_and_resentment_on_the_accuser():
    tr = _run(SENSITIVE)
    susp = relation_trajectory(tr, "accuser", "suspicion")
    resent = relation_trajectory(tr, "accuser", "resentment")
    # blaming back casts suspicion on the accuser; the accusation itself breeds resentment toward them
    assert susp[-1] > 0.0
    assert resent[-1] > 0.0


def test_avoidant_builds_avoidance_drive():
    av = trajectory(_run(AVOIDANT), "avoidance_drive")
    assert av[0] == 0.0
    assert av[-1] > 0.0
    assert all(0.0 <= v <= 1.0 for v in av)


# --- stability -------------------------------------------------------------------------


def test_accusation_slice_keeps_anger_stress_stable():
    cfg = load_persona(HALGRIM, DEFAULTS, param_overrides=moral_overrides(SENSITIVE))
    # perceived_injustice/avoidance_drive are fed FORWARD (no return edge into the anger<->stress 2-cycle)
    assert jury_margin(cfg.decay, cfg.couplings) > 0.0
