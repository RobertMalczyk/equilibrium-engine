"""metrics.compute on existing traces, plus the group-A/D litmus contrasts expressed as DSL
predicates (the executable form of the ad-hoc asserts in test_tick_golden / test_proactive_path).

Deterministic, no optimizer: this is step 1 of the M4 harness (metrics + DSL), verified against
runs we already trust.
"""

from pathlib import Path

from engine.expectations import evaluate
from engine.metrics import compute, decay_time
from engine.simulation import run_scenario
from engine.yaml_io import load_persona, load_scenario

ROOT = Path(__file__).resolve().parents[1]
DEFAULTS = ROOT / "calibration" / "defaults.yaml"


def _metrics(scenario_id: str, persona_id: str, n_ticks=None) -> dict:
    cfg = load_persona(ROOT / "data" / "personas" / f"{persona_id}.yaml", DEFAULTS)
    sc = load_scenario(ROOT / "data" / "scenarios" / f"{scenario_id}.yaml")
    _, trace = run_scenario(cfg, sc, n_ticks=n_ticks)
    return compute(trace)


# --- metric extraction --------------------------------------------------------------


def test_metric_namespace_basic():
    m = _metrics("same_soup_bad_day", "wojslaw")
    assert m["outburst_fired"] is True
    assert isinstance(m["action_sequence"], list)
    assert "peak_outburst" in m and "peak_anger" in m
    assert "peak_urge_boredom" in m  # raw urge exposed (M4 smooth-margin substrate)
    assert len(m["anger_curve"]) == len(m["action_sequence"])


def test_relational_metric_keys_present():
    m = _metrics("prisoner_bias_resentful", "cichy")
    # guard is the relational source in the prisoner_bias scenarios
    assert "resentment_delta__guard" in m
    assert "trust_delta__guard" in m
    assert "peak_resentment__guard" in m


def test_proactive_metrics_on_primed_idle():
    m = _metrics("idle_watch_primed", "welf", 12)
    assert m["proactive_start_count"] >= 1
    assert m["first_start_tick"] == 0
    assert m["peak_urge_boredom"] >= 0.6  # crossed theta_start


# --- group A/D litmus contrasts as DSL predicates ----------------------------------


def test_group_a_contrast_as_predicates():
    """Recruit bursts, veteran suppresses (same_soup_bad_day) -- the smooth form scores the
    raw outburst potential so a flat 0/1 isn't the only signal."""
    mbp = {
        "branic": _metrics("same_soup_bad_day", "branic"),
        "halgrim": _metrics("same_soup_bad_day", "halgrim"),
    }
    # discrete: recruit fires, veteran does not
    assert evaluate(
        {
            "type": "boolean",
            "persona": "branic",
            "metric": "outburst_fired",
            "equals": True,
        },
        mbp,
    ).satisfied
    assert evaluate(
        {
            "type": "boolean",
            "persona": "halgrim",
            "metric": "outburst_fired",
            "equals": False,
        },
        mbp,
    ).satisfied
    # smooth: recruit's peak outburst potential exceeds the veteran's, with a real margin
    r = evaluate(
        {
            "type": "comparative",
            "metric": "peak_outburst",
            "a": "branic",
            "b": "halgrim",
            "op": ">",
        },
        mbp,
    )
    assert r.satisfied and r.penalty == 0.0


def test_group_d_relational_asymmetry_as_predicates():
    """prisoner_bias: a resented guard's insult lands harder (more anger) and help is damped
    (less trust gained) than for the neutral guard."""
    mbp = {
        "resentful": _metrics("prisoner_bias_resentful", "cichy", 8),
        "neutral": _metrics("prisoner_bias_neutral", "cichy", 8),
    }
    # insult lands harder under resentment
    assert evaluate(
        {
            "type": "comparative",
            "metric": "peak_anger",
            "a": "resentful",
            "b": "neutral",
            "op": ">",
        },
        mbp,
    ).satisfied
    # help is damped: neutral gains more trust on the guard relation
    assert evaluate(
        {
            "type": "comparative",
            "metric": "trust_delta__guard",
            "a": "neutral",
            "b": "resentful",
            "op": ">",
        },
        mbp,
    ).satisfied


def test_decay_time_reached_flag():
    """decay_time returns (game-time to frac*peak, reached). The `reached` flag is what C1 uses:
    a decaying impulse reaches half-decay; a persisting one (resentment) does NOT, without measuring
    an unreachable time."""
    sec, reached = decay_time([0.0, 1.0, 0.6, 0.4, 0.3], dt=1.0, frac=0.5)
    assert (
        reached and sec == 2.0
    )  # peak idx1; 0.6>0.5, first <=0.5 at idx3 -> 2 ticks * dt
    sec2, reached2 = decay_time([0.0, 1.0, 1.0, 1.0, 1.0], dt=1.0, frac=0.5)
    assert not reached2  # never halves -> not reached (the resentment case)


def test_idle_boredom_shape_predicate():
    """idle_watch boredom curve rises monotonically (the M3b drift), expressed as a shape predicate.
    Checked on HALGRIM: low novelty_seeking -> does not seek from idle (D5), so boredom drifts up
    cleanly. (A fast-borer like welf now seeks, which relieves boredom -- not a monotonic-drift check.)"""
    m = _metrics("idle_watch", "halgrim", 60)
    r = evaluate(
        {
            "type": "shape",
            "persona": "halgrim",
            "metric": "boredom_curve",
            "shape": "monotonic_up",
        },
        {"halgrim": m},
    )
    assert r.satisfied and r.penalty == 0.0
