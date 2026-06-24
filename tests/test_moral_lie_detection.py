"""M-J.4.2 -- lie detection (`lie_detected` -> `betrayal`).

Two halves (spec section 5.6):
1. TARGET SIDE (betrayal). Discovering you were lied to damages the relationship with the liar: anger rises,
   resentment[liar] builds, and trust[liar] COLLAPSES.
2. LIAR SIDE (detected_risk). When a liar's own lie is caught, the matching LieRecord's `detected_risk`
   mini-integrator jumps -- the ledger now reflects that the lie is at risk of exposure.

Magnitudes are calibration placeholders; only ORDERING/lifecycle invariants are asserted.
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
BETRAYAL = ROOT / "data" / "scenarios" / "moral_betrayal.yaml"
CAUGHT = ROOT / "data" / "scenarios" / "moral_lie_caught.yaml"

ANY_MORAL = {"guilt_proneness": 0.5}
LIAR = {"guilt_proneness": 0.0, "honesty_humility": 0.0}


def _run(scenario, traits, n):
    cfg = load_persona(HALGRIM, DEFAULTS, param_overrides=moral_overrides(traits))
    return run_scenario(cfg, load_scenario(scenario), n_ticks=n)


# --- target side: betrayal damages the relationship -----------------------------------


def test_betrayal_collapses_trust_and_builds_resentment():
    _, tr = _run(BETRAYAL, ANY_MORAL, n=6)
    trust = relation_trajectory(tr, "betrayer", "trust")
    resent = relation_trajectory(tr, "betrayer", "resentment")
    anger = trajectory(tr, "anger")
    assert trust[-1] < trust[0]  # the trust the persona had is destroyed
    assert resent[-1] > resent[0]  # ...replaced by a grudge
    assert anger[-1] > anger[0]  # discovering the lie stings


def test_betrayal_relations_stay_bounded():
    _, tr = _run(BETRAYAL, ANY_MORAL, n=6)
    for dim in ("trust", "resentment"):
        assert all(0.0 <= v <= 1.0 for v in relation_trajectory(tr, "betrayer", dim))


# --- liar side: detection raises the record's detected_risk ----------------------------


def test_caught_lie_raises_detected_risk_on_the_record():
    rt, _ = _run(CAUGHT, LIAR, n=14)
    rec = rt.moral_ledger.lies.get("lie:interrogator")
    assert rec is not None  # the liar built a record while lying under probing
    assert rec.detected_risk > 0.0  # ...and being caught raised its exposure risk
    assert 0.0 <= rec.detected_risk <= 1.0


def test_detection_without_a_matching_record_is_a_noop_for_the_ledger():
    """A betrayed TARGET (no LieRecord of their own) gets the relational damage but books no detected_risk
    -- detection only touches a record that actually exists."""
    rt, _ = _run(BETRAYAL, ANY_MORAL, n=6)
    assert (
        rt.moral_ledger.is_empty()
    )  # the betrayed persona never lied, so no ledger entry


def test_legacy_persona_ignores_lie_detected():
    rt, tr = run_scenario(
        load_persona(HALGRIM, DEFAULTS), load_scenario(BETRAYAL), n_ticks=6
    )
    # legacy persona has no betrayal gains -> trust toward the (seeded) betrayer is untouched, ledger empty
    assert rt.moral_ledger.is_empty()


def test_detection_slice_keeps_anger_stress_stable():
    cfg = load_persona(HALGRIM, DEFAULTS, param_overrides=moral_overrides(ANY_MORAL))
    assert jury_margin(cfg.decay, cfg.couplings) > 0.0
