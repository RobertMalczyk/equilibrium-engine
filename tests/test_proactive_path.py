"""Proactive path (spec scenarios group B) -- property tests, not goldens.

D5 (the proactive boredom trigger fires from idle, WITH per-persona tempo) is implemented: a
novelty-seeker left idle eventually crosses theta_start and starts seek_stimulus, ordered by
novelty_seeking, while a low-novelty stoic does not seek at all. These tests assert:

  * the boredom drift edge is active -- idleness makes boredom rise monotonically FOR A NON-SEEKER
    (the M3b topology edge, cleanly: a seeker's boredom is relieved by seeking, so the monotonic-drift
    fact is checked on a stoic who does not seek);
  * D5 tempo: from the SAME pure idle, time-to-seek is ordered by novelty_seeking; fast-borers enter,
    low-novelty personas never do;
  * the FIXED proactive wiring works end-to-end when boredom is high: boredom -> urge_boredom ->
    seek_stimulus -> BUSY -> relief.

No golden is frozen for idle_watch: its full trace is placeholder-sensitive.
"""

from pathlib import Path

from engine.schema import RawEvent, Scenario
from engine.simulation import run_scenario
from engine.yaml_io import load_persona, load_scenario

ROOT = Path(__file__).resolve().parents[1]
DEFAULTS = ROOT / "calibration" / "defaults.yaml"


def _run(scenario_id: str, persona_id: str, n_ticks: int):
    cfg = load_persona(ROOT / "data" / "personas" / f"{persona_id}.yaml", DEFAULTS)
    sc = load_scenario(ROOT / "data" / "scenarios" / f"{scenario_id}.yaml")
    _, trace = run_scenario(cfg, sc, n_ticks=n_ticks)
    return trace


# Identical pure-idle fixture (zero events): isolates the boredom TEMPO by persona (only the trait differs).
_IDLE_INIT = {
    "global_state": {
        "boredom": 0.10,
        "fatigue": 0.20,
        "stress": 0.10,
        "anger": 0.0,
        "frustration": 0.0,
    }
}


def _time_to_seek(persona_id: str, n_ticks: int = 2000):
    cfg = load_persona(ROOT / "data" / "personas" / f"{persona_id}.yaml", DEFAULTS)
    sc = Scenario(
        id="idle", persona=persona_id, initial_overrides=_IDLE_INIT, events=()
    )
    _, trace = run_scenario(cfg, sc, n_ticks=n_ticks)
    return next(
        (tk.t for tk in trace.ticks if tk.selection.action == "seek_stimulus"), None
    )


def test_idle_boredom_accumulates():
    """The M3b boredom-drift edge: on an empty watch boredom rises monotonically (idleness bores).
    Checked on HALGRIM (low novelty_seeking -> does NOT seek from idle, so boredom drifts up cleanly;
    a fast-borer's boredom would be relieved by seeking -- see test_idle_seeking_tempo)."""
    trace = _run("idle_watch", "halgrim", 60)
    boredom = [tk.state_after_post.global_state["boredom"] for tk in trace.ticks]
    assert boredom[-1] > boredom[0]
    assert all(b2 >= b1 - 1e-9 for b1, b2 in zip(boredom, boredom[1:]))


def test_idle_recovery_settles_a_non_seeker(_replace=None):
    """D11 fix -- ambient idle homeostasis: a non-seeker (Halgrim, never seeks) left IDLE and unprovoked
    SETTLES. Property/contrast test (isolates the edge, no magic numbers): the SAME elevated-stress idle
    run has LOWER stress/anger WITH idle_recovery than with the edge removed. Non-seekers have no other
    intraday recovery path (they never engage a stress-relieving activity), so without this they sit
    chronically high and over-react to ordinary events."""
    import dataclasses

    cfg = load_persona(ROOT / "data" / "personas" / "halgrim.yaml", DEFAULTS)
    cfg_off = dataclasses.replace(cfg, idle_recovery={})  # same persona, edge removed
    init = {
        "global_state": {
            "stress": 0.60,
            "anger": 0.30,
            "boredom": 0.10,
            "fatigue": 0.20,
        }
    }
    sc = Scenario(id="idle", persona="halgrim", initial_overrides=init, events=())
    _, on = run_scenario(cfg, sc, n_ticks=80)
    _, off = run_scenario(cfg_off, sc, n_ticks=80)
    s_on = on.ticks[-1].state_after_post.global_state
    s_off = off.ticks[-1].state_after_post.global_state
    assert s_on["stress"] < s_off["stress"]  # recovery pulls stress down
    assert s_on["anger"] < s_off["anger"]  # ...and anger
    assert (
        s_on["stress"] < init["global_state"]["stress"]
    )  # net settling from the elevated start


def test_idle_recovery_is_weaker_for_a_reactive_persona():
    """D11 round-2 -- reactivity modulates idle recovery: a high-reactivity persona settles SLOWER (keeps
    its edge), a calm one recovers fully. Isolated by varying ONLY the reactivity trait on one persona
    (same everything else), so it tests the modulator, not persona differences. Both start equally stressed
    and idle; the reactive one ends with HIGHER stress (less recovered)."""
    import dataclasses

    base = load_persona(ROOT / "data" / "personas" / "halgrim.yaml", DEFAULTS)
    calm = dataclasses.replace(base, traits={**base.traits, "reactivity": 0.25})
    reactive = dataclasses.replace(base, traits={**base.traits, "reactivity": 0.90})
    init = {
        "global_state": {
            "stress": 0.60,
            "anger": 0.30,
            "boredom": 0.10,
            "fatigue": 0.20,
        }
    }
    sc = Scenario(id="idle", persona="halgrim", initial_overrides=init, events=())
    _, tr_calm = run_scenario(calm, sc, n_ticks=80)
    _, tr_react = run_scenario(reactive, sc, n_ticks=80)
    assert (
        tr_react.ticks[-1].state_after_post.global_state["stress"]
        > tr_calm.ticks[-1].state_after_post.global_state["stress"]
    )


def test_idle_recovery_floor_keeps_a_resentful_persona_tense():
    """D11 round-3 -- standing-grievance floor: idle stress recovery stops at idle_recovery_floor*resentment_max,
    so a persona carrying a deep resentment idles WARY (does not relax to calm) between events. Isolated by
    varying ONLY a relation's resentment on one persona; the resentful copy ends with HIGHER idle stress."""
    import dataclasses

    base = load_persona(ROOT / "data" / "personas" / "halgrim.yaml", DEFAULTS)
    resentful = dataclasses.replace(
        base,
        initial_relations={
            **base.initial_relations,
            "captor": {"trust": 0.1, "respect": 0.1, "resentment": 0.85},
        },
    )
    calm = dataclasses.replace(
        base,
        initial_relations={
            **base.initial_relations,
            "captor": {"trust": 0.5, "respect": 0.5, "resentment": 0.0},
        },
    )
    init = {
        "global_state": {
            "stress": 0.60,
            "anger": 0.10,
            "boredom": 0.10,
            "fatigue": 0.20,
        }
    }
    sc = Scenario(id="idle", persona="halgrim", initial_overrides=init, events=())
    _, tr_res = run_scenario(resentful, sc, n_ticks=120)
    _, tr_calm = run_scenario(calm, sc, n_ticks=120)
    s_res = tr_res.ticks[-1].state_after_post.global_state["stress"]
    s_calm = tr_calm.ticks[-1].state_after_post.global_state["stress"]
    assert (
        s_res > s_calm + 0.10
    )  # the grievance holds a tense floor; the calm copy settles low
    assert s_res > 0.30  # he idles "tense", not "at ease"


def test_idle_recovery_does_not_fire_when_provoked():
    """The recovery is gated on UNPROVOKED: an insult within the reactive window keeps the persona out of
    recovery (so a provoked persona does NOT magically calm mid-confrontation -- and the burst litmus,
    provoked throughout, is untouched)."""
    import dataclasses

    cfg = load_persona(ROOT / "data" / "personas" / "halgrim.yaml", DEFAULTS)
    cfg_off = dataclasses.replace(cfg, idle_recovery={})
    init = {"global_state": {"stress": 0.40, "anger": 0.20}}
    # an insult at t=0, then idle within the reactive window (10 ticks): recovery must stay OFF -> identical.
    sc = Scenario(
        id="provoked",
        persona="halgrim",
        initial_overrides=init,
        events=(RawEvent(type="insult", t=0, source="wojslaw", intensity=0.8),),
    )
    _, on = run_scenario(cfg, sc, n_ticks=8)
    _, off = run_scenario(cfg_off, sc, n_ticks=8)
    assert (
        on.ticks[-1].state_after_post.global_state["stress"]
        == off.ticks[-1].state_after_post.global_state["stress"]
    )


def test_idle_seeking_tempo():
    """D5: from the SAME pure idle, the proactive seek fires ordered by novelty_seeking -- fast-borers
    enter, low-novelty stoics never do. Asserts the ORDERING/floor/guard, not specific ticks (Rule 1)."""
    lutek = _time_to_seek("lutek")  # novelty 0.97
    branic = _time_to_seek("branic")  # novelty 0.90
    halgrim = _time_to_seek("halgrim")  # novelty 0.25
    edda = _time_to_seek("edda")  # novelty 0.25
    # fast-borers enter; stoics never (the guard against a flattened, fire-for-everyone fix)
    assert lutek is not None and branic is not None
    assert halgrim is None and edda is None
    # tempo ordered by novelty (Lutek bores faster than Branic), from an identical start
    assert lutek < branic


def test_proactive_path_closed_loop():
    """M7 Step 2 closed loop: high boredom -> SEEKING (seek_stimulus, the looking), then the WORLD CONFIRMS
    an `activity` -> BUSY engaged -> boredom relieved + satisfaction up. Boredom high via overrides (DATA);
    the activity confirmation is the world's reply (here scripted; the mock-world supplies it for real)."""
    cfg = load_persona(ROOT / "data" / "personas" / "welf.yaml", DEFAULTS)
    sc = Scenario(
        id="primed",
        persona="welf",
        initial_overrides={"global_state": {"boredom": 0.95, "fatigue": 0.10}},
        events=(
            RawEvent(
                type="activity", t=2, context={"kind": "self_activity", "novelty": 1.0}
            ),
        ),
    )
    _, trace = run_scenario(cfg, sc, n_ticks=10)
    actions = [tk.selection.action for tk in trace.ticks]
    modes = [tk.state_after_post.mode.value for tk in trace.ticks]

    assert (
        trace.ticks[0].selection.action == "seek_stimulus"
    )  # SEEKING at high boredom (the intent)
    assert "SEEKING" in modes
    assert "self_activity" in actions  # ...engages once the world confirms
    assert "BUSY" in modes

    g0 = trace.ticks[0].snapshot.global_state
    gN = trace.ticks[-1].state_after_post.global_state
    assert gN["boredom"] < g0["boredom"]  # the ENGAGED activity relieves boredom
    assert gN["satisfaction"] > g0["satisfaction"]  # ...and is rewarding


def test_seeking_times_out_and_costs_frustration():
    """M7 Step 2: SEEKING with NO `activity` confirmation -> frustration accrues, then give-up at the
    timeout. (The 'looks but finds nothing' arc.) No relief without a confirmation."""
    cfg = load_persona(ROOT / "data" / "personas" / "welf.yaml", DEFAULTS)
    sc = Scenario(
        id="nofind",
        persona="welf",
        initial_overrides={
            "global_state": {"boredom": 0.95, "fatigue": 0.10, "frustration": 0.0}
        },
        events=(),
    )
    _, trace = run_scenario(cfg, sc, n_ticks=40)
    modes = [tk.state_after_post.mode.value for tk in trace.ticks]
    assert "SEEKING" in modes  # it looks
    assert "self_activity" not in [
        tk.selection.action for tk in trace.ticks
    ]  # never engages (no confirm)
    # seeking costs frustration: it is higher after a stretch of fruitless looking than at the start.
    assert (
        trace.ticks[-1].state_after_post.global_state["frustration"]
        > trace.ticks[0].snapshot.global_state["frustration"]
    )


# ================= Obedience priority over venting (D11 Branic, signed/inhibitory edge) =================
# A respected commander's order INHIBITS outburst (command_x_respect_src read with a NEGATIVE weight), so
# obedience is robust to ambient/residual anger. Contrast tests toggle the edge (param_overrides -> 0.0) to
# isolate it; litmus-safety is asserted by showing the no-command burst + the low-respect refuse are untouched.

_NO_EDGE = {
    "potential_weights": {"outburst": {"command_x_respect_src": 0.0}}
}  # edge removed (neutral)


def test_obedience_priority_suppresses_residual_anger_outburst():
    """D11 Branic: a recruit carrying RESIDUAL anger receives an order from a RESPECTED commander (Halgrim).
    WITH the inhibitory edge he OBEYS (cooperate); with the edge removed the same residual anger makes
    outburst out-argmax cooperate -> he SNAPS. The flip is caused by the edge alone (same persona, same
    scenario, only the one weight differs) -- so 'obeyed one tick, snapped the next' becomes 'obeys'."""
    on = load_persona(ROOT / "data" / "personas" / "branic.yaml", DEFAULTS)
    off = load_persona(
        ROOT / "data" / "personas" / "branic.yaml", DEFAULTS, param_overrides=_NO_EDGE
    )
    sc = load_scenario(ROOT / "data" / "scenarios" / "branic_command_while_angry.yaml")
    tk_on = run_scenario(on, sc, n_ticks=1)[1].ticks[0]
    tk_off = run_scenario(off, sc, n_ticks=1)[1].ticks[0]
    assert (
        tk_off.selection.action == "outburst"
    )  # without the edge: residual anger vents on the order
    assert (
        tk_on.selection.action == "cooperate"
    )  # with the edge: a respected order is obeyed regardless
    assert (
        tk_on.potentials["outburst"] < tk_off.potentials["outburst"]
    )  # the edge lowers the venting potential
    assert (
        tk_on.potentials["cooperate"] == tk_off.potentials["cooperate"]
    )  # ...and touches nothing else


def test_obedience_inhibition_is_neutral_without_a_command():
    """Litmus-safety (no command): command_pressure==0 -> the edge is 0, so the burst litmus is bit-identical
    with or without it. Wojslaw still bursts at the soup (no order in play -> obedience priority cannot apply)."""
    on = load_persona(ROOT / "data" / "personas" / "wojslaw.yaml", DEFAULTS)
    off = load_persona(
        ROOT / "data" / "personas" / "wojslaw.yaml", DEFAULTS, param_overrides=_NO_EDGE
    )
    sc = load_scenario(ROOT / "data" / "scenarios" / "same_soup_bad_day.yaml")
    acts_on = [tk.selection.action for tk in run_scenario(on, sc)[1].ticks]
    acts_off = [tk.selection.action for tk in run_scenario(off, sc)[1].ticks]
    assert acts_on == acts_off  # no command -> edge inert -> identical trace
    assert "outburst" in acts_on


def test_obedience_inhibition_preserves_low_respect_refuse():
    """Litmus-safety (low respect): the edge scales WITH respect[src], so a resented/low-respect commander
    is barely damped and the refuse litmus stands. Halgrim still refuses Wojslaw's order with the edge on."""
    on = load_persona(ROOT / "data" / "personas" / "halgrim.yaml", DEFAULTS)
    off = load_persona(
        ROOT / "data" / "personas" / "halgrim.yaml", DEFAULTS, param_overrides=_NO_EDGE
    )
    sc = load_scenario(ROOT / "data" / "scenarios" / "command_from_wojslaw.yaml")
    tk_on = run_scenario(on, sc, n_ticks=4)[1].ticks[0]
    tk_off = run_scenario(off, sc, n_ticks=4)[1].ticks[0]
    assert tk_on.selection.action == "refuse" == tk_off.selection.action
