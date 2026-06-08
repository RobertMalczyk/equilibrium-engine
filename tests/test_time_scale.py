"""The `time_scale` knob (tick.time_scale, default 1.0) -- merge-safety locks.

These pin the two guarantees that make merging the believable-timescale work to main safe: (1) at the
DEFAULT (1.0) the knob is an exact no-op, so the frozen path is preserved and the world is reverted simply
by leaving the knob alone; (2) any setting is a pure CLOCK reparametrization -- scaling every half-life by k
leaves the per-tick decay ratios invariant, so the tick-by-tick BEHAVIOUR is unchanged (only dt stretches).
"""

import math
from pathlib import Path

from engine.schema import RawEvent, Scenario
from engine.simulation import run_scenario
from engine.yaml_io import load_persona

ROOT = Path(__file__).resolve().parents[1]
DEFAULTS = ROOT / "calibration" / "defaults.yaml"


def _cfg(name="wojslaw", time_scale=None):
    ov = {"tick": {"time_scale": time_scale}} if time_scale is not None else None
    return load_persona(
        ROOT / "data" / "personas" / f"{name}.yaml", DEFAULTS, param_overrides=ov
    )


def _scenario():
    return Scenario(
        id="ts",
        persona="wojslaw",
        initial_overrides={
            "global_state": {"anger": 0.3, "stress": 0.3, "fatigue": 0.4}
        },
        events=(
            RawEvent(
                type="insult",
                t=2,
                source="player",
                intensity=0.8,
                context={"public": True},
            ),
            RawEvent(
                type="food_given",
                t=10,
                source="marta",
                item="cabbage_soup",
                intensity=1.0,
                context={"public": False},
            ),
            RawEvent(type="nightfall", t=40, intensity=1.0),
        ),
    )


def test_default_is_identity():
    """time_scale absent == time_scale 1.0 -> dt/half_lives/decay identical: the frozen path is preserved and
    revertible just by leaving the knob at its default."""
    a, b = _cfg(), _cfg(time_scale=1.0)
    assert a.dt == b.dt
    assert a.half_lives == b.half_lives
    assert a.decay == b.decay


def test_reparametrization_preserves_behaviour():
    """Scaling every half-life by the knob is a pure clock reparametrization: the per-tick ACTION sequence is
    identical and every per-tick state matches to float precision -- so the world can be sped/slowed/reverted
    by the one knob with behaviour unchanged."""
    _, t1 = run_scenario(_cfg(time_scale=1.0), _scenario(), n_ticks=80)
    _, tk = run_scenario(_cfg(time_scale=37.0), _scenario(), n_ticks=80)
    assert [x.selection.action for x in t1.ticks] == [
        x.selection.action for x in tk.ticks
    ]
    for x, y in zip(t1.ticks, tk.ticks):
        gx, gy = x.state_after_post.global_state, y.state_after_post.global_state
        for s in gx:
            assert math.isclose(gx[s], gy[s], abs_tol=1e-9), (
                f"state {s} drifted under the knob"
            )


def test_dt_scales_linearly():
    """dt scales linearly with the knob, so the identical tick-trace spans k x the wall-clock."""
    assert math.isclose(
        _cfg(time_scale=50.0).dt, 50.0 * _cfg(time_scale=1.0).dt, rel_tol=1e-9
    )
