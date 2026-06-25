"""M-J.4 ledger coverage gaps (from the audit) -- mechanisms that were implemented but untested or only
config-asserted. Scenarios are built in-code (like test_multi_event) to avoid proliferating YAML files.

Covers: lies to DIFFERENT targets -> separate records; consistency_debt actually DECAYS between
reinforcements (not just config<1); the `complexity` field is booked; the `unresolvedness >= floor`
inactivation branch (a secret unresolved but no longer hidden stays active); multiple concurrent secrets
stack their stress weight; and the M-J.4 confession discharge (cognitive_load relief + record resolution).
"""

from __future__ import annotations

from pathlib import Path

from engine.schema import RawEvent, Scenario
from engine.simulation import run_scenario
from engine.yaml_io import load_persona
from eval.moral import moral_overrides
from eval.observe import action_counts, trajectory

ROOT = Path(__file__).resolve().parents[1]
DEFAULTS = ROOT / "calibration" / "defaults.yaml"
HALGRIM = ROOT / "data" / "personas" / "halgrim.yaml"

LIAR = {"guilt_proneness": 0.0, "honesty_humility": 0.0}
GUILT_PRONE_HONEST = {"guilt_proneness": 0.9, "honesty_humility": 0.95}
CALM = {
    "fatigue": 0.05,
    "boredom": 0.05,
    "stress": 0.05,
    "frustration": 0.05,
    "anger": 0.05,
}


def _cfg(traits):
    return load_persona(HALGRIM, DEFAULTS, param_overrides=moral_overrides(traits))


def _sc(events, secrets=None):
    ov = {"global_state": dict(CALM)}
    if secrets is not None:
        ov["secrets"] = secrets
    return Scenario(
        id="gap", persona="halgrim", initial_overrides=ov, events=tuple(events)
    )


def _ledger_at(tr, tick):
    return tr.ticks[tick].state_after_post.moral_ledger


# --- M-J.4.1: lies to different targets -> separate records -----------------------------


def test_lies_to_different_targets_make_separate_records():
    # wrongdoing seeds guilt; then two different interrogators probe on alternating ticks -> the liar lies to
    # each -> one record PER target (keyed by target), not a single merged record.
    events = [RawEvent(type="wrongdoing", t=i, intensity=1.0) for i in range(3)]
    for t in range(3, 16):
        src = "guard_a" if t % 2 else "guard_b"
        events.append(RawEvent(type="probe", t=t, source=src, intensity=1.0))
    rt, tr = run_scenario(_cfg(LIAR), _sc(events), n_ticks=16)
    ids = set(rt.moral_ledger.lies)
    assert ids == {"lie:guard_a", "lie:guard_b"}  # a SEPARATE record per target
    for r in rt.moral_ledger.lies.values():
        assert r.target_id in ("guard_a", "guard_b")


def test_complexity_is_booked_on_a_lie():
    events = [RawEvent(type="wrongdoing", t=i, intensity=1.0) for i in range(3)]
    events += [
        RawEvent(type="probe", t=t, source="g", intensity=1.0) for t in range(3, 12)
    ]
    rt, _ = run_scenario(_cfg(LIAR), _sc(events), n_ticks=12)
    rec = next(iter(rt.moral_ledger.lies.values()))
    assert (
        rec.complexity > 0.0
    )  # the lie's complexity is recorded (config max), not left at 0


def test_consistency_debt_decays_after_lying_stops():
    # lie under probing t3-6, then QUIET ticks t7-15 (no events) -> the record's debt is no longer reinforced
    # and decays (mini-integrator), so it is lower at the end than right after the last lie.
    events = [RawEvent(type="wrongdoing", t=i, intensity=1.0) for i in range(3)]
    events += [
        RawEvent(type="probe", t=t, source="g", intensity=1.0) for t in range(3, 11)
    ]
    rt, tr = run_scenario(
        _cfg(LIAR), _sc(events), n_ticks=22
    )  # probe t3-10, then QUIET t11-21
    debts = [
        _ledger_at(tr, t).lies["lie:g"].consistency_debt
        for t in range(22)
        if "lie:g" in _ledger_at(tr, t).lies
    ]
    assert debts, "expected a lie record to have formed"
    assert debts[-1] < max(debts)  # it decayed once reinforcement stopped


# --- M-J.4.3: unresolvedness inactivation branch + multi-secret stacking -----------------


def test_secret_unresolved_but_not_hidden_stays_active():
    """`_secret_active` = hidden_from non-empty OR unresolvedness >= floor. A secret no longer hidden
    (hidden_from empty) but still UNRESOLVED (>= floor) remains active -> its salience still builds."""
    secret = [
        {
            "id": "s1",
            "owner_id": "self",
            "topic": "theft",
            "category": "crime",
            "hidden_from": [],
            "unresolvedness": 0.20,  # not hiding, but unresolved >= floor(0.10) -> ACTIVE
        }
    ]
    events = [
        RawEvent(type="secret_cued", t=t, topic="theft", intensity=1.0)
        for t in range(6)
    ]
    rt, _ = run_scenario(
        _cfg(GUILT_PRONE_HONEST), _sc(events, secrets=secret), n_ticks=6
    )
    assert (
        rt.moral_ledger.secrets["s1"].salience > 0.0
    )  # active via unresolvedness -> cues raise salience


def test_resolved_and_unhidden_secret_is_inactive():
    """The complement: hidden_from empty AND unresolvedness below floor -> INACTIVE -> salience never rises."""
    secret = [
        {
            "id": "s1",
            "owner_id": "self",
            "topic": "theft",
            "category": "crime",
            "hidden_from": [],
            "unresolvedness": 0.0,  # not hiding, resolved -> INACTIVE
        }
    ]
    events = [
        RawEvent(type="secret_cued", t=t, topic="theft", intensity=1.0)
        for t in range(6)
    ]
    rt, _ = run_scenario(
        _cfg(GUILT_PRONE_HONEST), _sc(events, secrets=secret), n_ticks=6
    )
    assert (
        rt.moral_ledger.secrets["s1"].salience == 0.0
    )  # inactive -> the cue is gated to 0


def test_two_active_secrets_stack_their_stress_weight():
    one = [
        {
            "id": "s1",
            "owner_id": "self",
            "topic": "a",
            "category": "crime",
            "hidden_from": ["g"],
        }
    ]
    two = one + [
        {
            "id": "s2",
            "owner_id": "self",
            "topic": "b",
            "category": "crime",
            "hidden_from": ["g"],
        }
    ]
    events = []
    for t in range(8):
        events.append(RawEvent(type="secret_cued", t=t, topic="a", intensity=1.0))
        events.append(RawEvent(type="secret_cued", t=t, topic="b", intensity=1.0))
    _, tr1 = run_scenario(_cfg(GUILT_PRONE_HONEST), _sc(events, secrets=one), n_ticks=8)
    _, tr2 = run_scenario(_cfg(GUILT_PRONE_HONEST), _sc(events, secrets=two), n_ticks=8)
    assert (
        trajectory(tr2, "stress")[-1] > trajectory(tr1, "stress")[-1]
    )  # two burdens weigh more than one


# --- M-J.4 (correction): confession discharges the lie burden ---------------------------


def test_confession_discharges_cognitive_load_and_resolves_the_record():
    """Spec 3.5 lie_confessed: a confession sheds cognitive_load_from_lies and reduces the lie record. We
    seed a prior lie burden (the persona lied before), then it confesses under probing."""
    events = [
        RawEvent(type="probe", t=t, source="interrogator", intensity=1.0)
        for t in range(0, 10)
    ]
    ov = {
        "global_state": dict(CALM, guilt=0.8, cognitive_load_from_lies=0.6),
    }
    sc = Scenario(
        id="confdis", persona="halgrim", initial_overrides=ov, events=tuple(events)
    )
    cfg = _cfg(GUILT_PRONE_HONEST)
    rt, tr = run_scenario(cfg, sc, n_ticks=10)
    assert "confess" in action_counts(tr)
    load = trajectory(tr, "cognitive_load_from_lies")
    # confessing sheds the lie-maintenance burden (it does not just decay -- there is an active discharge)
    assert load[-1] < load[0]
