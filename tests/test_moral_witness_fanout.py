"""M-J.3.3 -- witness fan-out + false-accusation discovery (the M-MEM-unblocked moral slice).

The remaining M-J.3 work needed simultaneous multi-source delivery on one tick (review R7), now provided by
M-MEM. Two pieces:

1. PUBLIC ACCUSATION FAN-OUT (accused side). A public accusation lands as ONE tick carrying the accuser's
   `accusation` AND each witness's `suspicion_raised` -- so the accused grows wary of EVERY witness at once
   (suspicion[witness_i] all rise on the same tick) while perceived_injustice builds. No new engine code:
   the cues exist (M-J.3.1/.2); M-MEM delivers them together.

2. FALSE-ACCUSATION DISCOVERY (accuser side). When a false accusation is exposed, the accuser receives a
   `false_accusation_discovered` self-cue (guilt, scaled by guilt_proneness -- remorse for the wrong) plus
   the crowd turning (`suspicion_raised` from each witness, fanned out on one tick). A guilt-prone accuser
   feels the remorse; a callous one barely does.

Magnitudes are calibration placeholders; only ORDERING/fan-out invariants are asserted.
"""

from __future__ import annotations

from pathlib import Path

from engine.simulation import run_scenario
from engine.stability import jury_margin
from engine.yaml_io import load_persona, load_scenario
from eval.moral import moral_overrides
from eval.observe import relation_trajectory, trajectory

ROOT = Path(__file__).resolve().parents[1]
DEFAULTS = ROOT / "calibration" / "defaults.yaml"
HALGRIM = ROOT / "data" / "personas" / "halgrim.yaml"
PUBLIC = ROOT / "data" / "scenarios" / "moral_public_accusation.yaml"
DISCOVERY = ROOT / "data" / "scenarios" / "moral_false_accusation_discovered.yaml"

SENSITIVE = {
    "injustice_sensitivity": 0.9,
    "conflict_avoidance": 0.2,
    "guilt_proneness": 0.4,
}
GUILT_PRONE = {"guilt_proneness": 0.9, "honesty_humility": 0.6}
CALLOUS = {"guilt_proneness": 0.05, "honesty_humility": 0.6}


def _run(scenario, traits, n=12):
    cfg = load_persona(HALGRIM, DEFAULTS, param_overrides=moral_overrides(traits))
    return run_scenario(cfg, load_scenario(scenario), n_ticks=n)[1]


# --- piece 1: public accusation fan-out to the accused ---------------------------------


def test_public_accusation_fans_suspicion_to_every_witness_at_once():
    """The M-MEM unblock: accuser + N witnesses on ONE tick -> the accused grows wary of EACH witness
    simultaneously (neither suspicion_raised event is dropped) and the public charge reads as unfair."""
    tr = _run(PUBLIC, SENSITIVE)
    susp_w1 = relation_trajectory(tr, "witness_1", "suspicion")
    susp_w2 = relation_trajectory(tr, "witness_2", "suspicion")
    inj = trajectory(tr, "perceived_injustice")
    # both witnesses' suspicion lands on the very FIRST public tick -> they arrived together (fan-out)
    assert susp_w1[0] > 0.0 and susp_w2[0] > 0.0
    assert susp_w1[-1] > 0.0 and susp_w2[-1] > 0.0
    assert inj[-1] > 0.0  # the public accusation is felt as unjust
    # resentment toward the accuser too (the accusation cue), distinct from the witnesses
    assert relation_trajectory(tr, "accuser", "resentment")[-1] > 0.0


def test_public_accusation_witnesses_are_bounded():
    tr = _run(PUBLIC, SENSITIVE)
    for w in ("witness_1", "witness_2"):
        assert all(0.0 <= v <= 1.0 for v in relation_trajectory(tr, w, "suspicion"))


# --- piece 2: false-accusation discovery on the accuser --------------------------------


def test_discovery_breeds_guilt_scaled_by_guilt_proneness():
    """A guilt-prone accuser feels REMORSE when the false accusation is exposed; a callous one barely does
    (guilt deposit scaled by guilt_proneness) -- same scenario, one trait differs."""
    guilt_prone = trajectory(_run(DISCOVERY, GUILT_PRONE), "guilt")
    callous = trajectory(_run(DISCOVERY, CALLOUS), "guilt")
    assert guilt_prone[-1] > callous[-1]
    assert guilt_prone[-1] > 0.0
    assert all(0.0 <= v <= 1.0 for v in guilt_prone)


def test_discovery_crowd_turning_fans_suspicion_onto_the_accuser():
    """The crowd turns: each witness's suspicion lands on the accuser on the discovery tick (fan-out)."""
    tr = _run(DISCOVERY, GUILT_PRONE)
    susp_w1 = relation_trajectory(tr, "witness_1", "suspicion")
    susp_w2 = relation_trajectory(tr, "witness_2", "suspicion")
    assert susp_w1[0] > 0.0 and susp_w2[0] > 0.0  # both witnesses, same first tick
    assert (
        trajectory(tr, "exposure_anxiety")[-1] > 0.0
    )  # being exposed as a false accuser


def test_fanout_slice_keeps_anger_stress_stable():
    cfg = load_persona(HALGRIM, DEFAULTS, param_overrides=moral_overrides(SENSITIVE))
    assert jury_margin(cfg.decay, cfg.couplings) > 0.0
