"""Believable-timescale (eval/story path) -- merge-safety locks.

The project thesis is that personas play DIFFERENTLY in visible actions. These pin that the believable
timescale (the one knob + derived duration/ceiling anchors) PRESERVES those contrasts -- identical to
time_scale=1 -- and that the derivation reproduces the believable day and a sane multi-day run. Behaviour
assertions are CONTRASTS (Rule 1), not magnitudes.
"""

import dataclasses
from pathlib import Path

import yaml

import eval.timescale_keeper as keeper
from engine.simulation import run_scenario
from engine.yaml_io import load_scenario
from eval.calibrated import load_eval_persona, load_eval_persona_timescale

ROOT = Path(__file__).resolve().parents[1]
REACTIVE = {"outburst", "cold_response", "complain", "refuse", "cooperate"}


def _first_reaction(cfg, sc):
    _, tr = run_scenario(cfg, sc, n_ticks=40)
    for tk in tr.ticks:
        if tk.t <= 6 and tk.selection.action in REACTIVE:
            return tk.selection.action
    return "neutral"


def _across(scenario_id, personas, loader):
    base = load_scenario(ROOT / "data" / "scenarios" / f"{scenario_id}.yaml")
    return {
        p: _first_reaction(loader(p), dataclasses.replace(base, persona=p))
        for p in personas
    }


def test_burst_suppress_shrug_contrast_is_preserved():
    """Same elevated state + same galling soup -> Wojslaw BURSTS, Halgrim goes COLD, Lutek SHRUGS: three
    distinct visible actions, on the believable timescale."""
    r = _across(
        "same_soup_bad_day",
        ["wojslaw", "halgrim", "lutek"],
        load_eval_persona_timescale,
    )
    assert r["wojslaw"] == "outburst"
    assert r["halgrim"] == "cold_response"
    assert r["lutek"] == "neutral"
    assert len(set(r.values())) == 3  # three DIFFERENT actions from the same input


def test_contrast_identical_to_default_timescale():
    """The contrast pattern is the SAME at time_scale=1 and the believable timescale -- the time-constant
    changes moved the clock, not the behaviour."""
    personas = ["wojslaw", "halgrim", "lutek", "branic", "cichy"]
    assert _across("same_soup_bad_day", personas, load_eval_persona) == _across(
        "same_soup_bad_day", personas, load_eval_persona_timescale
    )


def test_obedience_contrast_is_preserved():
    """Same Halgrim, same order: cooperate from respected Edda, refuse from resented Wojslaw."""
    h = load_eval_persona_timescale("halgrim")
    assert (
        _first_reaction(
            h, load_scenario(ROOT / "data" / "scenarios" / "command_from_edda.yaml")
        )
        == "cooperate"
    )
    assert (
        _first_reaction(
            h, load_scenario(ROOT / "data" / "scenarios" / "command_from_wojslaw.yaml")
        )
        == "refuse"
    )


def test_believable_durations_within_ground_truth():
    """The derived timescale reproduces the believable day: the keeper's phenomena land within the
    human-set ground-truth tolerance (so the one knob + duration anchors hold)."""
    gt = yaml.safe_load(
        (ROOT / "calibration" / "timescale_ground_truth.yaml").read_text(
            encoding="utf-8"
        )
    )
    cfg = load_eval_persona_timescale(gt["reference_persona"])
    for name in (
        "anger_halflife",
        "frustration_halflife",
        "hunger_to_half",
        "boredom_to_seek",
        "grudge_halflife",
        "seeking_giveup",
    ):
        spec = gt["phenomena"][name]
        actual = keeper.measure(cfg, name, spec)
        lo, hi = (
            spec["target_s"] * (1 - spec["tol"]),
            spec["target_s"] * (1 + spec["tol"]),
        )
        assert lo <= actual <= hi, (
            f"{name}: {actual:.0f}s not within {spec['tol']:.0%} of {spec['target_s']}s"
        )


def test_believable_multiday_is_sane_smoke():
    """A believable multi-day run stays bounded, sleeps and recovers (the sanity gate, smoke-tested on one
    scenario so the suite stays fast)."""
    from eval.sanity_multiday import evaluate, run_multiday

    path = ROOT / "eval" / "scenarios" / "multiday" / "branic" / "branic_multi_001.yaml"
    n_days = len(yaml.safe_load(path.read_text(encoding="utf-8"))["day_plan"])
    res = evaluate(
        run_multiday(
            load_eval_persona_timescale("branic"), load_scenario(path), n_days
        ),
        n_days,
    )
    for check in (
        "clamped",
        "hunger_sane",
        "sleeps",
        "night_reset",
        "not_saturated",
        "recovers",
        "not_stuck",
    ):
        assert res[check], f"sanity check failed: {check}"
