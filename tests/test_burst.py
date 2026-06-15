"""Burst & saturation (spec section 8 burst) — acceptance-gate tests G0–G5.

G0 (ship inert) is the rest of the suite: all new config defaults are neutral/absent, so every
golden/litmus is bit-identical. Here: the escalation math (G2), the latch's loop-plateau
discrimination (G4), boundedness/return (G3), the displaced-discharge gate extension + transient
relational booking (G5), trace sparsity, and determinism. Loop-2 edge tests live with the eval
scenarios (rich vs barren world needs the mock-world runner).

Test values (thresholds, k_esc, extinction rates) are AUTHORED test fixtures, not engine literals.
"""

import pytest

from engine import update
from engine.runtime import init_runtime
from engine.schema import RawEvent, Scenario
from engine.simulation import run_scenario
from engine.yaml_io import load_persona

PERSONA = "data/personas/wojslaw.yaml"
DEFAULTS = "calibration/defaults.yaml"


def _load(overrides=None):
    return load_persona(PERSONA, DEFAULTS, param_overrides=overrides)


def _scenario(events, initial=None, sid="burst_test"):
    return Scenario(
        id=sid,
        persona="wojslaw",
        initial_overrides=initial or {},
        events=tuple(events),
    )


# Latch-enabled fixture: both loop states start pinned in the saturation band; the latch arms after
# burst_confirm_ticks; extinction then relaxes the loop; theta_displace sits under the initial anger.
BURST_THRESHOLDS = {
    "burst_enter.anger": 0.80,
    "burst_enter.stress": 0.60,
    "burst_exit": 0.30,
    "burst_confirm_ticks": 2,
    "theta_displace": 0.55,
    "reactive_window_ticks": 1,  # close the ordinary gate fast so the DISPLACED gate is isolated
}
HOT_START = {"global_state": {"anger": 0.95, "stress": 0.90}}


def _burst_cfg(extra=None, extinction=None, appraisal=None):
    ov = {
        "thresholds": dict(BURST_THRESHOLDS, **(extra or {})),
        "burst_extinction": extinction if extinction is not None else {},
    }
    if appraisal is not None:
        ov["appraisal"] = appraisal
    return _load(ov)


# --- G2: the escalation nonlinearity g_eff = g*(1 + k_esc*y) ---------------------------------------


def test_escalation_zero_is_exactly_linear():
    cfg_lin = _load()
    cfg_esc0 = _load({"coupling_escalation": {"anger": {"stress": 0.0}}})
    rt = init_runtime(cfg_lin, HOT_START)
    snap = rt.freeze()
    d_lin = update.compute(snap, {}, cfg_lin, None)
    d_esc0 = update.compute(snap, {}, cfg_esc0, None)
    assert (
        d_lin.global_ == d_esc0.global_
    )  # k_esc=0 reproduces the frozen linear loop EXACTLY


def test_escalation_adds_the_quadratic_term_exactly():
    k = 2.0
    cfg_lin = _load()
    cfg_esc = _load({"coupling_escalation": {"anger": {"stress": k}}})
    rt = init_runtime(cfg_lin, HOT_START)
    snap = rt.freeze()
    stress = snap.global_state["stress"]
    g = cfg_lin.couplings["anger"]["stress"]
    d_lin = update.compute(snap, {}, cfg_lin, None)
    d_esc = update.compute(snap, {}, cfg_esc, None)
    # the escalated edge contributes g*(1+k*y)*y = g*y + g*k*y^2: the difference is exactly g*k*y^2
    assert d_esc.global_["anger"] - d_lin.global_["anger"] == pytest.approx(
        g * k * stress * stress, rel=1e-12
    )
    # and at y=0 the term vanishes (anchored at the origin: the frozen calibration is untouched)
    rt0 = init_runtime(cfg_lin, {"global_state": {"anger": 0.5, "stress": 0.0}})
    snap0 = rt0.freeze()
    assert (
        update.compute(snap0, {}, cfg_esc, None).global_["anger"]
        == update.compute(snap0, {}, cfg_lin, None).global_["anger"]
    )


def test_escalation_of_undeclared_edge_is_a_config_error():
    with pytest.raises(ValueError, match="no such edge"):
        _load({"coupling_escalation": {"anger": {"hunger": 1.0}}})


# --- G4: latch discrimination — the LOOP plateau arms it, a single-state spike does not ------------


def test_latch_arms_on_loop_plateau_after_confirm_ticks():
    cfg = _burst_cfg()
    _, tr = run_scenario(cfg, _scenario([], initial=HOT_START), n_ticks=4)
    # both loop states in the band from t0; confirm=2 -> not latched at the end of t0, latched at t1
    assert tr.ticks[0].burst_latched is False
    assert tr.ticks[1].burst_latched is True


def test_single_state_spike_does_not_arm_the_latch():
    cfg = _burst_cfg()
    spike = {
        "global_state": {"anger": 0.95, "stress": 0.10}
    }  # anger spikes, the LOOP is not pinned
    _, tr = run_scenario(cfg, _scenario([], initial=spike), n_ticks=6)
    assert all(not tk.burst_latched for tk in tr.ticks)


def test_latch_disabled_when_thresholds_absent():
    cfg = _load()  # shipped defaults: no burst thresholds
    _, tr = run_scenario(cfg, _scenario([], initial=HOT_START), n_ticks=4)
    assert all(not tk.burst_latched for tk in tr.ticks)
    # ...and the trace dict stays SPARSE: no burst key at all in a non-bursting run
    assert all("burst_latched" not in tk.to_dict() for tk in tr.ticks)


# --- G3: boundedness/return — the episode extinguishes and the latch releases ----------------------


def test_extinction_brings_the_trajectory_back_and_releases_the_latch():
    cfg = _burst_cfg(extinction={"anger": 0.15, "stress": 0.15})
    n = 60
    _, tr = run_scenario(cfg, _scenario([], initial=HOT_START), n_ticks=n)
    assert tr.ticks[1].burst_latched is True  # the episode begins...
    released = [t for t in range(n) if not tr.ticks[t].burst_latched and t > 1]
    assert released, "the latch never released: extinction failed to dominate"
    t_rel = released[0]
    exit_th = BURST_THRESHOLDS["burst_exit"]
    # the latch resets in the same tick whose end-of-tick anger crossed the exit hysteresis
    assert tr.ticks[t_rel].state_after_post.global_state["anger"] <= exit_th
    # ...and STAYS down: no re-ignition without a fresh drive
    assert all(not tr.ticks[t].burst_latched for t in range(t_rel, n))
    final = tr.ticks[n - 1].state_after_post.global_state["anger"]
    assert final < exit_th


# --- G5: displaced discharge — the gate extension + the transient relational booking ---------------


def _displacement_run(theta_displace_on=True, n_ticks=8, discount=None):
    """The LOADED SPRING: the persona starts pinned hot with NO provocation, so the ordinary reactive
    gate stays SHUT (nothing to reply to) and nothing discharges the anger — the latch arms at t1.
    (A free-to-vent character outbursts and discharges −0.30 anger per reply, so it never plateaus;
    the burst is precisely the blocked-discharge mode, per the wojsław/Marta measurement.)
    t5: kind Marta brings food — NOT a provocation, NOT appraised kindness (gesture_channels emptied
    so the kindness gate stays shut and the DISPLACED gate is isolated)."""
    extra = {} if theta_displace_on else {"theta_displace": 2.0}  # unreachable
    appraisal = {"gesture_channels": [], "kindness_pressure": 0.0}
    if discount is not None:
        appraisal["displaced_relational_discount"] = discount
    cfg = _burst_cfg(
        extra=extra,
        extinction={"anger": 0.02, "stress": 0.02},
        appraisal=appraisal,
    )
    events = [
        RawEvent(
            t=5, type="food_given", source="marta", item="warm_meal", intensity=0.8
        ),
    ]
    _, tr = run_scenario(cfg, _scenario(events, initial=HOT_START), n_ticks=n_ticks)
    return tr


def test_displaced_discharge_fires_on_a_kind_bystander():
    tr = _displacement_run(theta_displace_on=True)
    tk = tr.ticks[5]
    assert tk.burst_latched is True  # still in the episode when Marta arrives
    assert (
        tk.selection.kind.value == "reactive"
    )  # the gate extension admitted the sourced event
    assert (
        "[DISPLACED" in tk.selection.explanation
    )  # rendered AS displacement, by contract


def test_no_displacement_below_the_bar():
    tr = _displacement_run(theta_displace_on=False)
    tk = tr.ticks[5]
    # gate shut: the kind event from a non-resented source draws no reply at all here
    assert tk.selection.kind.value != "reactive"


def test_displaced_discharge_books_no_durable_grudge():
    # Marta carries a SEEDED initial relation in wojsław's persona (resentment ~0.2), so the contract
    # is measured as the DELTA across the discharge tick: with the default discount (0.0) the displaced
    # outburst adds NOTHING durable to her resentment (the trace shows only the slow relational decay).
    def jump(tr):
        def res(t):
            return (
                tr.ticks[t]
                .state_after_post.relations.get("marta", {})
                .get("resentment", 0.0)
            )

        return res(5) - res(4)

    tr = _displacement_run(theta_displace_on=True)
    assert tr.ticks[5].selection.action == "outburst"  # the discharge really happened
    assert jump(tr) <= 0.0  # ...and booked no grudge (decay only)
    # CONTROL: with the discount lifted (1.0 = undiscounted), the SAME displaced discharge books the
    # full outburst resentment on Marta — proving the discount is what excludes the runaway, not luck
    tr_full = _displacement_run(theta_displace_on=True, discount=1.0)
    booked = float(
        tr_full.ticks[5]
        .selection.post_effects.relations.get("marta", {})
        .get("resentment", 0.0)
    )
    assert booked > 0.05  # the undiscounted booking is the configured outburst cost
    assert jump(tr_full) > 0.05  # and it lands as a durable grudge step


def test_sourceless_weather_never_catches_the_burst():
    cfg = _burst_cfg(appraisal={"gesture_channels": [], "kindness_pressure": 0.0})
    events = [
        RawEvent(t=5, type="weather", intensity=1.0)
    ]  # no source: you cannot kick the rain
    _, tr = run_scenario(cfg, _scenario(events, initial=HOT_START), n_ticks=8)
    assert tr.ticks[5].burst_latched is True
    assert tr.ticks[5].selection.kind.value != "reactive"


# --- corner cases (review pass, 2026-06-12) ---------------------------------------------------------


def test_direct_reply_to_a_new_provoker_is_never_displaced():
    """While latched, a brand-new provoker insults — the reply is a DIRECT reply to this tick's
    provocation: full relational cost, no displacement tag (the bug the review caught: it was
    tagged displaced because last_provocation_source was still None)."""
    cfg = _burst_cfg(
        extinction={"anger": 0.02, "stress": 0.02},
        appraisal={"gesture_channels": [], "kindness_pressure": 0.0},
    )
    events = [RawEvent(t=5, type="insult", source="brun", intensity=1.0)]
    _, tr = run_scenario(cfg, _scenario(events, initial=HOT_START), n_ticks=8)
    tk = tr.ticks[5]
    assert tk.burst_latched is True
    assert tk.selection.kind.value == "reactive"
    assert "[DISPLACED" not in tk.selection.explanation
    booked = tk.selection.post_effects.relations.get("brun", {}).get("resentment", 0.0)
    assert booked > 0.05  # the provoker's grudge books in FULL


def test_warm_reply_below_the_displacement_bar_is_not_tagged_or_discounted():
    """Kindness appraisal ON, latched, but anger BELOW theta_displace: the appraisal route wins
    completely unchanged — positive_response, no displacement tag, trust deposit kept."""
    cfg = _burst_cfg(
        extra={"theta_displace": 0.99},  # the bar sits above the run's anger
        extinction={"anger": 0.02, "stress": 0.02},
    )  # default appraisal: kindness ON
    events = [
        RawEvent(
            t=5, type="food_given", source="marta", item="warm_meal", intensity=0.8
        )
    ]
    _, tr = run_scenario(cfg, _scenario(events, initial=HOT_START), n_ticks=8)
    tk = tr.ticks[5]
    assert tk.burst_latched is True
    assert tk.selection.action == "positive_response"
    assert "[DISPLACED" not in tk.selection.explanation
    trust = tk.selection.post_effects.relations.get("marta", {}).get("trust", 0.0)
    assert trust > 0.0  # goodwill books undiscounted


def test_above_the_bar_displacement_overrides_kindness():
    """Kindness appraisal ON, latched, anger ABOVE theta_displace: the kindness is suppressed —
    fury past the bar no longer hears it ("even someone kind, even at their kindness"). The
    discharge lands on Marta, tagged displaced, transient booking — and NO trust deposit (the warm
    reply never fired). theta_displace is THE dial between the two regimes (spec section 8 burst)."""
    cfg = _burst_cfg(
        extinction={"anger": 0.02, "stress": 0.02}
    )  # kindness ON, bar at 0.55 < anger 0.95
    events = [
        RawEvent(
            t=5, type="food_given", source="marta", item="warm_meal", intensity=0.8
        )
    ]
    _, tr = run_scenario(cfg, _scenario(events, initial=HOT_START), n_ticks=8)
    tk = tr.ticks[5]
    assert tk.burst_latched is True
    assert tk.selection.action == "outburst"
    assert "[DISPLACED" in tk.selection.explanation
    booked = tk.selection.post_effects.relations.get("marta", {})
    assert booked.get("resentment", 0.0) == 0.0  # transient (discount 0)
    assert booked.get("trust", 0.0) == 0.0  # no goodwill either: the warmth never fired


def test_strangers_first_insult_books_a_real_grudge():
    """Spec section 5: booking CREATES the relation row — a stranger's first insult starts a real
    grudge from the INPUT deposit itself (previously dropped; only post-effects created rows).
    Run with anger low and the gate effectively closed so no reply fires: the deposit alone must
    appear."""
    cfg = _load({"thresholds": {"react_default": 2.0, "reactive_window_ticks": 1}})
    events = [RawEvent(t=2, type="insult", source="total_stranger", intensity=0.8)]
    calm = {"global_state": {"anger": 0.05, "stress": 0.05}}
    _, tr = run_scenario(cfg, _scenario(events, initial=calm), n_ticks=5)
    row = tr.ticks[2].state_after_commit.relations.get("total_stranger", {})
    assert row.get("resentment", 0.0) > 0.05  # the input deposit landed on a fresh row
    # and the row persists (relational memory)
    end = tr.ticks[-1].state_after_post.relations.get("total_stranger", {})
    assert end.get("resentment", 0.0) > 0.05


def test_theta_displace_without_latch_config_is_inert():
    cfg = _load(
        {
            "thresholds": {"theta_displace": 0.55, "reactive_window_ticks": 1},
            "appraisal": {"gesture_channels": [], "kindness_pressure": 0.0},
        }
    )
    events = [
        RawEvent(
            t=5, type="food_given", source="marta", item="warm_meal", intensity=0.8
        )
    ]
    _, tr = run_scenario(cfg, _scenario(events, initial=HOT_START), n_ticks=8)
    assert all(not tk.burst_latched for tk in tr.ticks)
    assert tr.ticks[5].selection.kind.value != "reactive"  # the gate never widens


def test_confirm_dwell_resets_when_the_band_is_left():
    """The confirm counter must reset if the loop dips out of the saturation band mid-dwell: a
    strong extinction-free decay run that leaves the band before confirm completes never latches."""
    cfg = _load(
        {
            "thresholds": dict(BURST_THRESHOLDS, **{"burst_confirm_ticks": 6}),
        }
    )
    # stress starts just at the band edge and decays out of it within the 6-tick confirm window
    init = {"global_state": {"anger": 0.95, "stress": 0.62}}
    _, tr = run_scenario(cfg, _scenario([], initial=init), n_ticks=12)
    assert all(not tk.burst_latched for tk in tr.ticks)


def test_partial_burst_threshold_set_is_a_config_error():
    with pytest.raises(ValueError, match="partial burst-latch"):
        _load({"thresholds": {"burst_enter.anger": 0.8}})


def test_inverted_hysteresis_is_a_config_error():
    with pytest.raises(ValueError, match="hysteresis"):
        _load(
            {
                "thresholds": {
                    "burst_enter.anger": 0.8,
                    "burst_enter.stress": 0.6,
                    "burst_exit": 0.85,
                }
            }
        )


def test_zero_confirm_ticks_is_a_config_error():
    with pytest.raises(ValueError, match="burst_confirm_ticks"):
        _load({"thresholds": dict(BURST_THRESHOLDS, **{"burst_confirm_ticks": 0})})


def test_negative_k_esc_is_a_config_error():
    with pytest.raises(ValueError, match="k_esc"):
        _load({"coupling_escalation": {"anger": {"stress": -0.5}}})


def test_out_of_range_extinction_is_a_config_error():
    with pytest.raises(ValueError, match="rate must be"):
        _load(
            {
                "thresholds": BURST_THRESHOLDS,
                "burst_extinction": {"anger": 1.5},
            }
        )


# --- G7: the latched-provoker refractory edge (M20.1, the 4th inhibitory edge) ---------------------


def _refractory_run(refractory_on=True, n_ticks=9):
    """LATCHED + a deeply-resented provoker (brun) insults TWICE from the same source. The first
    insult (t3) is a brand-new provocation -- last_provocation_source is not yet brun -- so it is an
    ordinary direct reply that arms the episode (outburst). The second (t6) re-provokes from the SAME
    remembered source while still latched: the refractory edge fires. refractory_on=False zeroes the
    transient magnitude (the edge OFF) as a control, isolating the mechanism (mirror of the
    displacement-discount control test)."""
    appraisal = {"gesture_channels": [], "kindness_pressure": 0.0}
    if not refractory_on:
        appraisal["refractory_pressure"] = 0.0
    cfg = _burst_cfg(
        extra={
            "reactive_window_ticks": 1,
            "burst_exit": 0.10,
            "refractory_anger": 0.30,
        },
        extinction={"anger": 0.005, "stress": 0.005},  # latch holds across both insults
        appraisal=appraisal,
    )
    initial = {
        "global_state": {"anger": 0.95, "stress": 0.90},
        "relations": {"brun": {"resentment": 0.9}},
    }
    events = [
        RawEvent(t=3, type="insult", source="brun", intensity=1.0),
        RawEvent(t=5, type="insult", source="brun", intensity=1.0),
    ]
    _, tr = run_scenario(cfg, _scenario(events, initial=initial), n_ticks=n_ticks)
    return tr


def test_refractory_suppresses_a_second_outburst_at_the_same_provoker():
    """One episode, not two identical eruptions: the first same-source insult erupts (arms the
    episode); the second, while still latched, does NOT re-explode -- the spent fury yields to a
    lower-intensity reply. The cichy_multi_060 relentless-cluster fix. (Which reply survives is
    calibration texture; the TOPOLOGY claim is only that a fresh full outburst does not re-fire.)"""
    tr = _refractory_run(refractory_on=True)
    first, second = tr.ticks[3], tr.ticks[5]
    assert first.burst_latched is True
    assert first.selection.action == "outburst"  # the first eruption stands
    assert second.burst_latched is True  # still inside the episode
    assert second.selection.action != "outburst"  # ...but it does NOT re-explode
    assert (
        second.event is not None and second.event.source == "brun"
    )  # the same provoker spoke


def test_refractory_off_re_explodes_every_time_the_provoker_speaks():
    """CONTROL: with the refractory transient zeroed, the SAME scenario re-fires a fresh outburst on
    the second insult -- proving the edge (not luck or decay) is what produces the single-episode
    reading."""
    tr = _refractory_run(refractory_on=False)
    assert tr.ticks[3].selection.action == "outburst"
    assert (
        tr.ticks[5].selection.action == "outburst"
    )  # the relentless cluster, un-fixed
    # ...and the edge measurably lowers the second outburst potential:
    on = _refractory_run(refractory_on=True).ticks[5].potentials["outburst"]
    off = tr.ticks[5].potentials["outburst"]
    assert on < off


def test_refractory_does_not_fire_for_a_different_provoker():
    """Source-scoped (like the displacement gate's `target != provoker`): a genuinely NEW provoker
    interrupting a latched episode still draws a full ordinary reaction -- the refractory brake only
    spares the engine from re-exploding at the SAME source it already vented on."""
    appraisal = {"gesture_channels": [], "kindness_pressure": 0.0}
    cfg = _burst_cfg(
        extra={
            "reactive_window_ticks": 1,
            "burst_exit": 0.10,
            "refractory_anger": 0.30,
        },
        extinction={"anger": 0.005, "stress": 0.005},
        appraisal=appraisal,
    )
    initial = {
        "global_state": {"anger": 0.95, "stress": 0.90},
        "relations": {"brun": {"resentment": 0.9}, "kasimir": {"resentment": 0.9}},
    }
    events = [
        RawEvent(
            t=3, type="insult", source="brun", intensity=1.0
        ),  # arms; brun = provoker
        RawEvent(t=5, type="insult", source="kasimir", intensity=1.0),  # a NEW provoker
    ]
    _, tr = run_scenario(cfg, _scenario(events, initial=initial), n_ticks=9)
    assert tr.ticks[5].burst_latched is True
    assert (
        tr.ticks[5].selection.action == "outburst"
    )  # a new provoker still gets the full reaction


def test_refractory_is_inert_without_refractory_anger():
    """The bit-identical guarantee for the shipped default: with `refractory_anger` UNSET, the edge
    never engages -- repeated same-source insults behave exactly as without it, even when hot. (The
    gate is now keyed on `refractory_anger`, not the latch; absent -> always 0.)"""
    base = _load(
        {"thresholds": {"reactive_window_ticks": 3}}
    )  # no refractory_anger, no burst thresholds
    initial = {
        "global_state": {"anger": 0.95, "stress": 0.90},
        "relations": {"brun": {"resentment": 0.9}},
    }
    events = [
        RawEvent(t=3, type="insult", source="brun", intensity=1.0),
        RawEvent(t=6, type="insult", source="brun", intensity=1.0),
    ]
    _, tr = run_scenario(base, _scenario(events, initial=initial), n_ticks=9)
    assert all(not tk.burst_latched for tk in tr.ticks)
    # both same-source insults are handled by the ordinary path (no refractory suppression)
    assert tr.ticks[3].selection.action == tr.ticks[6].selection.action


def test_refractory_fires_WITHOUT_the_latch():
    """THE DECOUPLING (M20.1, 2026-06-14): the spent-fury brake works with NO latch at all -- exactly
    the relentless single-provoker case (cichy_multi_060) the vent never catches. A resented provoker
    insults twice from a moderate, NON-saturating state: the loop never reaches the band, the latch
    never arms, yet the SECOND same-source insult (anger still >= refractory_anger from the first
    eruption) does NOT re-explode. With `refractory_anger` UNSET on the same scenario, it would."""
    initial = {
        "global_state": {
            "anger": 0.55,
            "stress": 0.20,
        },  # hot temper, but stress far below the band
        "relations": {"brun": {"resentment": 0.9}},
    }
    events = [
        RawEvent(
            t=2, type="insult", source="brun", intensity=1.0
        ),  # first: new source -> erupts
        RawEvent(
            t=4, type="insult", source="brun", intensity=1.0
        ),  # repeat: still hot -> refractory
    ]
    # NO burst-latch thresholds; only the refractory gate + reactive window.
    on = _load({"thresholds": {"reactive_window_ticks": 1, "refractory_anger": 0.30}})
    off = _load({"thresholds": {"reactive_window_ticks": 1}})  # refractory_anger unset
    _, tr_on = run_scenario(on, _scenario(events, initial=initial), n_ticks=8)
    _, tr_off = run_scenario(off, _scenario(events, initial=initial), n_ticks=8)
    assert all(
        not tk.burst_latched for tk in tr_on.ticks
    )  # the vent never armed (single loop)
    assert tr_on.ticks[2].selection.action == "outburst"  # first eruption stands
    assert (
        tr_on.ticks[4].selection.action != "outburst"
    )  # ...but the repeat does NOT re-explode
    assert (
        tr_off.ticks[4].selection.action == "outburst"
    )  # without the gate, it re-explodes


# --- determinism ------------------------------------------------------------------------------------


def test_burst_run_is_deterministic():
    a = _displacement_run(theta_displace_on=True)
    b = _displacement_run(theta_displace_on=True)
    assert a.to_json() == b.to_json()
