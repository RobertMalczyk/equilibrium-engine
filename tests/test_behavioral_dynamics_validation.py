"""Generic behavioral-dynamics VALIDATION (characterization) -- not tuning, not a game feature.

These tests verify that the engine's GENERIC single-agent dynamics are plausible and well-behaved,
independent of any game/world/scenario:

  Part 1 -- the homeostatic core:
    A. idle under-stimulation -> boredom rises, bounded, deterministic, no spurious outburst
    B. higher boredom -> higher activity-seeking tendency (urge / seek_stimulus)
    C. an engaged activity -> fatigue rises (vs idle) while boredom/stress do NOT climb like pure idle
    D. higher fatigue -> higher rest tendency (urge / rest action)
    E. a night/rest mechanism recovers the FAST states while SLOW relational memory persists

  Part 2 -- generic social inputs (sources are opaque ids: source_a, source_b, observer, actor):
    F. social effects stay SOURCE-SPECIFIC (A's hostility is not attributed to B)
    G. the negative social event types are DISTINCT (not aliases) and ordered by severity

Assertions are DIRECTIONAL (orderings, set differences, sign, boundedness), never hand-picked
magnitudes (project persona-contrast / no-magic-number style). No engine code, no event->action
scripting, no world model, no LLM. Runs on the calibrated eval persona path. Observability summaries
come from eval.observe (read-only; they change no runtime behavior).
"""

from __future__ import annotations

import pytest

from engine.schema import RawEvent, Scenario
from engine.simulation import run_scenario
from eval import observe
from eval.calibrated import load_eval_persona
from eval.night_runner import DAY_LEN, _insults, day_summaries, run_nights

# Generic, world-agnostic source ids -- opaque relation keys, NOT players/NPCs/rooms.
SOURCE_A = "source_a"
SOURCE_B = "source_b"
OBSERVER = "observer"
ACTOR = "actor"

NEG = ("insult", "cold_reply", "refusal", "complaint")


def _ev(t, typ, src=None, intensity=1.0, public=False):
    return RawEvent(
        type=typ,
        t=t,
        source=src,
        intensity=intensity,
        context={"public": public} if public else {},
    )


def _run(persona, events=(), init=None, n=None, burst=False):
    cfg = load_eval_persona(persona, burst=burst)
    sc = Scenario(
        id="validate",
        persona=persona,
        initial_overrides=init or {},
        events=tuple(events),
    )
    return run_scenario(cfg, sc, n)[1]


# ===================================================================================================
# Part 1 -- the homeostatic core
# ===================================================================================================


# ---- Test A: idle under-stimulation increases boredom -------------------------------------------
def test_A_idle_increases_boredom_bounded_deterministic():
    """A non-seeker (halgrim, low novelty_seeking -> never engages an activity) left on an empty idle
    stream: boredom rises and never steps down, the whole state stays in [0,1], the trace is bit-identical
    across two runs, and NO outburst fires on a neutral idle stream (no provocation -> nothing to vent)."""
    init = {
        "global_state": {"boredom": 0.10, "fatigue": 0.20, "stress": 0.10, "anger": 0.0}
    }
    a = _run("halgrim", (), init, n=120)
    b = _run("halgrim", (), init, n=120)

    boredom = observe.trajectory(a, "boredom")
    assert boredom[-1] > boredom[0]  # idleness bores (the M3b boredom-drift edge)
    assert observe.is_nondecreasing(
        boredom
    )  # ...monotonically, for a non-seeker (no relief path)
    assert observe.is_bounded(a)  # all states & relations stay within [0, 1]
    assert observe.is_deterministic(a, b)  # bit-identical across executions
    assert "outburst" not in observe.action_counts(a)  # neutral idle never erupts


def test_A_idle_does_not_inflate_anger():
    """Corollary: on a neutral idle stream anger does not climb out of nothing (no phantom provocation)."""
    init = {"global_state": {"anger": 0.0, "stress": 0.10, "boredom": 0.10}}
    tr = _run("halgrim", (), init, n=120)
    anger = observe.state_summary(tr, "anger")
    assert anger["max"] < 0.20  # stays near its floor; idleness is not a provocation


# ---- Test B: boredom increases activity-seeking tendency ----------------------------------------
def test_B_higher_boredom_raises_seeking_tendency():
    """A novelty-seeker (welf): with boredom HIGH the activity-seeking urge is greater than with boredom
    low, and the proactive `seek_stimulus` action fires when high but not at the low baseline. Compares
    DIRECTION/ordering at t=0 (same persona, only the boredom override differs), not specific values."""
    low = {"global_state": {"boredom": 0.05, "fatigue": 0.10, "stress": 0.10}}
    high = {"global_state": {"boredom": 0.95, "fatigue": 0.10, "stress": 0.10}}
    tr_low = _run("welf", (), low, n=1)
    tr_high = _run("welf", (), high, n=1)

    urge_low = tr_low.ticks[0].urges["boredom"]
    urge_high = tr_high.ticks[0].urges["boredom"]
    assert urge_high > urge_low  # more boredom -> more activity-seeking drive

    assert (
        tr_high.ticks[0].selection.action == "seek_stimulus"
    )  # the drive crosses into seeking
    assert (
        tr_low.ticks[0].selection.action != "seek_stimulus"
    )  # ...the low baseline does not seek


def test_B_seeking_tempo_ordered_by_novelty():
    """The activity-seeking onset is a trait-modulated property of the SAME idle excitation: a faster-boring
    persona starts seeking sooner than a slower one, and a low-novelty stoic never seeks at all. Ordering
    only (no specific ticks)."""
    init = {"global_state": {"boredom": 0.10, "fatigue": 0.20, "stress": 0.10}}

    def time_to_seek(persona):
        tr = _run(persona, (), init, n=2000)
        return observe.first_tick_with_action(tr, "seek_stimulus")

    lutek = time_to_seek("lutek")  # high novelty_seeking
    branic = time_to_seek("branic")  # medium
    halgrim = time_to_seek("halgrim")  # low -> never
    assert lutek is not None and branic is not None
    assert halgrim is None
    assert lutek < branic


# ---- Test C: activity raises fatigue (and does not bore/stress like pure idle) -------------------
def test_C_engaged_activity_raises_fatigue_more_than_idle():
    """Drive the proactive loop to an ENGAGED activity (high boredom -> seek_stimulus -> SEEKING; a world
    `activity` confirmation -> BUSY). Against an idle baseline of equal length from the same start: an
    engaged self_activity TIRES the agent (fatigue rises more than idle) while it RELIEVES boredom and
    does not raise stress the way fruitless idle does. State stays bounded throughout."""
    init = {"global_state": {"boredom": 0.95, "fatigue": 0.10, "stress": 0.30}}
    activity = RawEvent(
        type="activity", t=2, context={"kind": "self_activity", "novelty": 1.0}
    )
    busy = _run("welf", (activity,), init, n=12)
    idle = _run("welf", (), init, n=12)

    assert "BUSY" in observe.mode_timeline(
        busy
    )  # the activity engaged (world confirmed)
    assert observe.is_bounded(busy)

    f_busy = observe.state_summary(busy, "fatigue")["net"]
    f_idle = observe.state_summary(idle, "fatigue")["net"]
    assert f_busy > f_idle  # engaging tires more than sitting idle

    # the engaged activity RELIEVES boredom; pure idle (seeker stuck SEEKING) does not get that relief:
    assert (
        observe.state_summary(busy, "boredom")["last"]
        < observe.state_summary(idle, "boredom")["last"]
    )
    # ...and self_activity recovers stress rather than letting it sit/climb like fruitless idle:
    assert (
        observe.state_summary(busy, "stress")["last"]
        < observe.state_summary(idle, "stress")["last"]
    )


# ---- Test D: fatigue increases rest tendency ----------------------------------------------------
def test_D_higher_fatigue_raises_rest_tendency():
    """Same persona, only the fatigue override differs: HIGH fatigue yields a greater rest urge than LOW,
    and the proactive `rest` action fires when tired but not at the rested baseline. Ordering + action
    presence (potential/urge ordering, not a brittle exact magnitude)."""
    low = {"global_state": {"fatigue": 0.05, "boredom": 0.10, "stress": 0.10}}
    high = {"global_state": {"fatigue": 0.95, "boredom": 0.10, "stress": 0.10}}
    tr_low = _run("halgrim", (), low, n=1)
    tr_high = _run("halgrim", (), high, n=8)

    assert tr_high.ticks[0].urges["fatigue"] > tr_low.ticks[0].urges["fatigue"]
    assert "rest" in observe.action_counts(tr_high)  # a tired agent takes a rest
    assert "rest" not in observe.action_counts(tr_low)  # a rested one does not


def test_D_rest_discharges_fatigue():
    """The rest break actually serves the need: once `rest` engages, fatigue falls from its high start."""
    high = {"global_state": {"fatigue": 0.95, "boredom": 0.10, "stress": 0.10}}
    tr = _run("halgrim", (), high, n=20)
    assert "rest" in observe.action_counts(tr)
    fat = observe.state_summary(tr, "fatigue")
    assert fat["last"] < fat["first"]  # rest pulls fatigue back down
    assert observe.is_bounded(tr)


# ---- Test E: night/rest recovery resets fast states, keeps slow memory --------------------------
def test_E_night_recovers_fast_states_keeps_relational_memory():
    """Raise the FAST states and build a relational grudge during the day, then let the supported night/
    sleep mechanism run: across the night the fast states (anger) bottom out (recovery) while the SLOW
    relational memory (resentment toward the actual source) survives to the next dawn. Deterministic."""
    src = SOURCE_A
    _, tr = run_nights(
        "halgrim",
        days=2,
        day_events=lambda d: _insults(src, 2)(d) if d == 0 else [],
        initial={"global_state": {"fatigue": 0.5, "anger": 0.4, "stress": 0.5}},
    )
    days = day_summaries(tr, 2)
    assert all(d["slept"] for d in days)  # the night/sleep mechanism engages
    for d in days:
        assert d["min_anger"] < 0.20  # fast state (anger) recovers overnight
        assert d["min_anger"] < d["peak_anger"]

    res_dusk = (
        tr.ticks[DAY_LEN - 1]
        .state_after_post.relations.get(src, {})
        .get("resentment", 0.0)
    )
    res_dawn = (
        tr.ticks[DAY_LEN].state_after_post.relations.get(src, {}).get("resentment", 0.0)
    )
    assert res_dusk > 0.05  # a grudge formed from the day's events
    assert (
        abs(res_dawn - res_dusk) < 0.02
    )  # ...and the SLOW memory is NOT erased by the night

    # determinism: a second identical run is bit-identical
    _, tr2 = run_nights(
        "halgrim",
        days=2,
        day_events=lambda d: _insults(src, 2)(d) if d == 0 else [],
        initial={"global_state": {"fatigue": 0.5, "anger": 0.4, "stress": 0.5}},
    )
    assert observe.is_deterministic(tr, tr2)


# ===================================================================================================
# Part 2 -- generic social inputs (opaque sources)
# ===================================================================================================


# ---- Test F: social effects are source-specific -------------------------------------------------
def test_F_negative_pressure_stays_with_its_source():
    """source_a emits a negative social event; source_b emits a positive one. The negative pressure
    creates/raises resentment toward source_a ONLY -- it is NOT blindly attributed to source_b, and each
    addressed source gets its own consistently-updated relation row."""
    # one event per source on separate ticks keeps each clean; run a few ticks so both rows settle.
    tr = _run(
        "wojslaw", [_ev(0, "insult", SOURCE_A, 1.0), _ev(2, "help", SOURCE_B, 1.0)], n=4
    )
    last = tr.ticks[-1].state_after_post

    assert SOURCE_A in last.relations and SOURCE_B in last.relations  # both rows exist
    res_a = last.relations[SOURCE_A].get("resentment", 0.0)
    res_b = last.relations[SOURCE_B].get("resentment", 0.0)
    assert res_a > 0.0  # the insult's grudge lands on source_a
    assert (
        res_b <= 1e-9
    )  # ...and is NOT attributed to source_b (source-specific filter)
    assert res_a > res_b


def test_F_two_hostile_sources_accrue_independently():
    """Two distinct hostile sources accrue their OWN grudges; resenting A does not bleed into B's row."""
    tr = _run(
        "wojslaw",
        [_ev(0, "insult", SOURCE_A, 1.0), _ev(2, "cold_reply", OBSERVER, 1.0)],
        n=4,
    )
    rel = tr.ticks[-1].state_after_post.relations
    assert rel.get(SOURCE_A, {}).get("resentment", 0.0) > rel.get(OBSERVER, {}).get(
        "resentment", 0.0
    )
    # the milder cold_reply from `observer` still registers as its own (nonzero) row, not folded into A:
    assert rel.get(OBSERVER, {}).get("resentment", 0.0) > 0.0


# ---- Test G: negative social events are distinct, ordered by severity ---------------------------
def _state1(persona, typ, init, src=ACTOR):
    tr = _run(persona, [_ev(0, typ, src, 1.0)], init, n=1)
    return tr.ticks[0].state_after_commit.global_state


def test_G_insult_is_the_strongest_anger():
    init = {"global_state": {"anger": 0.0, "frustration": 0.0, "stress": 0.0}}
    anger = {t: _state1("wojslaw", t, init)["anger"] for t in NEG}
    for t in ("cold_reply", "refusal", "complaint"):
        assert anger["insult"] > anger[t], f"insult anger should exceed {t}"


def test_G_cold_reply_is_the_mildest():
    init = {"global_state": {"anger": 0.0, "frustration": 0.0, "stress": 0.0}}
    g = {t: _state1("wojslaw", t, init) for t in NEG}
    for t in ("insult", "refusal", "complaint"):
        assert g["cold_reply"]["anger"] < g[t]["anger"], (
            f"cold_reply should be milder than {t}"
        )


def test_G_negative_events_are_distinct_not_aliases():
    """The four negative event types produce pairwise-distinct global-state footprints at equal intensity
    & source -- none is a silent alias of another (a stronger check than 'each differs from insult')."""
    init = {"global_state": {"anger": 0.2, "frustration": 0.2, "stress": 0.1}}
    footprints = {
        t: tuple(round(v, 9) for v in _state1("wojslaw", t, init).values()) for t in NEG
    }
    assert len(set(footprints.values())) == 4, (
        "negative events are not all distinguishable"
    )


@pytest.mark.parametrize("typ", NEG)
def test_G_negative_events_stay_bounded(typ):
    """Each negative event, even repeated, keeps the state bounded (the clamp holds) -- a generic
    well-behavedness check across all four types."""
    tr = _run("wojslaw", [_ev(t, typ, SOURCE_A, 1.0) for t in range(0, 30, 3)], n=30)
    assert observe.is_bounded(tr)
