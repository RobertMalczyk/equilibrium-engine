"""Game-facing tests -- Part 3 (source attribution & residual anger for the new social events),
Part 7 (sleep/night with slow social memory), Part 9 (trace usefulness for a game integration).

These extend the existing target-policy and night/sleep coverage to the cold_reply/refusal/complaint
vocabulary, and pin down the trace fields a game needs to explain a tick. CHARACTERIZATION only --
no engine changes, no scripting, no world model, no LLM. Directional assertions.
"""

from __future__ import annotations

import pytest

from engine.schema import RawEvent, Scenario
from engine.simulation import run_scenario
from eval.calibrated import load_eval_persona
from eval.night_runner import DAY_LEN, day_summaries, run_nights

NEW_NEG = ("cold_reply", "refusal", "complaint")

# already carrying some heat, so a SECOND source interacting can catch displaced anger:
HOT = {"global_state": {"anger": 0.3, "frustration": 0.3}}


def _ev(t, typ, src, intensity=1.0, public=False):
    return RawEvent(
        type=typ,
        t=t,
        source=src,
        intensity=intensity,
        context={"public": public} if public else {},
    )


def _run(persona, events, init=None, n=8):
    cfg = load_eval_persona(persona)
    sc = Scenario(
        id="mem", persona=persona, initial_overrides=init or {}, events=tuple(events)
    )
    return run_scenario(cfg, sc, n)[1]


def _act(tr, t):
    return tr.ticks[t].selection.action


def _cold(tr, t):
    return tr.ticks[t].potentials["cold_response"]


# ============================ Part 3: source attribution & residual anger ============================


# Test 3A: the provoker stays the relevant target -- a follow-up from the SAME source is not spared.
@pytest.mark.parametrize("prov", NEW_NEG)
def test_3A_provoker_remains_relevant(prov):
    """A provokes with a new social event, then A issues a command shortly after. The reactive
    tendency toward A is allowed to remain elevated (A is the provoker, not a bystander) -- strictly
    higher than the same follow-up command coming from an uninvolved RESPECTED source."""
    same = _run(
        "halgrim",
        [_ev(0, prov, "wojslaw", 1.0, public=True), _ev(2, "command", "wojslaw")],
        HOT,
    )
    other = _run(
        "halgrim",
        [_ev(0, prov, "wojslaw", 1.0, public=True), _ev(2, "command", "edda")],
        HOT,
    )
    assert _cold(same, 2) > _cold(other, 2)


# Test 3B: a respected bystander is spared the displaced anger.
@pytest.mark.parametrize("prov", NEW_NEG)
def test_3B_respected_bystander_is_spared(prov):
    """Wojsław provokes (new social event), then RESPECTED Edda gives a routine order within the
    window: Halgrim must not vent Wojsław-anger onto Edda -- the obedience response wins instead.
    Mirrors the existing insult-based target-policy intent for the new vocabulary."""
    tr = _run(
        "halgrim",
        [_ev(0, prov, "wojslaw", 1.0, public=True), _ev(2, "command", "edda")],
        HOT,
    )
    assert _act(tr, 2) not in ("cold_response", "outburst")
    assert _act(tr, 2) == "cooperate"


# Test 3C: a low-respect bystander is less protected than a respected one.
# Restricted to refusal/complaint: cold_reply (the mildest event) leaves too little residual heat to
# produce ANY displaced spillover, so it cannot differentiate the two bystanders (see the next test).
@pytest.mark.parametrize("prov", ("refusal", "complaint"))
def test_3C_low_respect_bystander_less_protected(prov):
    base = [_ev(0, prov, "wojslaw", 1.0, public=True)]
    edda = _run("halgrim", base + [_ev(2, "command", "edda")], HOT)  # respect 0.65
    player = _run("halgrim", base + [_ev(2, "command", "player")], HOT)  # respect 0.50
    assert _cold(edda, 2) < _cold(player, 2)  # the respected source is spared MORE


def test_3C_cold_reply_too_mild_to_displace():
    """Documented finding: a single cold_reply is too weak (mildest of the negative events) to leave
    residual heat that spills onto a later bystander -- BOTH a respected and a low-respect follow-up
    source draw the same (zero) displaced cold_response. The respect-graded sparing only bites for the
    stronger refusal/complaint/insult provocations. This is calibration texture, not a topology gap."""
    base = [_ev(0, "cold_reply", "wojslaw", 1.0, public=True)]
    edda = _run("halgrim", base + [_ev(2, "command", "edda")], HOT)
    player = _run("halgrim", base + [_ev(2, "command", "player")], HOT)
    assert _cold(edda, 2) == _cold(player, 2) == 0.0


# ============================ Part 7: night/sleep with slow social memory ============================


def _player_insults(d):
    if d != 0:
        return []
    return [
        (6, {"type": "insult", "source": "player", "intensity": 0.9, "context": {"public": True}}),
        (13, {"type": "insult", "source": "player", "intensity": 0.9, "context": {"public": True}}),
    ]


def _player_res(tr, t):
    return tr.ticks[t].state_after_post.relations.get("player", {}).get("resentment", 0.0)


def test_7A_night_resets_fast_state_slow_relation_persists():
    """The player provokes on day 0; across the night the FAST anger bottoms out (the reset) while
    the SLOW grudge toward the player survives the night boundary -- fast affect resets faster than
    slow social memory (mirrors the existing night tests, here keyed on a `player` source)."""
    _, tr = run_nights(
        "wojslaw",
        days=2,
        day_events=_player_insults,
        initial={"global_state": {"fatigue": 0.5}},
    )
    s = day_summaries(tr, 2, source="player")
    assert s[0]["min_anger"] < 0.20  # the fast state is driven down overnight
    res_dusk0 = _player_res(tr, DAY_LEN - 1)
    res_dawn1 = _player_res(tr, DAY_LEN)  # first tick after the night
    assert res_dusk0 > 0.05  # a grudge formed
    assert res_dawn1 >= res_dusk0 - 0.02  # ...and it is NOT erased overnight (slow state)


def test_7A_deterministic():
    def actions():
        _, tr = run_nights(
            "wojslaw",
            days=2,
            day_events=_player_insults,
            initial={"global_state": {"fatigue": 0.5}},
        )
        return [(tk.t, tk.selection.action) for tk in tr.ticks]

    assert actions() == actions()


# ============================ Part 9: trace usefulness for a game integration ============================


def test_9_trace_exposes_full_tick_anatomy():
    """One tick's serialized trace must let a game explain WHAT happened: the input event, the mapped
    semantic channels, state before/after the commit, the potentials, and the selected action."""
    tr = _run("wojslaw", [_ev(0, "insult", "player", 1.0, public=True)], n=1)
    tk = tr.to_dict()["ticks"][0]
    for fld in (
        "event",
        "eff_inputs",
        "snapshot",
        "state_after_commit",
        "derived_post",
        "potentials",
        "selection",
        "state_after_post",
    ):
        assert fld in tk, f"trace tick is missing '{fld}'"
    assert tk["event"]["type"] == "insult"
    assert tk["event"]["source"] == "player"  # the input event preserves its source id
    assert "insult" in tk["eff_inputs"]  # the mapped semantic channel is visible
    assert tk["eff_inputs"]["insult"]["source"] == "player"  # ...with the source attributed
    assert "global" in tk["snapshot"]  # state BEFORE the commit
    assert "global" in tk["state_after_commit"]  # state AFTER the commit
    assert tk["potentials"]  # a non-empty potential vector
    assert tk["selection"]["action"]  # a selected action


@pytest.mark.parametrize("typ", NEW_NEG)
def test_9_source_preserved_for_new_social_events(typ):
    tr = _run("wojslaw", [_ev(0, typ, "player", 1.0)], n=1)
    tk = tr.to_dict()["ticks"][0]
    assert tk["eff_inputs"][typ]["source"] == "player"
