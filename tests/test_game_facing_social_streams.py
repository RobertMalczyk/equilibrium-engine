"""Game-facing tests -- Part 1 (player-like source streams), Part 2 (negative-event severity),
Part 4 (public vs private appraisal), Part 5 (persona contrast under one shared stream).

SIMULATION-level CHARACTERIZATION of how the single-persona engine behaves under realistic,
game-like event streams. No new engine code, no event->action scripting, no world model, no LLM.
"player" is used only as an ordinary RawEvent.source string (every persona already carries a
`player` relation row) -- this is NOT a player system. Assertions are DIRECTIONAL (relative
orderings, set differences), not hand-picked magnitudes, per the project's persona-contrast /
no-magic-number style. Runs on the calibrated eval persona path (eval.calibrated.load_eval_persona).
"""

from __future__ import annotations

import pytest

from engine.schema import RawEvent, Scenario
from engine.simulation import run_scenario
from eval.calibrated import load_eval_persona

NEW_NEG = ("cold_reply", "refusal", "complaint")


def _ev(t, typ, src="player", intensity=1.0, public=False):
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
        id="game", persona=persona, initial_overrides=init or {}, events=tuple(events)
    )
    return run_scenario(cfg, sc, n)[1]


def _res(tr, t, src="player"):
    return tr.ticks[t].state_after_post.relations.get(src, {}).get("resentment", 0.0)


# ============================ Part 1: player-like source streams ============================


# Test 1A: repeated minor hostility from one source -> a bounded grudge, no instant saturation.
def test_1A_repeated_minor_hostility_builds_bounded_resentment():
    events = [
        _ev(t, "cold_reply" if (t // 2) % 2 else "complaint", "player", intensity=0.4)
        for t in range(0, 10, 2)
    ]
    tr = _run("halgrim", events, n=11)
    last = tr.ticks[-1].state_after_post
    assert "player" in last.relations  # a relational source gets/updates a relation row
    r = last.relations["player"]["resentment"]
    assert r > 0.0  # resentment toward the player moved up (from halgrim's 0.0 baseline)
    assert r < 0.95  # ...but weak events alone do NOT saturate into a permanent max grudge
    assert all(  # nor pin anger to the ceiling
        tk.state_after_post.global_state["anger"] < 0.95 for tk in tr.ticks
    )


def test_1A_deterministic():
    events = [_ev(t, "cold_reply", "player", 0.4) for t in range(0, 10, 2)]
    a = _run("halgrim", events, n=11)
    b = _run("halgrim", events, n=11)
    assert a.to_json() == b.to_json()


# Test 1B: repeated help from one source -> trust grows, no resentment.
def test_1B_repeated_help_builds_trust_no_resentment():
    init = {"relations": {"player": {"trust": 0.4, "respect": 0.4, "resentment": 0.0}}}
    events = [_ev(t, "help", "player", 1.0) for t in range(0, 8, 2)]
    tr = _run("wojslaw", events, init, n=9)
    row = tr.ticks[-1].state_after_post.relations["player"]
    assert row["trust"] > 0.4  # positive relational effect from pure help
    assert row["resentment"] <= 1e-9  # pure help adds no resentment


# Test 1C: alternating hostility and help -> slow memory, not an instant reset.
def test_1C_help_does_not_erase_slow_negative_memory():
    init = {"relations": {"player": {"trust": 0.4, "respect": 0.4, "resentment": 0.0}}}
    events = [
        _ev(0, "insult", "player", 0.9, public=True),
        _ev(6, "help", "player", 1.0),
        _ev(12, "insult", "player", 0.9, public=True),
    ]
    tr = _run("wojslaw", events, init, n=16)
    res_after_insult1 = _res(tr, 0)
    res_after_help = _res(tr, 6)
    res_final = _res(tr, 15)
    assert res_after_insult1 > 0.0  # the first insult built a grudge
    # one help in the middle does NOT zero the slow grudge (source-specific memory persists):
    assert res_after_help > 0.5 * res_after_insult1
    assert res_final > 0.0  # the final relation reflects mixed history, not a pure reset


# ============================ Part 2: negative events are not all insults ============================


def _state1(persona, typ, init, src="x"):
    tr = _run(persona, [_ev(0, typ, src, 1.0)], init, n=1)
    return tr.ticks[0].state_after_commit.global_state


def _pots1(persona, typ, init, src="x"):
    tr = _run(persona, [_ev(0, typ, src, 1.0)], init, n=1)
    return tr.ticks[0].potentials


# Test 2A: relative severity ordering at the same intensity & source.
def test_2A_insult_is_strongest_anger():
    init = {"global_state": {"anger": 0.0, "frustration": 0.0, "stress": 0.0}}
    anger = {t: _state1("wojslaw", t, init)["anger"] for t in ("insult",) + NEW_NEG}
    for t in NEW_NEG:
        assert anger["insult"] > anger[t], f"insult anger should exceed {t}"


def test_2A_cold_reply_is_mildest():
    init = {"global_state": {"anger": 0.0, "frustration": 0.0, "stress": 0.0}}
    g = {t: _state1("wojslaw", t, init) for t in NEW_NEG}
    # strictly mildest on BOTH dims (strict, so an alias of another event would fail)
    assert g["cold_reply"]["anger"] < g["complaint"]["anger"]
    assert g["cold_reply"]["anger"] < g["refusal"]["anger"]
    assert g["cold_reply"]["frustration"] < g["complaint"]["frustration"]
    assert g["cold_reply"]["frustration"] < g["refusal"]["frustration"]


def test_2A_complaint_weights_frustration_over_anger():
    init = {"global_state": {"anger": 0.0, "frustration": 0.0}}
    g = _state1("wojslaw", "complaint", init)
    assert g["frustration"] > g["anger"]


def test_2A_refusal_distinct_from_insult_and_command():
    init = {"global_state": {"anger": 0.0, "frustration": 0.0}}
    refusal = _state1("wojslaw", "refusal", init)
    insult = _state1("wojslaw", "insult", init)
    command = _state1("wojslaw", "command", init)
    assert refusal["anger"] < insult["anger"]  # a refusal is not an attack
    # ...and not an alias of a command either (different global footprint):
    assert (refusal["anger"], refusal["frustration"]) != (
        command["anger"],
        command["frustration"],
    )


# Test 2B: the four negative events are distinguishable in the potential vector (not aliases).
def test_2B_negative_events_distinguishable_in_potentials():
    init = {"global_state": {"anger": 0.2, "frustration": 0.2}}
    pots = {
        t: tuple(round(v, 9) for v in _pots1("wojslaw", t, init).values())
        for t in ("insult",) + NEW_NEG
    }
    # all FOUR produce pairwise-distinct potential vectors -- none is an alias of any other
    # (a strictly stronger check than "each differs from insult"):
    assert len(set(pots.values())) == 4, "negative events are not all distinguishable"
    for t in NEW_NEG:
        assert pots[t] != pots["insult"], f"{t} potentials alias insult's"


# ============================ Part 4: public vs private social context ============================


@pytest.mark.parametrize("typ", NEW_NEG)
def test_4_public_at_least_as_strong_as_private(typ):
    def res(pub):
        tr = _run("wojslaw", [_ev(0, typ, "player", 1.0, public=pub)], n=1)
        return (
            tr.ticks[0].state_after_commit.relations.get("player", {}).get(
                "resentment", 0.0
            )
        )

    assert res(True) >= res(False)


@pytest.mark.parametrize("typ", NEW_NEG)
def test_4_public_strictly_amplified_by_exposure(typ):
    """Characterization: the relation_filter's public exposure makes a public social slight STRICTLY
    stronger than the same one in private (the new channels are relational, so they get exposure free)."""

    def res(pub):
        tr = _run("wojslaw", [_ev(0, typ, "player", 1.0, public=pub)], n=1)
        return (
            tr.ticks[0].state_after_commit.relations.get("player", {}).get(
                "resentment", 0.0
            )
        )

    assert res(True) > res(False)


# ============================ Part 5: persona contrast under one shared stream ============================

# A shared game-like stream: low-level complaint, a public insult, help, a command (from an
# authority), then a refusal. The SAME excitation drives every persona; only traits/relations differ.
STREAM = (
    ("complaint", "player", False),
    ("insult", "player", True),
    ("help", "player", False),
    ("command", "edda", False),
    ("refusal", "player", False),
)


def _stream_actions(persona):
    events = [
        _ev(i * 3, typ, src, 1.0, public) for i, (typ, src, public) in enumerate(STREAM)
    ]
    tr = _run(persona, events, n=len(STREAM) * 3 + 1)
    return [tr.ticks[i * 3].selection.action for i in range(len(STREAM))]


def test_5_personas_differ_under_same_stream():
    seqs = {
        p: tuple(_stream_actions(p))
        for p in ("halgrim", "wojslaw", "cichy", "lutek", "branic")
    }
    assert len(set(seqs.values())) > 1  # the exact action sequence is NOT identical for all


def test_5_stoic_suppresses_reactive_erupts():
    halgrim = _stream_actions("halgrim")  # high control / high stoicism
    wojslaw = _stream_actions("wojslaw")  # reactive / proud
    assert "outburst" not in halgrim  # the stoic suppresses into colder replies
    assert "outburst" in wojslaw  # the reactive persona erupts under the same pressure


@pytest.mark.parametrize("persona", ["halgrim", "wojslaw", "lutek"])
def test_5_help_yields_a_positive_reply(persona):
    """Pro-social help from a non-resented source warms into positive_response (Theme A), across
    very different personas -- the cooperative side of the contrast, not only the hostile side."""
    init = {"relations": {"player": {"trust": 0.5, "respect": 0.5, "resentment": 0.0}}}
    tr = _run(persona, [_ev(0, "help", "player", 1.0)], init, n=1)
    assert tr.ticks[0].selection.action == "positive_response"
