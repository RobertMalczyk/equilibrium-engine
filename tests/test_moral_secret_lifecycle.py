"""M-J.4.3 -- Secret lifecycle (salience mini-integrator + known_by/hidden_from transitions + inactivation).

A scenario-authored Secret is seeded into the ledger. A `secret_cued` reminder raises its `salience`
(decaying between cues); while the secret is ACTIVE (hidden_from non-empty OR unresolved) that salience
WEIGHS as stress. `secret_exposed` fills `known_by` with the witnesses and EMPTIES `hidden_from` -> the
secret becomes INACTIVE: salience is no longer raised (gated) and it stops weighing (spec 3.4). Magnitudes
are calibration placeholders; only the lifecycle/ordering is asserted.
"""

from __future__ import annotations

from pathlib import Path

from engine.simulation import run_scenario
from engine.yaml_io import load_persona, load_scenario
from eval.moral import moral_overrides
from eval.observe import trajectory

ROOT = Path(__file__).resolve().parents[1]
DEFAULTS = ROOT / "calibration" / "defaults.yaml"
HALGRIM = ROOT / "data" / "personas" / "halgrim.yaml"
SECRET = ROOT / "data" / "scenarios" / "moral_secret.yaml"
EXPOSED = ROOT / "data" / "scenarios" / "moral_secret_exposed.yaml"

MORAL = {"guilt_proneness": 0.5}


def _run(scenario, n):
    cfg = load_persona(HALGRIM, DEFAULTS, param_overrides=moral_overrides(MORAL))
    return run_scenario(cfg, load_scenario(scenario), n_ticks=n)


def test_authored_secret_seeds_into_the_ledger():
    rt, _ = _run(SECRET, 6)
    s = rt.moral_ledger.secrets.get("s_theft")
    assert s is not None
    assert s.topic == "theft" and s.category == "crime"
    assert s.hidden_from == ["guard"] and s.stakes == 0.8


def test_active_secret_salience_builds_and_weighs_as_stress():
    rt, tr = _run(SECRET, 6)
    s = rt.moral_ledger.secrets["s_theft"]
    assert s.salience > 0.0  # reminders built salience
    stress = trajectory(tr, "stress")
    assert stress[-1] > stress[0]  # the hidden secret weighs on the persona


def test_exposure_fills_known_by_empties_hidden_from_and_inactivates():
    rt, tr = _run(EXPOSED, 10)
    s = rt.moral_ledger.secrets["s_theft"]
    # public exposure: the witnesses now KNOW, and the owner is no longer actively hiding it
    assert set(s.known_by) == {"guard", "warden", "cook"}
    assert s.hidden_from == []
    # inactive (hidden_from empty, unresolvedness low) -> post-exposure cues no longer drive salience up:
    sal_at_exposure = trajectory_secret_salience(tr, "s_theft", 5)
    sal_end = trajectory_secret_salience(tr, "s_theft", 9)
    assert (
        sal_end < sal_at_exposure
    )  # salience only decays now (gated), never re-raised


def test_inactive_secret_stops_weighing_stress_after_exposure():
    _, tr = _run(EXPOSED, 12)
    stress = trajectory(tr, "stress")
    # while hidden (t0-4) stress climbs; once exposed/inactive (t5+) the secret no longer adds its weight,
    # so the late-run stress rise per tick is smaller than the pre-exposure rise (it stops being driven up).
    pre = stress[4] - stress[1]  # rise while actively hidden
    post = stress[11] - stress[8]  # rise after exposure (no secret weight)
    assert post < pre


def test_secret_is_inert_without_the_moral_overlay():
    """The secret is SEEDED from the scenario (not the overlay), but its lifecycle is overlay-driven: a
    legacy persona (no ledger_params) carries the secret INERT -- salience never rises, it never weighs.
    (Golden scenarios author no `secrets:`, so their ledger stays empty -> byte-identical.)"""
    legacy = load_persona(HALGRIM, DEFAULTS)
    rt, _ = run_scenario(legacy, load_scenario(SECRET), n_ticks=6)
    # no overlay -> no salience build (cue_gain absent) -> the secret never activates / weighs
    assert rt.moral_ledger.secrets["s_theft"].salience == 0.0
    assert (
        "secret_salience_to_stress" not in legacy.ledger_params
    )  # no weight channel at all


def trajectory_secret_salience(tr, secret_id, tick):
    """Salience isn't a global state; read it off the per-tick end-of-tick ledger in the trace."""
    led = tr.ticks[tick].state_after_post.moral_ledger
    return led.secrets[secret_id].salience
