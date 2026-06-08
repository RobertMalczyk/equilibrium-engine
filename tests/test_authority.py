"""Proactive authority -- the live-multi-agency FIRST SLICE (spec section 8).

The duty drive (a state in its second role, the mirror of boredom->seek) makes Edda issue orders;
the cross-agent router turns each command_other into a subordinate's command event, resolved by the
EXISTING cooperate/refuse pipeline. Property/contrast tests (Rule 1): assert orderings/contrasts and
the routing structure, never hand-picked magnitudes. Magnitudes are calibration placeholders.
"""

from pathlib import Path

from engine.schema import Mode, Scenario
from engine.simulation import run_scenario
from engine.yaml_io import load_persona
from eval.orchestrator import Roster

ROOT = Path(__file__).resolve().parents[1]
DEFAULTS = ROOT / "calibration" / "defaults.yaml"
_IDLE = {"global_state": {"boredom": 0.10, "fatigue": 0.20, "stress": 0.10}}


def _cfg(persona_id, overrides=None):
    return load_persona(
        ROOT / "data" / "personas" / f"{persona_id}.yaml",
        DEFAULTS,
        param_overrides=overrides,
    )


def _idle_run(persona_id, n, overrides=None):
    cfg = _cfg(persona_id, overrides)
    sc = Scenario(id="idle", persona=persona_id, initial_overrides=_IDLE, events=())
    _, tr = run_scenario(cfg, sc, n_ticks=n)
    return tr


def _first_command(tr):
    return next(
        (tk.t for tk in tr.ticks if tk.selection.action == "command_other"), None
    )


# ----------------------------- the duty drive (engine side) -----------------------------


def test_duty_accrues_only_for_an_authority_persona():
    """duty drifts up for Edda (authority: drift>0) and stays flat at 0 for a non-authority persona
    (sparse: drift 0). The duty STATE is what carries the authority drive (a state in its second role)."""
    edda = [
        tk.state_after_post.global_state["duty"] for tk in _idle_run("edda", 400).ticks
    ]
    halgrim = [
        tk.state_after_post.global_state["duty"]
        for tk in _idle_run("halgrim", 400).ticks
    ]
    assert edda[-1] > edda[0]  # accrues
    assert all(d == 0.0 for d in halgrim)  # non-authority: never leaves 0


def test_command_other_fires_for_authority_only():
    """Edda issues orders (command_other); non-authority personas never do -- the contrast emerges from
    the duty drift (sparse) + the need_for_control tempo, not a special case."""
    assert _first_command(_idle_run("edda", 1500)) is not None
    for p in ("halgrim", "branic", "lutek", "wojslaw"):
        assert _first_command(_idle_run(p, 1500)) is None


def test_command_other_discharges_duty_then_cooldown():
    """An order fires INSTANTANEOUSLY: it discharges duty (the accrue/discharge arc) and goes to COOLDOWN
    (not BUSY, not SEEKING) -- so it cannot re-fire the very next tick; the cooldown rate-limits it."""
    tr = _idle_run("edda", 1500)
    i = next(
        i for i, tk in enumerate(tr.ticks) if tk.selection.action == "command_other"
    )
    duty_before = tr.ticks[i].state_after_commit.global_state["duty"]
    duty_after = tr.ticks[i].state_after_post.global_state["duty"]
    assert duty_after < duty_before  # post-effect discharged duty
    assert (
        tr.ticks[i].state_after_post.mode == Mode.COOLDOWN
    )  # instantaneous -> COOLDOWN
    assert (
        tr.ticks[i + 1].selection.action != "command_other"
    )  # rate-limited (no order every tick)


def test_urge_command_tempo_by_need_for_control():
    """need_for_control is the TEMPO modulator (mirror of novelty_seeking -> urge_boredom): a higher-control
    persona acts on the SAME accrued duty sooner. Vary ONLY need_for_control on Edda (same drift)."""
    hi = _first_command(
        _idle_run("edda", 2000, overrides={"traits": {"need_for_control": 0.95}})
    )
    lo = _first_command(
        _idle_run("edda", 2000, overrides={"traits": {"need_for_control": 0.70}})
    )
    assert hi is not None and lo is not None
    assert hi < lo  # more control -> issues sooner


def test_no_duty_drift_means_no_authority():
    """Isolate the activation: zero Edda's duty drift and she never issues an order (duty can't accrue).
    Confirms the authority behavior rides on the drift, not on her other traits."""
    flat = _idle_run("edda", 1500, overrides={"drifts": {"duty": 0.0}})
    assert _first_command(flat) is None


# ----------------------------- the cross-agent router -----------------------------


def _roster_run(n=1200):
    # The orchestrator is the believability-run (eval) component, so it is exercised on the SAME
    # calibrated+recovery dynamics the day corpus uses (eval.calibrated.load_eval_persona) -- a settled
    # subordinate, not one wound up by uncalibrated idle drift. (The duty drive itself is config-identical;
    # only the recovery layer differs, and it is what lets respect-driven cooperate cleanly win.)
    from eval.calibrated import load_eval_persona

    agents = ["edda", "halgrim"]
    configs = {a: load_eval_persona(a) for a in agents}
    scenarios = {
        a: Scenario(id="idle", persona=a, initial_overrides=_IDLE, events=())
        for a in agents
    }
    roster = Roster(
        configs=configs,
        targets={"edda": ["halgrim"]},
        order_intensity=1.0,
        world_kwargs=dict(seed=7),
    )
    return roster.run(scenarios, n_ticks=n)


def test_router_delivers_order_one_tick_later_and_subordinate_obeys():
    """The core of the slice: Edda's command_other becomes Halgrim's `command` event ONE TICK LATER, and
    Halgrim resolves it through the existing obedience pipeline -> cooperate (he respects Edda). Authority
    is now observable: an order issued, a subordinate obeying."""
    traces = _roster_run()
    orders = [
        tk.t for tk in traces["edda"].ticks if tk.selection.action == "command_other"
    ]
    assert orders, "Edda issued no orders"
    # Halgrim cooperates at the tick AFTER each routed order (one-tick delay).
    hal = {tk.t: tk.selection.action for tk in traces["halgrim"].ticks}
    assert any(hal.get(t0 + 1) == "cooperate" for t0 in orders)


def test_router_is_deterministic():
    """Sorted roster iteration + deterministic target + one-tick delay -> bit-for-bit reproducible."""
    a = [tk.selection.action for tk in _roster_run()["halgrim"].ticks]
    b = [tk.selection.action for tk in _roster_run()["halgrim"].ticks]
    assert a == b


def test_back_edge_off_issuer_receives_nothing():
    """Back-edge OFF (slice 1): a subordinate's reaction does NOT route back to the issuer. Edda is no
    one's target, so she never receives a command -> her obedience potentials stay dormant (no cooperate/
    refuse in her own trace). The cross-agent path is pure feedforward."""
    edda = {tk.selection.action for tk in _roster_run()["edda"].ticks}
    assert "cooperate" not in edda and "refuse" not in edda
