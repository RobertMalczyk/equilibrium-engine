"""Target policy (the THIRD inhibitory edge): a respected BYSTANDER does not catch displaced anger.

With one global `anger` pool, residual anger from provoker X could vent onto a different source Y who merely
interacts next (the `halgrim_068` flag: cold contempt at respected Edda while the anger is really Wojsław's).
The `bystander_x_respect_src` edge damps venting at a respected non-provoker. Neutral by construction.
"""

from __future__ import annotations

from engine.schema import RawEvent, Scenario
from engine.simulation import run_scenario
from eval.calibrated import load_eval_persona

HOT = {"global_state": {"anger": 0.3, "frustration": 0.3}}  # already carrying some heat


def _run(events, overrides=HOT, n=8, persona="halgrim"):
    sc = Scenario(
        id="tp", persona=persona, initial_overrides=overrides, events=tuple(events)
    )
    return run_scenario(load_eval_persona(persona), sc, n)[1]


def _act(tr, t):
    return tr.ticks[t].selection.action


def test_respected_bystander_is_spared_spillover():
    """Wojsław provokes, then RESPECTED Edda gives a routine order within the window: Halgrim must NOT answer
    Edda with cold contempt / outburst (displaced Wojsław-anger) -- the respected order wins -> cooperate."""
    tr = _run(
        [
            RawEvent(
                type="insult",
                t=0,
                source="wojslaw",
                intensity=1.0,
                context={"public": True},
            ),
            RawEvent(type="command", t=2, source="edda", intensity=1.0, context={}),
        ]
    )
    assert _act(tr, 0) == "cold_response"  # he IS cold to the actual provoker, Wojsław
    assert _act(tr, 2) not in ("cold_response", "outburst")  # but not to respected Edda
    assert _act(tr, 2) == "cooperate"  # the obedience response wins instead


def test_provoker_themselves_still_caught():
    """Same source provokes then orders: he is NOT a bystander (he caused the anger) -> the reaction stands."""
    tr = _run(
        [
            RawEvent(
                type="insult",
                t=0,
                source="wojslaw",
                intensity=1.0,
                context={"public": True},
            ),
            RawEvent(type="command", t=2, source="wojslaw", intensity=1.0, context={}),
        ]
    )
    assert _act(tr, 2) in (
        "cold_response",
        "outburst",
        "refuse",
    )  # still reacts to Wojsław himself


def test_no_residual_anger_is_bit_identical():
    """A command from Edda with NO prior provocation (no residual anger) -> bystander gate is 0, behaviour is
    exactly the obedience case (cooperate). The fix only bites when a SECOND source interacts amid lingering
    anger from a FIRST."""
    calm = {"global_state": {}}
    tr = _run(
        [RawEvent(type="command", t=2, source="edda", intensity=1.0, context={})],
        overrides=calm,
    )
    assert _act(tr, 2) == "cooperate"


def test_bystander_sparing_scales_with_respect():
    """A respected bystander (Edda) is spared MORE than a low-respect one. Same residual anger, same routine
    command: Edda -> cooperate/neutral (spared); a low-respect source's order is NOT fully spared."""
    base = [
        RawEvent(
            type="insult",
            t=0,
            source="wojslaw",
            intensity=1.0,
            context={"public": True},
        )
    ]
    edda = _run(
        base + [RawEvent(type="command", t=2, source="edda", intensity=1.0, context={})]
    )
    # player has lower respect than edda for halgrim -> less sparing -> the cold reaction is not suppressed away
    player = _run(
        base
        + [RawEvent(type="command", t=2, source="player", intensity=1.0, context={})]
    )
    assert (
        edda.ticks[2].potentials["cold_response"]
        < player.ticks[2].potentials["cold_response"]
    )
