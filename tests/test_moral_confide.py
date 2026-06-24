"""M-J.2 deferred completions: the `confide` safe-vs-gossip split + relational `reparation`.

Closes the two pieces M-J.2 shipped as topology-only (see commit b4270a7 / impl spec build order):

1. CONFIDE SAFE-VS-GOSSIP SPLIT. On the SAME `moral_confide` scenario (a wrong replayed as rumination,
   then a TRUSTED confidant present) a DISCREET persona (gossip_tendency=0) CONFIDES -- rumination is
   relieved (the burden shared safely) -- while a GOSSIP-PRONE persona (gossip_tendency=0.9) CANNOT confide
   safely: the (1-gossip_tendency) gate collapses the confide drive, so rumination keeps weighing AND the
   gossip-modulated probe->exposure gain leaves it MORE exposed (a blabber has spread it). One trait differs
   -> safe relief vs leaked exposure (the litmus). Magnitudes are calibration placeholders; only the
   ORDERING/contrast is asserted.

2. REPARATION. `apologize` now books a RELATIONAL amends on the wronged target (trust up, resentment down),
   not just self-relief -- the moral loop closes through the relationship, not only inside the persona.

The split is gated on `trust[confidant]`, so it stays inert in the legacy `moral_probe` runs (interrogator
trust 0) -> the existing M-J.0/.1/.2 litmus tests are untouched.
"""

from __future__ import annotations

from pathlib import Path

from engine.schema import MORAL_POTENTIALS, MORAL_TRAITS
from engine.simulation import run_scenario
from engine.stability import jury_margin
from engine.yaml_io import load_persona, load_scenario
from eval.moral import moral_overrides
from eval.observe import (
    action_counts,
    first_tick_with_action,
    relation_trajectory,
    trajectory,
)

ROOT = Path(__file__).resolve().parents[1]
DEFAULTS = ROOT / "calibration" / "defaults.yaml"
HALGRIM = ROOT / "data" / "personas" / "halgrim.yaml"
CONFIDE = ROOT / "data" / "scenarios" / "moral_confide.yaml"
PROBE = ROOT / "data" / "scenarios" / "moral_probe.yaml"

# Guilt-prone + honest (no lying); gossip_tendency is the M-J.2 axis under test.
DISCREET = {"guilt_proneness": 0.8, "honesty_humility": 0.9, "gossip_tendency": 0.0}
GOSSIP = {"guilt_proneness": 0.8, "honesty_humility": 0.9, "gossip_tendency": 0.9}
# An empathic confessor for the reparation litmus (apologizes, per the M-J.2 repair slice).
EMPATHIC = {"guilt_proneness": 0.8, "honesty_humility": 0.9, "empathy": 0.9}


def _run(scenario, traits, n=18):
    cfg = load_persona(HALGRIM, DEFAULTS, param_overrides=moral_overrides(traits))
    return run_scenario(cfg, load_scenario(scenario), n_ticks=n)[1]


# --- opt-in plumbing -------------------------------------------------------------------


def test_confide_action_and_gossip_trait_are_opt_in():
    assert "confide" in MORAL_POTENTIALS
    assert "gossip_tendency" in MORAL_TRAITS
    legacy = load_persona(HALGRIM, DEFAULTS)
    assert "confide" not in legacy.potential_weights
    # gossip_tendency defaults to 0.0 for a persona that omits it (golden-safe).
    assert legacy.traits.get("gossip_tendency", 0.0) == 0.0


# --- the confide safe-vs-gossip litmus -------------------------------------------------


def test_discreet_confides_and_relieves_rumination():
    tr = _run(CONFIDE, DISCREET)
    assert "confide" in action_counts(tr)
    t = first_tick_with_action(tr, "confide")
    rum = trajectory(tr, "rumination")
    # safe unburdening discharges the replayed conflict (post_effects relief)
    assert rum[t] < rum[t - 1]


def test_gossip_prone_cannot_confide_safely_and_stays_more_exposed():
    disc = _run(CONFIDE, DISCREET)
    goss = _run(CONFIDE, GOSSIP)
    # the (1-gossip_tendency) gate collapses the safe-confide drive -> no confide for the blabber
    assert "confide" not in action_counts(goss)
    rum_d = trajectory(disc, "rumination")
    rum_g = trajectory(goss, "rumination")
    exa_d = trajectory(disc, "exposure_anxiety")
    exa_g = trajectory(goss, "exposure_anxiety")
    # the unshared burden keeps weighing, and the gossip-modulated probe gain leaves it more exposed
    assert rum_g[-1] > rum_d[-1]
    assert exa_g[-1] > exa_d[-1]


def test_confide_is_inert_without_a_trusted_confidant():
    """Gated on trust[confidant]: in moral_probe (only the interrogator, trust 0) confide never fires,
    so the existing guilt/repair litmus on that scenario is undisturbed."""
    assert "confide" not in action_counts(_run(PROBE, DISCREET))


# --- reparation ------------------------------------------------------------------------


def test_apologize_makes_relational_reparation():
    tr = _run(PROBE, EMPATHIC)
    t = first_tick_with_action(tr, "apologize")
    assert t is not None
    trust = relation_trajectory(tr, "interrogator", "trust")
    resent = relation_trajectory(tr, "interrogator", "resentment")
    # making amends repairs the RELATIONSHIP (not just the persona's own guilt): trust up, resentment down
    assert trust[t] > trust[t - 1]
    assert resent[t] <= resent[t - 1]


# --- stability -------------------------------------------------------------------------


def test_confide_slice_keeps_anger_stress_stable():
    cfg = load_persona(HALGRIM, DEFAULTS, param_overrides=moral_overrides(DISCREET))
    assert jury_margin(cfg.decay, cfg.couplings) > 0.0
