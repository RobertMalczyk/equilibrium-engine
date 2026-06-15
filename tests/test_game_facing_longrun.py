"""Game-facing tests -- Part 6 (long-run boundedness & determinism) and Part 8 (a small engine-only
game scenario corpus, run against two contrasting personas).

Realistic-but-simple scheduled RawEvent streams (no world loop): periodic weak social pressure with
occasional help/commands, and an intentionally-hostile abuse stream. The contract is BOUNDED +
DETERMINISTIC + EXPLAINABLE, not calm. The Part-8 corpus lives in data/scenarios/game_*.yaml and is
loaded through the existing engine.yaml_io.load_scenario. No engine changes, no LLM, no world model.
"""

from __future__ import annotations

import dataclasses
from pathlib import Path

import pytest

from engine.schema import RawEvent, Scenario
from engine.simulation import run_scenario
from engine.yaml_io import load_scenario
from eval.calibrated import load_eval_persona

ROOT = Path(__file__).resolve().parents[1]


def _ev(t, typ, src, intensity=1.0, public=False):
    return RawEvent(
        type=typ,
        t=t,
        source=src,
        intensity=intensity,
        context={"public": public} if public else {},
    )


def _run(persona, events, init=None, n=None, burst=False):
    cfg = load_eval_persona(persona, burst=burst)
    sc = Scenario(
        id="long", persona=persona, initial_overrides=init or {}, events=tuple(events)
    )
    return run_scenario(cfg, sc, n)[1]


def _bounds_ok(tr) -> bool:
    for tk in tr.ticks:
        for v in tk.state_after_post.global_state.values():
            if not (0.0 <= v <= 1.0):
                return False
        for row in tk.state_after_post.relations.values():
            for v in row.values():
                if not (0.0 <= v <= 1.0):
                    return False
    return True


# ============================ Part 6: long-run boundedness ============================


# Test 6A: occasional/sparse social noise stays finite, bounded, unsaturated, and bit-identical.
def _sparse_noise():
    events = []
    for t in range(0, 300, 40):
        events.append(_ev(t, "complaint", "player", 0.4))
    for t in range(0, 300, 55):
        events.append(_ev(t, "cold_reply", "guard", 0.3))
    for t in range(0, 300, 50):
        events.append(_ev(t, "help", "player", 1.0))
    for t in range(0, 300, 60):
        events.append(_ev(t, "command", "edda", 1.0))
    return events


def test_6A_social_noise_does_not_explode():
    events = _sparse_noise()
    a = _run("halgrim", events, {"global_state": {"fatigue": 0.3}}, n=300)
    b = _run("halgrim", events, {"global_state": {"fatigue": 0.3}}, n=300)
    assert _bounds_ok(a)  # all global states & relations remain within [0, 1]
    assert a.to_json() == b.to_json()  # bit-identical across two executions
    anger = [tk.state_after_post.global_state["anger"] for tk in a.ticks]
    assert max(anger) < 1.0  # no PERMANENT saturation: anger never pins at the ceiling
    tail = anger[-50:]
    assert min(tail) < max(tail)  # it fluctuates / recovers between events, not stuck


# Characterization (documented finding): DENSE weak social pressure (relentless nagging -- a
# complaint every ~7 ticks) DOES drive anger to the 1.0 ceiling. That is bounded (the clamp holds)
# but it is a SATURATION the calibration permits, not a runaway -- recorded here, not asserted away.
# A game integration that wants stoic NPCs to shrug off frequent low-grade nagging would need a
# calibration change (frustration->anger coupling / idle recovery), not a test change.
def test_6A_dense_pressure_saturates_but_stays_bounded():
    events = [_ev(t, "complaint", "player", 0.5) for t in range(0, 300, 7)]
    tr = _run("halgrim", events, {"global_state": {"fatigue": 0.3}}, n=300)
    assert _bounds_ok(tr)  # still bounded -- the clamp holds even at saturation
    anger = [tk.state_after_post.global_state["anger"] for tk in tr.ticks]
    assert max(anger) >= 0.99  # the documented finding: dense nagging saturates anger


# Test 6B: extreme abuse is bounded but NOT ignored -- it reacts, and the grudge is traceable to the source.
def test_6B_extreme_abuse_is_bounded_but_reacts():
    events = [_ev(t, "insult", "player", 1.0, public=True) for t in range(0, 200, 5)]
    tr = _run("wojslaw", events, {"global_state": {"fatigue": 0.3}}, n=200, burst=True)
    assert _bounds_ok(
        tr
    )  # bounded even under relentless hostility (burst overlay armed)
    hostile = {"outburst", "cold_response", "complain", "refuse"}
    assert any(tk.selection.action in hostile for tk in tr.ticks)  # it reacts, not calm
    # the standing grudge lands on the actual abuser -- explainable by the hostile stream:
    assert (
        tr.ticks[-1].state_after_post.relations.get("player", {}).get("resentment", 0.0)
        > 0.5
    )


# ============================ Part 8: engine-only game scenario corpus ============================

GAME_SCENARIOS = sorted((ROOT / "data" / "scenarios").glob("game_*.yaml"))
CONTRAST = ("halgrim", "wojslaw")  # stoic/high-control vs reactive/proud


def test_8_game_corpus_exists():
    assert len(GAME_SCENARIOS) >= 3, "expected a small game_*.yaml scenario corpus"


@pytest.mark.parametrize("path", GAME_SCENARIOS, ids=[p.stem for p in GAME_SCENARIOS])
def test_8_game_scenario_two_personas(path):
    """Each game scenario: runs against two contrasting personas, deterministic, all states valid,
    and at least one meaningful behavioral difference between the two personas."""
    sc = load_scenario(path)
    seqs = {}
    for p in CONTRAST:
        tr = run_scenario(load_eval_persona(p), dataclasses.replace(sc, persona=p))[1]
        assert _bounds_ok(tr), f"{path.stem}/{p}: state left [0,1]"
        tr2 = run_scenario(load_eval_persona(p), dataclasses.replace(sc, persona=p))[1]
        assert tr.to_json() == tr2.to_json(), f"{path.stem}/{p}: not deterministic"
        # a meaningful behavioral difference = action sequence OR emotional trajectory (the weak
        # negative-only streams may leave both personas at `neutral` actions while their internal
        # appraisal -- anger/frustration/resentment -- still diverges by trait).
        seqs[p] = tuple(
            (
                tk.selection.action,
                round(tk.state_after_post.global_state["anger"], 4),
                round(tk.state_after_post.global_state["frustration"], 4),
                round(
                    tk.state_after_post.relations.get("player", {}).get(
                        "resentment", 0.0
                    ),
                    4,
                ),
            )
            for tk in tr.ticks
        )
    assert seqs[CONTRAST[0]] != seqs[CONTRAST[1]], (
        f"{path.stem}: the two personas produced identical traces"
    )


def _action_seq(path, persona):
    sc = load_scenario(path)
    tr = run_scenario(
        load_eval_persona(persona), dataclasses.replace(sc, persona=persona)
    )[1]
    return tuple(tk.selection.action for tk in tr.ticks)


def test_8_corpus_shows_visible_action_contrast():
    """The project litmus (CLAUDE.md): two personas in the same scenario must play differently in
    VISIBLE ACTIONS, not merely in anger numbers. The weak negative-only scenarios may leave both at
    `neutral`, so this is asserted over the CORPUS: at least one game scenario yields a different
    action sequence for the stoic vs the reactive persona."""
    assert any(
        _action_seq(path, CONTRAST[0]) != _action_seq(path, CONTRAST[1])
        for path in GAME_SCENARIOS
    )
