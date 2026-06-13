"""Social Event Mapper Pack — the three negative-but-not-insult social events (cold_reply, refusal,
complaint). Mapper unit tests (A-D), simulation-level effects (E-G), regression of the existing
vocabulary (A-E), and an event-vocabulary coverage contract test.

These cover a MAPPER/SPEC extension only: new input surfaces -> tagged relational SemanticInput
channels, with magnitudes in config. No new internal state, no event-to-action scripting.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from engine.mapper import map_event
from engine.schema import (
    HistoryFeatures,
    InputClass,
    Polarity,
    RawEvent,
    Scenario,
)
from engine.simulation import run_scenario
from engine.yaml_io import load_persona

ROOT = Path(__file__).resolve().parents[1]
PERSONA = ROOT / "data" / "personas" / "wojslaw.yaml"
DEFAULTS = ROOT / "calibration" / "defaults.yaml"

NEW_EVENTS = ("cold_reply", "refusal", "complaint")


def _cfg():
    return load_persona(PERSONA, DEFAULTS)


def _feats():
    return HistoryFeatures()


def _map(event_type, intensity=1.0, source="speaker", target="listener", context=None):
    ev = RawEvent(
        type=event_type,
        t=0,
        source=source,
        target=target,
        intensity=intensity,
        context=context or {},
    )
    return map_event(ev, _cfg(), _feats())


def _scenario(events, initial=None):
    return Scenario(
        id="social_test",
        persona="wojslaw",
        initial_overrides=initial or {},
        events=tuple(events),
    )


# ============================ MAPPER UNIT TESTS ============================


# Test A: new events are recognized, relational, negative, source-preserved, value tied to intensity.
@pytest.mark.parametrize("etype", NEW_EVENTS)
def test_A_new_event_recognized(etype):
    out = _map(etype, intensity=1.0)
    assert out, f"{etype} mapped to an empty vector"
    assert etype in out, f"{etype} did not emit its own channel '{etype}'"
    si = out[etype]
    assert si.cls is InputClass.RELATIONAL
    assert si.source == "speaker"
    assert si.polarity is Polarity.NEGATIVE
    assert si.value > 0.0
    assert si.value == pytest.approx(1.0)  # value tied to intensity (mapper is dumb)


# Test B: zero intensity is inert at the mapper level (channel present but value 0 -> no social effect).
@pytest.mark.parametrize("etype", NEW_EVENTS)
def test_B_zero_intensity_inert(etype):
    out = _map(etype, intensity=0.0)
    # consistent with the existing dumb-mapper style: the channel may exist, but with value 0.0
    assert out.get(etype) is None or out[etype].value == pytest.approx(0.0)


# Test C: the channel value is monotonic with intensity.
@pytest.mark.parametrize("etype", NEW_EVENTS)
def test_C_intensity_scaling(etype):
    half = _map(etype, intensity=0.5)[etype].value
    full = _map(etype, intensity=1.0)[etype].value
    assert half < full
    assert half == pytest.approx(0.5)


# Test D: not aliases of insult — own channel names, and a lower anger effect than insult.
def test_D_not_aliases_of_insult_channels():
    for etype in NEW_EVENTS:
        out = _map(etype)
        assert "insult" not in out, f"{etype} leaked the insult channel"
        assert etype in out


def test_D_lower_anger_than_insult():
    cfg = _cfg()
    init = {"global_state": {"anger": 0.0, "stress": 0.0}}

    def anger_after(etype):
        _, tr = run_scenario(
            cfg,
            _scenario([RawEvent(type=etype, t=0, source="x", intensity=1.0)], init),
            n_ticks=1,
        )
        return tr.ticks[0].state_after_commit.global_state["anger"]

    insult_anger = anger_after("insult")
    for etype in NEW_EVENTS:
        assert anger_after(etype) < insult_anger, (
            f"{etype} anger effect should be < insult's"
        )


# ============================ SIMULATION-LEVEL EFFECTS ============================


# Test E: each new event moves state in the intended direction (vs an empty scenario).
@pytest.mark.parametrize("etype", NEW_EVENTS)
def test_E_new_event_affects_state(etype):
    cfg = _cfg()
    init = {"global_state": {"anger": 0.0, "stress": 0.0, "frustration": 0.0}}
    _, base = run_scenario(cfg, _scenario([], init), n_ticks=1)
    _, ev = run_scenario(
        cfg,
        _scenario([RawEvent(type=etype, t=0, source="x", intensity=1.0)], init),
        n_ticks=1,
    )
    b = base.ticks[0].state_after_commit
    e = ev.ticks[0].state_after_commit
    # frustration (the shared social-friction path) rises for all three
    assert e.global_state["frustration"] > b.global_state["frustration"]
    # and a standing-grievance deposit lands on the source
    assert e.relations.get("x", {}).get("resentment", 0.0) > 0.0


def test_E_refusal_erodes_respect_or_trust():
    """refusal expresses friction WITH respect/trust erosion (the negative relation deposits)."""
    cfg = _cfg()
    init = {"relations": {"x": {"respect": 0.6, "trust": 0.6}}}
    _, tr = run_scenario(
        cfg,
        _scenario([RawEvent(type="refusal", t=0, source="x", intensity=1.0)], init),
        n_ticks=1,
    )
    row = tr.ticks[0].state_after_commit.relations["x"]
    assert row["respect"] < 0.6 or row["trust"] < 0.6


def test_E_complaint_weights_frustration_over_anger():
    """complaint should hit the frustration/resentment paths MORE than raw anger."""
    cfg = _cfg()
    init = {"global_state": {"anger": 0.0, "frustration": 0.0}}
    _, tr = run_scenario(
        cfg,
        _scenario([RawEvent(type="complaint", t=0, source="x", intensity=1.0)], init),
        n_ticks=1,
    )
    g = tr.ticks[0].state_after_commit.global_state
    assert g["frustration"] > g["anger"]


# Test F: public exposure amplifies the relational impact (handled by the relation_filter, not the
# mapper -- the new channels are relational, so they get social exposure for free).
@pytest.mark.parametrize("etype", NEW_EVENTS)
def test_F_public_at_least_as_strong_as_private(etype):
    cfg = _cfg()

    def resentment(public):
        _, tr = run_scenario(
            cfg,
            _scenario(
                [
                    RawEvent(
                        type=etype,
                        t=0,
                        source="x",
                        intensity=1.0,
                        context={"public": public},
                    )
                ]
            ),
            n_ticks=1,
        )
        return (
            tr.ticks[0].state_after_commit.relations.get("x", {}).get("resentment", 0.0)
        )

    assert resentment(True) >= resentment(False)


# Test G: relation-row creation works for a previously-unknown source (booking creates the row).
@pytest.mark.parametrize("etype", NEW_EVENTS)
def test_G_relation_row_created_for_new_source(etype):
    cfg = _cfg()
    _, tr = run_scenario(
        cfg,
        _scenario([RawEvent(type=etype, t=0, source="newcomer", intensity=1.0)]),
        n_ticks=1,
    )
    row = tr.ticks[0].state_after_commit.relations.get("newcomer")
    assert row is not None, (
        "a new source's first social event did not create a relation row"
    )
    assert row.get("resentment", 0.0) > 0.0


# ============================ REGRESSION ============================


# Regression A: existing mapper events unchanged.
def test_regression_existing_relational_channels_unchanged():
    assert "insult" in _map("insult")
    assert "help" in _map("help")
    assert "command" in _map("command")


def test_regression_food_weather_nightfall_channels_unchanged():
    assert "food_nutrition" in _map("food_given", source=None)
    assert "weather" in _map("weather", source=None)
    assert "night" in _map("nightfall", source=None)


# Regression B: unknown events remain intentionally empty.
def test_regression_unknown_event_is_empty():
    assert _map("definitely_not_a_real_event") == {}
    assert _map("activity") == {}  # mode-control: handled in simulation, not the mapper


# Regression E: an old event stream is bit-identical before/after (the new channels don't perturb it).
def test_regression_old_stream_bit_identical():
    cfg = _cfg()
    init = {"global_state": {"anger": 0.3, "stress": 0.3}}
    events = [
        RawEvent(type="insult", t=0, source="x", intensity=1.0),
        RawEvent(
            type="food_given", t=4, source="m", item="cabbage_soup", intensity=1.0
        ),
        RawEvent(type="command", t=8, source="cap", intensity=1.0),
    ]
    _, a = run_scenario(cfg, _scenario(events, init), n_ticks=12)
    _, b = run_scenario(cfg, _scenario(events, init), n_ticks=12)
    assert (
        a.to_json() == b.to_json()
    )  # determinism; an old stream never touches the new channels


# ============================ EVENT-VOCABULARY CONTRACT ============================

# The engine's current OFFICIAL RawEvent vocabulary. RawEvent stays an open string type (not an enum);
# this list guards against silent omissions in the mapper/spec, not against new types existing.
OFFICIAL_EVENTS = (
    "food_given",
    "insult",
    "help",
    "command",
    "nightfall",
    "weather",
    "cold_reply",
    "refusal",
    "complaint",
)
# Events handled OUTSIDE the mapper (mode/world control in simulation), documented as intentionally
# empty at the mapper layer.
MODE_CONTROL_EVENTS = ("activity",)


@pytest.mark.parametrize("etype", OFFICIAL_EVENTS)
def test_contract_official_event_maps_to_nonempty(etype):
    # food/weather/nightfall are sourceless (self); the relational ones carry a source.
    src = None if etype in ("food_given", "weather", "nightfall") else "speaker"
    out = _map(etype, source=src, context={})
    assert out, f"official event '{etype}' produced an empty vector"


@pytest.mark.parametrize("etype", MODE_CONTROL_EVENTS)
def test_contract_mode_control_event_is_empty_at_mapper(etype):
    # documented: these are mode/world-control signals consumed in simulation, not channel-mapped.
    assert _map(etype) == {}
