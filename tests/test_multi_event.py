"""M-MEM.0 -- multi-event-per-tick plumbing.

The engine historically delivered exactly ONE RawEvent per tick: run_scenario built
`events_by_t = {ev.t: ev for ev in events}`, so two events sharing a tick collided and the last one won.
These tests pin the lifted constraint: a tick may carry many events, each mapped and merged with correct
per-source attribution, while a scenario with <=1 event per tick stays byte-identical (the golden suite,
test_tick_golden.py, is the byte-identical gate; here we prove the NEW capability + the single/empty paths).
"""

from __future__ import annotations

from pathlib import Path

from engine.schema import RawEvent, Scenario
from engine.simulation import run_scenario
from engine.yaml_io import load_persona
from eval.observe import relation_trajectory

ROOT = Path(__file__).resolve().parents[1]
DEFAULTS = ROOT / "calibration" / "defaults.yaml"
WOJSLAW = ROOT / "data" / "personas" / "wojslaw.yaml"


def _cfg():
    return load_persona(WOJSLAW, DEFAULTS)


def _scenario(events):
    return Scenario(id="multi", persona="wojslaw", initial_overrides={}, events=tuple(events))


def test_two_events_same_tick_are_both_delivered():
    """Two insults from two DIFFERENT sources on the SAME tick must BOTH land (today one is dropped)."""
    sc = _scenario(
        [
            RawEvent(type="insult", t=0, source="alpha", intensity=1.0),
            RawEvent(type="insult", t=0, source="beta", intensity=1.0),
        ]
    )
    _, tr = run_scenario(_cfg(), sc, n_ticks=2)
    # both insulters earn a resentment grudge -- neither event was silently dropped
    assert relation_trajectory(tr, "alpha", "resentment")[-1] > 0.0
    assert relation_trajectory(tr, "beta", "resentment")[-1] > 0.0


def test_empty_tick_is_idle():
    """A tick with no events is a clean idle tick (no crash, no spurious reaction)."""
    sc = _scenario([RawEvent(type="insult", t=1, source="x", intensity=1.0)])
    _, tr = run_scenario(_cfg(), sc, n_ticks=3)  # t0 and t2 carry no event
    assert len(tr.ticks) == 3
    assert tr.ticks[0].event is None  # nothing happened at t0


def test_single_event_trace_keeps_scalar_event_field():
    """Byte-identical seam: with <=1 event a tick's trace carries the single RawEvent (not a list), so the
    existing golden traces are unchanged."""
    sc = _scenario([RawEvent(type="insult", t=0, source="x", intensity=1.0)])
    _, tr = run_scenario(_cfg(), sc, n_ticks=1)
    ev = tr.ticks[0].event
    assert isinstance(ev, RawEvent) and ev.source == "x"


# --- M-MEM.1: multi-source primary-provoker arbitration --------------------------------


def test_strongest_provoker_becomes_the_primary():
    """Two insults on one tick: the reaction keys on the STRONGEST provoker, not scenario order. The weak
    insulter is listed FIRST, so M-MEM.0 (primary = first) would pick it -- M-MEM.1 picks the strong one."""
    sc = _scenario(
        [
            RawEvent(type="insult", t=0, source="weak", intensity=0.2),
            RawEvent(type="insult", t=0, source="strong", intensity=1.0),
        ]
    )
    rt, _ = run_scenario(_cfg(), sc, n_ticks=1)
    assert rt.last_provocation_source == "strong"


def test_provoker_beats_a_gesture_for_the_primary():
    """A benign gesture (help) and an insult on the same tick, gesture listed FIRST: the primary provoker is
    the INSULTER (the gesture is not a provocation), so the lingering anger is attributed to the insulter."""
    sc = _scenario(
        [
            RawEvent(type="help", t=0, source="friend", intensity=1.0),
            RawEvent(type="insult", t=0, source="enemy", intensity=1.0),
        ]
    )
    rt, _ = run_scenario(_cfg(), sc, n_ticks=1)
    assert rt.last_provocation_source == "enemy"


def test_fan_out_n_sources_on_one_tick_all_land():
    """The witness-fan-out shape (the seam M-J.3.3 will consume): a single tick carries events from MANY
    distinct sources -- here one 'accuser' plus three 'witnesses' -- and EVERY source's relational deposit
    lands. No engine fan-out helper is needed; authoring same-tick multi-source events suffices."""
    srcs = ["accuser", "witness_1", "witness_2", "witness_3"]
    sc = _scenario([RawEvent(type="insult", t=0, source=s, intensity=1.0) for s in srcs])
    _, tr = run_scenario(_cfg(), sc, n_ticks=2)
    for s in srcs:
        assert relation_trajectory(tr, s, "resentment")[-1] > 0.0
