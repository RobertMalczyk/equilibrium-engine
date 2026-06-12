"""Gate G1 — Loop 2 closed through the world (spec section 8 burst, loop inventory).

The relief-seeking loop's SIGN is environmental: the SAME persona, same edges, same weights —
in a RICH world (activities to find) stress descends (stress -> seek -> engage self_activity ->
stress recovers: negative feedback); in a BARREN world (nothing to find) it climbs (stress ->
seek -> can't find -> +stress/tick: positive feedback). Asserted as ORDERINGS over a closed-loop
mock-world run, not hand-picked magnitudes. Loop-2 weights here are AUTHORED test fixtures.
"""

from engine.schema import Mode, Scenario
from engine.yaml_io import load_persona
from eval.mock_world import MockWorld, run_with_world

PERSONA = "data/personas/lutek.yaml"  # the fast-borer: seeks readily
DEFAULTS = "calibration/defaults.yaml"

LOOP2 = {
    "derived_weights": {
        "urge_boredom": {"stress": 0.60}
    },  # relief-seeking (return edge)
    "action_params": {
        "seek_stimulus": {"per_tick": {"stress": 0.015}}
    },  # can't-find wear
}
STRESSED = {"global_state": {"stress": 0.60, "boredom": 0.50, "fatigue": 0.10}}


def _run(world: MockWorld, n=80):
    cfg = load_persona(PERSONA, DEFAULTS, param_overrides=LOOP2)
    sc = Scenario(id="loop2", persona="lutek", initial_overrides=STRESSED, events=())
    return run_with_world(cfg, sc, world, n)


def _stress(tr, t):
    return tr.ticks[t].state_after_post.global_state["stress"]


def test_rich_world_is_negative_feedback_stress_descends():
    tr = _run(MockWorld(novelty_start=1.0, replenish_per_tick=0.02, work_fraction=0.0))
    assert any(
        tk.snapshot.mode == Mode.SEEKING and tk.state_after_post.mode == Mode.BUSY
        for tk in tr.ticks
    ), "never engaged: the rich world failed to confirm an activity"
    assert _stress(tr, len(tr.ticks) - 1) < _stress(
        tr, 0
    )  # relief: the loop is negative


def test_barren_world_is_positive_feedback_stress_climbs():
    tr = _run(MockWorld(novelty_start=0.0))  # nothing to find, ever
    assert any(tk.snapshot.mode == Mode.SEEKING for tk in tr.ticks), (
        "never sought: the relief-seeking term failed to drive the urge"
    )
    assert not any(tk.state_after_post.mode == Mode.BUSY for tk in tr.ticks)
    assert _stress(tr, len(tr.ticks) - 1) > _stress(
        tr, 0
    )  # wind-up: the loop is positive


def test_same_edges_opposite_sign_is_the_environment():
    rich = _run(MockWorld(novelty_start=1.0, replenish_per_tick=0.02))
    barren = _run(MockWorld(novelty_start=0.0))
    n = min(len(rich.ticks), len(barren.ticks)) - 1
    # one config, two worlds: the ordering IS the loop-sign contrast
    assert _stress(barren, n) > _stress(rich, n)


def test_neutral_weights_keep_todays_behaviour():
    cfg0 = load_persona(PERSONA, DEFAULTS)  # Loop-2 weights at their 0 defaults
    sc = Scenario(
        id="loop2_off", persona="lutek", initial_overrides=STRESSED, events=()
    )
    a = run_with_world(cfg0, sc, MockWorld(novelty_start=0.0), 40)
    b = run_with_world(cfg0, sc, MockWorld(novelty_start=0.0), 40)
    assert (
        a.to_json() == b.to_json()
    )  # deterministic baseline, no new dynamics leaked in
