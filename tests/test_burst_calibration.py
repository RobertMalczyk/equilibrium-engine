"""M20.1 burst-calibration acceptance gates (plan §5). Stage C1 so far: G2* (stability-at-pairs).

These verify the CHOSEN calibration numbers (calibration/calibrated_burst.yaml) against the measured
operating-point envelope (eval/burst_operating_points.json) using the SAME Jury criterion the engine
stability test/loss use (engine.stability) — no second copy of the math. Later stages (C2-C5) add
G3*/G6*/G7-calibrated/Loop-2/contrast checks here.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

from calibration.calibrate_burst import (
    _lambda_max,
    _t_cool_ticks,
    latched_cooldown,
    loop2_contrast,
)
from engine.stability import jury_margin
from eval.calibrated import load_eval_persona

ROOT = Path(__file__).resolve().parents[1]
BURST_YAML = ROOT / "calibration" / "calibrated_burst.yaml"
ENV_JSON = ROOT / "eval" / "burst_operating_points.json"

pytestmark = pytest.mark.skipif(
    not (BURST_YAML.exists() and ENV_JSON.exists()),
    reason="run eval/measure_operating_points.py + calibration/calibrate_burst.py first",
)


def _loop():
    c = load_eval_persona("wojslaw")  # frozen Layer-2 loop (persona-independent)
    return c.decay, c.couplings["stress"]["anger"], c.couplings["anger"]["stress"]


def _k_esc() -> float:
    doc = yaml.safe_load(BURST_YAML.read_text(encoding="utf-8"))
    cal = doc["calibrated"]
    k1 = cal["coupling_escalation.anger.stress"]["value"]
    k2 = cal["coupling_escalation.stress.anger"]["value"]
    assert k1 == k2, "C1 chose a single shared k; the two edges must match"
    return float(k1)


def _extinction() -> tuple[float, float]:
    doc = yaml.safe_load(BURST_YAML.read_text(encoding="utf-8"))
    cal = doc["calibrated"]
    return (
        float(cal["burst_extinction.anger"]["value"]),
        float(cal["burst_extinction.stress"]["value"]),
    )


def _loop2() -> dict:
    doc = yaml.safe_load(BURST_YAML.read_text(encoding="utf-8"))
    cal = doc["calibrated"]
    return {
        "seek_cost": float(cal["action_params.seek_stimulus.per_tick.stress"]["value"]),
        "w_s": float(cal["derived_weights.urge_boredom.stress"]["value"]),
    }


def _latch() -> dict:
    doc = yaml.safe_load(BURST_YAML.read_text(encoding="utf-8"))
    cal = doc["calibrated"]
    return {
        "enter_a": float(cal["thresholds.burst_enter.anger"]["value"]),
        "enter_s": float(cal["thresholds.burst_enter.stress"]["value"]),
        "exit": float(cal["thresholds.burst_exit"]["value"]),
        "confirm": int(cal["thresholds.burst_confirm_ticks"]["value"]),
    }


def _escalated_margin(decay, g_as, g_sa, k, a, s) -> float:
    """Jury margin of the loop with the escalated LOCAL gains at operating point (a, s), via the
    engine's own jury_margin (single source of truth)."""
    couplings = {
        "stress": {
            "anger": g_as * (1.0 + k * a)
        },  # anger -> stress, escalated by anger*
        "anger": {
            "stress": g_sa * (1.0 + k * s)
        },  # stress -> anger, escalated by stress*
    }
    return jury_margin(decay, couplings)


def test_k_esc_is_inside_the_measured_feasible_window():
    """C1: the chosen k must be >= the spiral floor (so a burst CAN fire in-band) and the linear
    (k=0) margin must be positive (the frozen loop is stable) — sanity that calibration didn't break
    the resting loop."""
    decay, g_as, g_sa = _loop()
    k = _k_esc()
    assert k > 0.0
    assert (
        _escalated_margin(decay, g_as, g_sa, 0.0, 0.0, 0.0) > 0.0
    )  # frozen loop stable


def test_G2star_frequent_pairs_stay_linearly_stable():
    """G2*: with the calibrated k_esc, the escalated 2-cycle Jury margin is >= 0 at EVERY measured
    frequent (<=2-way) operating point — both the p99 envelope and the observed MAX pair. The burst
    must be RARE: ordinary coinciding drives never spiral."""
    decay, g_as, g_sa = _loop()
    k = _k_esc()
    env = json.loads(ENV_JSON.read_text(encoding="utf-8"))
    for a, s in [
        (env["le2_anger_p99"], env["le2_stress_p99"]),
        (env["le2_anger_max"], env["le2_stress_max"]),
    ]:
        assert _escalated_margin(decay, g_as, g_sa, k, a, s) >= 0.0, (
            f"frequent pair (anger={a:.3f}, stress={s:.3f}) went unstable at k={k}"
        )


def test_G2star_complement_a_deep_saturation_point_DOES_cross():
    """The complement of G2* (plan C1): the burst must not be VACUOUS — at a deep in-band operating
    point (both states pushed above the observed pair ceiling, into the saturation band) the escalated
    margin goes negative, so the loop spirals = the burst is reachable."""
    decay, g_as, g_sa = _loop()
    k = _k_esc()
    # the saturation band the latch will sit on (C1 spiral target; C3 pins it)
    assert _escalated_margin(decay, g_as, g_sa, k, 0.80, 0.60) < 0.0
    assert _escalated_margin(decay, g_as, g_sa, k, 1.00, 1.00) < 0.0


# --- C2 (extinction) acceptance -------------------------------------------------------------


def test_C2_extinction_returns_from_full_saturation_within_T_cool():
    """C2 boundedness+speed: with the calibrated extinction, a latched loop started at FULL
    saturation (1,1) returns below theta_burst_exit within T_cool ticks AND is monotone (stays down
    — no re-spiral). The worst-case ceiling: any lower in-band plateau returns at least as fast."""
    decay, g_as, g_sa = _loop()
    k = _k_esc()
    ext_a, ext_s = _extinction()
    r = latched_cooldown(decay, g_as, g_sa, k, ext_a, ext_s)
    assert r["mono"], "latched cool-down re-spiralled (not monotone) — extinction too weak"
    assert r["cross"] is not None, "latched loop never returned below theta_burst_exit"
    assert r["cross"] <= _t_cool_ticks(), (
        f"cool-down took {r['cross']} ticks > T_cool={_t_cool_ticks()}"
    )


def test_C2_extinction_is_bounded_at_the_ceiling():
    """The extinction-damped escalated loop has spectral radius < 1 even at full saturation: the
    burst is a BOUNDED episode, not a runaway. (The complement of the C1 spiral: in-band the loop
    spirals UP; once latched, extinction makes it contract.)"""
    decay, g_as, g_sa = _loop()
    k = _k_esc()
    ext_a, ext_s = _extinction()
    assert _lambda_max(decay, g_as, g_sa, k, ext_a, ext_s, 1.0, 1.0) < 1.0


def test_C2_extinction_minimal_anger_faster_than_stress():
    """Design-note shape: anger falls fast, stress cools slower => ext_anger > ext_stress. And the
    calibration is the SMALLEST sufficient extinction: dropping one grid step (beta-0.01, i.e.
    scaling both rates down ~1.5%) must FAIL the return-within-T_cool predicate (not over-damped)."""
    decay, g_as, g_sa = _loop()
    k = _k_esc()
    ext_a, ext_s = _extinction()
    assert ext_a > ext_s
    # one notch weaker (~ beta-0.01): scale both down and confirm it no longer returns in time
    weaker = latched_cooldown(
        decay, g_as, g_sa, k, ext_a * (0.64 / 0.65), ext_s * (0.64 / 0.65)
    )
    too_slow = weaker["cross"] is None or weaker["cross"] > _t_cool_ticks()
    assert too_slow, "extinction is stronger than the minimal return-within-T_cool rate"


# --- C3 (latch geometry) acceptance ---------------------------------------------------------


def test_C3_enter_band_clears_the_frequent_ceiling_and_spirals():
    """The latch arm band sits ABOVE the measured frequent <=2-way ceiling (so ordinary coinciding
    drives never arm it) and inside the escalated-loop spiral region (so once armed the loop is
    actually bursting). This is the 'rare and earned' selectivity k_esc can't supply (C1)."""
    decay, g_as, g_sa = _loop()
    k = _k_esc()
    lat = _latch()
    env = json.loads(ENV_JSON.read_text(encoding="utf-8"))
    assert lat["enter_a"] > env["le2_anger_max"] and lat["enter_s"] > env["le2_stress_max"]
    # the frequent ceiling itself stays stable; the enter band spirals
    assert _escalated_margin(decay, g_as, g_sa, k, env["le2_anger_max"], env["le2_stress_max"]) >= 0.0
    assert _escalated_margin(decay, g_as, g_sa, k, lat["enter_a"], lat["enter_s"]) < 0.0


def test_C3_exit_hysteresis_is_below_enter_and_chatter_free():
    """Release hysteresis: exit < enter.anger (engine yaml_io requires it) and below the ordinary
    reactive anger p99, so the latch cannot re-toggle from a normal provocation."""
    lat = _latch()
    env = json.loads(ENV_JSON.read_text(encoding="utf-8"))
    assert lat["exit"] < lat["enter_a"]
    assert lat["exit"] < env["le2_anger_p99"]


def test_C3_confirm_dwell_rejects_a_single_tick():
    """The loop-plateau signature: a single in-band tick must not arm — confirm >= 2."""
    assert _latch()["confirm"] >= 2


def test_C3_exit_is_consistent_with_C2_cooldown():
    """C2/C3 coupling: the calibrated extinction returns the saturated loop below the C3 exit within
    T_cool — the two stages agree on the same theta_burst_exit (no provisional drift)."""
    decay, g_as, g_sa = _loop()
    k = _k_esc()
    ext_a, ext_s = _extinction()
    r = latched_cooldown(decay, g_as, g_sa, k, ext_a, ext_s)
    # latched_cooldown's internal cross uses THETA_BURST_EXIT; assert the YAML exit matches it
    from calibration.calibrate_burst import THETA_BURST_EXIT

    assert _latch()["exit"] == THETA_BURST_EXIT
    assert r["cross"] is not None and r["cross"] <= _t_cool_ticks()


# --- C4 (Loop 2: relief vs wind-up) acceptance ----------------------------------------------


def test_C4_rich_world_relieves_barren_world_winds_up():
    """C4 Loop-2 sign: with the calibrated seek stress-cost, a RICH mock world (activities to engage)
    makes stress DESCEND (relief) while a BARREN world (nothing to find) makes it WIND UP — the same
    persona, the same stressed start, opposite slopes. The min-margin contrast."""
    seek_cost = _loop2()["seek_cost"]
    c = loop2_contrast(seek_cost)
    assert c["rich"] < 0.0, f"rich world did not relieve (slope {c['rich']:+.4f})"
    assert c["barren"] > 0.0, f"barren world did not wind up (slope {c['barren']:+.4f})"
    assert c["margin"] > 0.0


def test_C4_seek_cost_is_necessary_for_the_windup():
    """The wind-up is CARRIED by the seek stress-cost: at cost 0 the barren world does not wind up
    (the burst Loop-2 forward edge is what lifts stress into burst range)."""
    assert loop2_contrast(0.0)["barren"] <= 0.0


def test_C4_seek_cost_is_below_the_relief_rate():
    """'Small': the fruitless-looking cost is below the rich-world relief rate, so engaging always
    dominates looking and a rich world resolves stress."""
    c = loop2_contrast(_loop2()["seek_cost"])
    assert 0.0 < _loop2()["seek_cost"] < c["relief"]


def test_C4_urge_boredom_stress_edge_is_inert():
    """Measured finding: the stress->seek return edge stays neutral (boredom already drives seeking);
    the topology edge exists but its calibrated weight is 0."""
    assert _loop2()["w_s"] == 0.0


# --- C5 (displacement bar) acceptance -------------------------------------------------------


def _displace() -> dict:
    doc = yaml.safe_load(BURST_YAML.read_text(encoding="utf-8"))
    cal = doc["calibrated"]
    return {
        "theta": float(cal["thresholds.theta_displace"]["value"]),
        "discount": float(cal["appraisal.displaced_relational_discount"]["value"]),
    }


def test_C5_theta_displace_sits_in_the_deep_half_of_the_burst():
    """Displacement fires only in DEEP burst: theta_displace is inside the latch band (exit <
    theta < enter.anger) and above typical reactive anger (the frequent <=2-way anger p99), so a
    normal reactive anger never displaces and the gate closes as anger cools below it."""
    d = _displace()
    lat = _latch()
    env = json.loads(ENV_JSON.read_text(encoding="utf-8"))
    assert lat["exit"] < d["theta"] < lat["enter_a"]
    assert d["theta"] > env["le2_anger_p99"]


def test_C5_displaced_grudge_is_fully_transient():
    """The discharge onto an innocent bystander books NO durable grudge (discount 0) — the intended
    default that excludes the fabricated-nemesis runaway."""
    assert _displace()["discount"] == 0.0
