"""Predicate DSL (expectations.py) -- margin-MAGNITUDE tests, not just sign.

The whole point of a margin evaluator is that the penalty equals the violation distance: a
predicate violated by 0.1 must return 0.1 (not 1, not 0.2), and an ordering with two violated
pairs must return the SUM of the gaps (not the max). Those are exactly where a margin evaluator
quietly lies and the optimizer then descends the wrong way.
"""

import pytest

from engine.expectations import evaluate


def test_boolean_discrete():
    mbp = {"x": {"final_action": "cooperate"}}
    assert (
        evaluate(
            {
                "type": "boolean",
                "persona": "x",
                "metric": "final_action",
                "equals": "cooperate",
            },
            mbp,
        ).penalty
        == 0.0
    )
    r = evaluate(
        {
            "type": "boolean",
            "persona": "x",
            "metric": "final_action",
            "equals": "refuse",
        },
        mbp,
    )
    assert r.penalty == 1.0 and not r.satisfied


def test_threshold_margin_is_the_distance():
    mbp = {"x": {"m": 0.4}}
    r = evaluate(
        {"type": "threshold", "persona": "x", "metric": "m", "op": ">", "value": 0.5},
        mbp,
    )
    assert not r.satisfied
    assert r.penalty == pytest.approx(0.1)  # the distance, ...
    assert r.penalty != pytest.approx(1.0)  # ... not a flat 0/1, ...
    assert r.penalty != pytest.approx(0.2)  # ... not double.
    # satisfied side -> exactly 0
    assert (
        evaluate(
            {
                "type": "threshold",
                "persona": "x",
                "metric": "m",
                "op": "<",
                "value": 0.5,
            },
            mbp,
        ).penalty
        == 0.0
    )


def test_threshold_le_ge_boundaries():
    mbp = {"x": {"m": 0.5}}
    assert evaluate(
        {"type": "threshold", "persona": "x", "metric": "m", "op": ">=", "value": 0.5},
        mbp,
    ).satisfied
    assert not evaluate(
        {"type": "threshold", "persona": "x", "metric": "m", "op": ">", "value": 0.5},
        mbp,
    ).satisfied
    # both report 0 penalty at the boundary (margin is zero), only `satisfied` differs
    assert (
        evaluate(
            {
                "type": "threshold",
                "persona": "x",
                "metric": "m",
                "op": ">",
                "value": 0.5,
            },
            mbp,
        ).penalty
        == 0.0
    )


def test_comparative_margin():
    mbp = {"a": {"m": 0.3}, "b": {"m": 0.5}}
    r = evaluate(
        {"type": "comparative", "metric": "m", "a": "a", "b": "b", "op": ">"}, mbp
    )
    assert not r.satisfied and r.penalty == pytest.approx(0.2)
    assert (
        evaluate(
            {"type": "comparative", "metric": "m", "a": "a", "b": "b", "op": "<"}, mbp
        ).penalty
        == 0.0
    )


def test_ordering_is_sum_of_gaps_not_max():
    # increasing wanted, vals [3, 1, 0]: gaps (3->1)=2 and (1->0)=1 -> SUM 3, not max 2.
    mbp = {"lo": {"m": 3}, "mid": {"m": 1}, "hi": {"m": 0}}
    r = evaluate(
        {
            "type": "ordering",
            "metric": "m",
            "personas": ["lo", "mid", "hi"],
            "direction": "increasing",
        },
        mbp,
    )
    assert not r.satisfied
    assert r.penalty == pytest.approx(3.0)
    assert r.penalty != pytest.approx(2.0)  # NOT the max gap
    # a correctly increasing triple -> 0
    good = {"lo": {"m": 0}, "mid": {"m": 1}, "hi": {"m": 2}}
    assert (
        evaluate(
            {
                "type": "ordering",
                "metric": "m",
                "personas": ["lo", "mid", "hi"],
                "direction": "increasing",
            },
            good,
        ).penalty
        == 0.0
    )


def test_shape_monotonic_up_penalizes_each_dip():
    mbp = {"x": {"c": [0.1, 0.2, 0.15, 0.3]}}  # one dip of 0.05
    r = evaluate(
        {"type": "shape", "persona": "x", "metric": "c", "shape": "monotonic_up"}, mbp
    )
    assert not r.satisfied and r.penalty == pytest.approx(0.05)
    assert (
        evaluate(
            {"type": "shape", "persona": "x", "metric": "c", "shape": "monotonic_up"},
            {"x": {"c": [0.1, 0.1, 0.2, 0.3]}},
        ).penalty
        == 0.0
    )


def test_shape_peak_requires_interior_max():
    # a clean peak -> 0
    assert (
        evaluate(
            {"type": "shape", "persona": "x", "metric": "c", "shape": "peak"},
            {"x": {"c": [0.0, 0.5, 1.0, 0.4, 0.1]}},
        ).penalty
        == 0.0
    )
    # monotonically rising -> not a peak (max at the endpoint): positive penalty
    r = evaluate(
        {"type": "shape", "persona": "x", "metric": "c", "shape": "peak"},
        {"x": {"c": [0.0, 0.25, 0.5, 0.75, 1.0]}},
    )
    assert not r.satisfied and r.penalty > 0.0


def test_shape_converges_to_within():
    # settles to ~0.1 after t=2
    mbp = {"x": {"c": [0.9, 0.5, 0.12, 0.10, 0.10]}}
    r = evaluate(
        {
            "type": "shape",
            "persona": "x",
            "metric": "c",
            "shape": "converges_to",
            "value": 0.10,
            "within": 2,
            "tol": 0.05,
        },
        mbp,
    )
    assert r.satisfied and r.penalty == 0.0
    # without tolerance, the 0.12 sample is 0.02 away -> that exact margin
    r2 = evaluate(
        {
            "type": "shape",
            "persona": "x",
            "metric": "c",
            "shape": "converges_to",
            "value": 0.10,
            "within": 2,
        },
        mbp,
    )
    assert r2.penalty == pytest.approx(0.02)


def test_scale_normalizes_the_margin():
    # the same violation, divided by scale, so seconds-margins are commensurate with [0..1] ones.
    mbp = {"x": {"m": 0.4}}
    raw = evaluate(
        {"type": "threshold", "persona": "x", "metric": "m", "op": ">", "value": 0.5},
        mbp,
    )
    scaled = evaluate(
        {
            "type": "threshold",
            "persona": "x",
            "metric": "m",
            "op": ">",
            "value": 0.5,
            "scale": 2.0,
        },
        mbp,
    )
    assert raw.penalty == pytest.approx(0.1)
    assert scaled.penalty == pytest.approx(0.05)  # 0.1 / 2
    assert scaled.satisfied == raw.satisfied  # scale changes only the magnitude


def test_comparative_cross_metric():
    # resentment settle > anger settle on one run (two DIFFERENT metrics, same run label).
    mbp = {"r": {"settle_res": 300.0, "settle_anger": 150.0}}
    r = evaluate(
        {
            "type": "comparative",
            "a": "r",
            "b": "r",
            "metric_a": "settle_res",
            "metric_b": "settle_anger",
            "op": ">",
        },
        mbp,
    )
    assert r.satisfied and r.penalty == 0.0


def test_unknown_type_raises():
    with pytest.raises(ValueError):
        evaluate({"type": "nonsense"}, {})
