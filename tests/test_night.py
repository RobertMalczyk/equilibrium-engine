"""Night & sleep (M7.5 Part B) -- multi-day property tests.

Short (2-day) and long (few-day) runs of the day/night cycle. They assert the QUALITATIVE contract, not
hand-picked magnitudes (Rule 1): the FAST states reset each night while the SLOW causes (a grudge built
from insults AND from one's own outbursts at the provoker) PERSIST across every night and compound day
over day. Personas stay STATIC -- only world events (insults + a `nightfall`) are scheduled; no trait/param
change. All magnitudes are calibration placeholders.
"""

from engine.schema import Mode
from eval.night_runner import DAY_LEN, _insults, day_summaries, run_nights


def _resentment(tr, src, t):
    return tr.ticks[t].state_after_post.relations.get(src, {}).get("resentment", 0.0)


# ----------------------------- SHORT: 2 days -----------------------------


def test_sleeps_each_night_and_resets_anger():
    """A calm persona over 2 days enters SLEEP each night and the fast states bottom out (the reset): the
    minimum anger reached each day (the sleep-bottom) is low, well below the day's peak."""
    _, tr = run_nights(
        "halgrim",
        days=2,
        day_events=_insults("wojslaw", 1),
        initial={"global_state": {"fatigue": 0.5, "anger": 0.4}},
    )
    days = day_summaries(tr, 2)
    assert all(d["slept"] for d in days)  # sleeps both nights
    for d in days:
        assert d["min_anger"] < 0.20  # the night drives anger down (reset)
        assert d["min_anger"] < d["peak_anger"]


def test_grudge_persists_over_the_night():
    """Sleep angry, wake calm, but the grudge stays: an insult on day 0 builds resentment[source]; across
    the night anger resets (sleep-bottom low) while resentment is essentially unchanged at the next dawn."""
    src = "wojslaw"
    _, tr = run_nights(
        "halgrim",
        days=2,
        day_events=lambda d: _insults(src, 2)(d) if d == 0 else [],
        initial={"global_state": {"fatigue": 0.5}},
    )
    res_dusk_day0 = _resentment(tr, src, DAY_LEN - 1)
    res_dawn_day1 = _resentment(
        tr, src, DAY_LEN
    )  # first tick of day 1 (just after the night)
    assert res_dusk_day0 > 0.05  # a grudge formed
    assert (
        abs(res_dawn_day1 - res_dusk_day0) < 0.02
    )  # ...and it survived the night (slow state)
    assert (
        day_summaries(tr, 2)[0]["min_anger"] < 0.20
    )  # while anger was reset overnight


# ----------------------------- LONG: a few days -----------------------------


def test_outburst_grudge_compounds_and_persists_over_nights():
    """The headline LONG case: a hot persona (Wojsław) provoked daily by Marta OUTBURSTS at her repeatedly;
    each outburst books +resentment[Marta] (on top of the insults), so the dislike HARDENS into a standing
    grudge that (a) never falls back overnight and (b) the fast anger still resets every night."""
    days = 4
    _, tr = run_nights(
        "wojslaw",
        days=days,
        day_events=_insults("marta", 3),
        initial={"global_state": {"fatigue": 0.5}},
    )
    s = day_summaries(tr, days, source="marta")
    assert all(d["slept"] for d in s)  # sleeps every night despite the day's fury
    assert all(d["outbursts"] >= 3 for d in s)  # numerous outbursts at Marta each day
    # the grudge is built up and NEVER falls back across a night (persistence of the slow cause):
    for d in range(1, days):
        assert s[d]["resentment_dawn"] >= s[d - 1]["resentment_dusk"] - 1e-6
    assert (
        s[-1]["resentment_dusk"] > s[0]["resentment_dawn"] + 0.2
    )  # it hardened well above the start
    # ...while the FAST anger is reset each night (the sleep-bottom is low every day):
    assert all(d["min_anger"] < 0.20 for d in s)
    # bounded -- no runaway:
    assert all(
        0.0 <= _resentment(tr, "marta", t) <= 1.0 for t in range(0, days * DAY_LEN, 50)
    )


def test_sparse_grudge_strictly_compounds_across_days():
    """With only ONE provocation per day the grudge climbs gradually -- resentment[Marta] strictly INCREASES
    from day to day (each day's outburst adds to it; the night never erases it) until it nears saturation."""
    days = 3
    _, tr = run_nights(
        "wojslaw",
        days=days,
        day_events=_insults("marta", 1),
        initial={"global_state": {"fatigue": 0.5}},
    )
    s = day_summaries(tr, days, source="marta")
    dawns = [d["resentment_dawn"] for d in s]
    assert (
        dawns[1] > dawns[0] and dawns[2] > dawns[1]
    )  # the dislike compounds day over day
    assert all(d["slept"] for d in s)


def test_few_day_run_is_deterministic():
    """Bit-for-bit determinism over a multi-day run (the project pillar) -- same actions, same states."""

    def actions():
        _, tr = run_nights(
            "wojslaw",
            days=4,
            day_events=_insults("marta", 3),
            initial={"global_state": {"fatigue": 0.5}},
        )
        return [
            (
                tk.t,
                tk.selection.action,
                round(tk.state_after_post.global_state["anger"], 6),
            )
            for tk in tr.ticks
        ]

    assert actions() == actions()


def test_wake_on_threat_interrupts_sleep():
    """Wake-on-threat (no special-cased tiers -- just the high theta_interrupt): a calm morning lets the
    persona fall asleep; then a RESENTED source hammers strong insults mid-night, the reaction clears the
    interrupt threshold, and the sleeper is shaken awake (a REACTIVE action while the previous mode is SLEEP).
    A mild stimulus would never clear that threshold -- you sleep through small things, wake to big ones."""

    def events(d):  # several hard insults DURING the night window
        return [
            (
                130 + i * 2,
                {
                    "type": "insult",
                    "source": "marta",
                    "intensity": 1.0,
                    "context": {"public": True},
                },
            )
            for i in range(4)
        ]

    _, tr = run_nights(
        "wojslaw",
        days=1,
        day_events=events,
        initial={
            "global_state": {"fatigue": 0.6},
            "relations": {"marta": {"resentment": 0.9, "respect": 0.1, "trust": 0.1}},
        },
    )
    assert any(
        tk.state_after_post.mode == Mode.SLEEP for tk in tr.ticks
    )  # it did fall asleep
    woke = any(
        tr.ticks[i].snapshot.mode == Mode.SLEEP
        and tr.ticks[i].selection.kind.name == "REACTIVE"
        for i in range(len(tr.ticks))
    )
    assert woke  # ...and was shaken awake by the threat
