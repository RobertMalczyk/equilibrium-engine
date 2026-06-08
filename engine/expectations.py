"""expectations.evaluate (M.expectations) -- predicate DSL over metrics (spec section 16).

Pure. In: one Predicate (executable data: a plain dict) + ``metrics_by_persona`` mapping
``{persona_id: metrics}`` (each from ``metrics.compute``). Out: ``Result(satisfied, penalty,
explanation)``. ``penalty == 0.0`` when satisfied, else **proportional to the margin of
violation** so a derivative-free optimizer can descend it. Does NOT aggregate a loss (that is
the calibration loop, step 2).

Five predicate types (spec scenarios file, expectation schema):

  boolean      {metric, persona, equals}                 penalty 0/1 (DISCRETE)
  threshold    {metric, persona, op, value}              penalty = signed distance past value
  comparative  {metric, a, b, op}                        penalty = how far the order is wrong
  ordering     {metric, personas[], direction}           penalty = SUM of violated adjacent gaps
  shape        {metric(curve), persona, shape, params}   penalty = work to reach the shape

M4 note: a ``boolean`` penalty is flat 0/1 -- a blind spot for the optimizer when the goal is
really a threshold crossing of a continuous quantity (e.g. ``outburst_fired`` sits on
``peak_outburst`` vs ``theta_outburst``). For such goals PREFER a ``threshold`` predicate on the
raw metric (``peak_outburst``, ``peak_urge_boredom``, ...) so the margin is smooth. Keep
``boolean`` only for irreducibly discrete goals (e.g. ``final_action == "cooperate"``).
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Result:
    satisfied: bool
    penalty: float
    explanation: str


def evaluate(pred: dict, metrics_by_persona: dict) -> Result:
    kind = pred["type"]
    handler = _HANDLERS.get(kind)
    if handler is None:
        raise ValueError(f"unknown predicate type: {kind!r}")
    res = handler(pred, metrics_by_persona)
    # Optional normalization: divide the margin by a scale so penalties in different units
    # (e.g. seconds vs [0..1]) are commensurate in the loss. Does not change satisfied/sign.
    scale = pred.get("scale")
    if scale:
        res = Result(
            res.satisfied,
            res.penalty / float(scale),
            res.explanation + f" /scale={scale}",
        )
    return res


def _get(metrics_by_persona: dict, persona: str, metric: str):
    return metrics_by_persona[persona][metric]


def _boolean(pred: dict, mbp: dict) -> Result:
    persona, metric, want = pred["persona"], pred["metric"], pred["equals"]
    val = _get(mbp, persona, metric)
    ok = val == want
    return Result(
        ok,
        0.0 if ok else 1.0,
        f"{metric}[{persona}]={val!r} == {want!r}: {'ok' if ok else 'FAIL'}",
    )


def _threshold(pred: dict, mbp: dict) -> Result:
    persona, metric, op, v = pred["persona"], pred["metric"], pred["op"], pred["value"]
    val = _get(mbp, persona, metric)
    if op in (">", ">="):
        penalty = max(0.0, v - val)
        ok = val > v if op == ">" else val >= v
    elif op in ("<", "<="):
        penalty = max(0.0, val - v)
        ok = val < v if op == "<" else val <= v
    else:
        raise ValueError(f"bad threshold op: {op!r}")
    return Result(
        ok,
        penalty,
        f"{metric}[{persona}]={val:.6g} {op} {v:.6g}: penalty={penalty:.6g}",
    )


def _comparative(pred: dict, mbp: dict) -> Result:
    """Compare two scalars. Same metric across two runs (the common case), OR two DIFFERENT metrics
    via metric_a/metric_b (e.g. resentment settle vs anger settle on one run)."""
    a, b, op = pred["a"], pred["b"], pred["op"]
    ma_key = pred.get("metric_a", pred.get("metric"))
    mb_key = pred.get("metric_b", pred.get("metric"))
    ma, mb = _get(mbp, a, ma_key), _get(mbp, b, mb_key)
    if op == ">":
        ok, penalty = ma > mb, max(0.0, mb - ma)
    elif op == "<":
        ok, penalty = ma < mb, max(0.0, ma - mb)
    else:
        raise ValueError(f"bad comparative op: {op!r}")
    return Result(
        ok,
        penalty,
        f"{ma_key}[{a}]={ma:.6g} {op} {mb_key}[{b}]={mb:.6g}: penalty={penalty:.6g}",
    )


def _ordering(pred: dict, mbp: dict) -> Result:
    metric, personas = pred["metric"], pred["personas"]
    direction = pred.get("direction", "increasing")
    vals = [_get(mbp, p, metric) for p in personas]
    pairs = list(zip(vals, vals[1:]))
    if direction == "increasing":
        penalty = sum(
            max(0.0, lo - hi) for lo, hi in pairs
        )  # SUM of violated gaps, not max
        ok = all(lo < hi for lo, hi in pairs)
    elif direction == "decreasing":
        penalty = sum(max(0.0, hi - lo) for lo, hi in pairs)
        ok = all(lo > hi for lo, hi in pairs)
    else:
        raise ValueError(f"bad ordering direction: {direction!r}")
    return Result(
        ok,
        penalty,
        f"ordering {metric} {direction} over {personas}: vals={vals} penalty={penalty:.6g}",
    )


def _up_violation(series: list) -> float:
    return sum(max(0.0, a - b) for a, b in zip(series, series[1:]))


def _down_violation(series: list) -> float:
    return sum(max(0.0, b - a) for a, b in zip(series, series[1:]))


def _shape(pred: dict, mbp: dict) -> Result:
    persona, metric, shape = pred["persona"], pred["metric"], pred["shape"]
    series = _get(mbp, persona, metric)
    if shape == "monotonic_up":
        penalty = _up_violation(series)
        ok = penalty == 0.0
    elif shape == "monotonic_down":
        penalty = _down_violation(series)
        ok = penalty == 0.0
    elif shape == "peak":
        n = len(series)
        cands = [
            _up_violation(series[: k + 1]) + _down_violation(series[k:])
            for k in range(1, n - 1)
        ]
        penalty = min(cands) if cands else float("inf")
        ok = bool(cands) and penalty == 0.0
    elif shape == "converges_to":
        v, within = pred["value"], pred["within"]
        tol = pred.get("tol", 0.0)
        tail = series[within:]
        worst = max((abs(x - v) for x in tail), default=0.0)
        penalty = max(0.0, worst - tol)
        ok = penalty == 0.0
    else:
        raise ValueError(f"bad shape: {shape!r}")
    return Result(
        ok, penalty, f"shape {shape} on {metric}[{persona}]: penalty={penalty:.6g}"
    )


_HANDLERS = {
    "boolean": _boolean,
    "threshold": _threshold,
    "comparative": _comparative,
    "ordering": _ordering,
    "shape": _shape,
}
