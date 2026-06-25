"""M-J.4.4 (deterministic part) -- the compatibility/validation GATES (impl spec section 9.1).

Gate A (legacy byte-identical) is covered by `tests/test_tick_golden.py`. This file adds:
- GATE B -- moral ENABLED but all gains zeroed -> behaviorally EQUIVALENT to legacy on a non-moral scenario
  (same actions, same non-moral state/relation curves, no moral action, empty ledger).
- A handful of consolidated GATE C moral invariants (spec section 9.2) not already pinned by a slice test.

The non-deterministic part of M-J.4.4 -- the calibration grid over the placeholder magnitudes and the
judged 700+700 labeled corpus (spec section 10) -- is an LLM-judge / eval-harness task, out of scope here.
"""

from __future__ import annotations

from pathlib import Path

from engine.schema import GLOBAL_STATES, MORAL_POTENTIALS, MORAL_STATES, RELATION_DIMS
from engine.simulation import run_scenario
from engine.yaml_io import load_persona, load_scenario
from eval.moral import moral_overrides, zero_gain_overrides
from eval.observe import trajectory

ROOT = Path(__file__).resolve().parents[1]
DEFAULTS = ROOT / "calibration" / "defaults.yaml"
WOJSLAW = ROOT / "data" / "personas" / "wojslaw.yaml"
HALGRIM = ROOT / "data" / "personas" / "halgrim.yaml"
INSULT = ROOT / "data" / "scenarios" / "insult_public.yaml"
PROBE = ROOT / "data" / "scenarios" / "moral_probe.yaml"

NON_MORAL_STATES = [s for s in GLOBAL_STATES if s not in MORAL_STATES]


def _actions(tr):
    return [tk.selection.action for tk in tr.ticks]


# --- GATE B: zero-gain behavioral equivalence ------------------------------------------


def test_gate_b_zero_gain_matches_legacy_actions_and_nonmoral_curves():
    sc = load_scenario(INSULT)
    rt_l, tr_l = run_scenario(load_persona(WOJSLAW, DEFAULTS), sc, n_ticks=6)
    rt_z, tr_z = run_scenario(
        load_persona(WOJSLAW, DEFAULTS, param_overrides=zero_gain_overrides()),
        sc,
        n_ticks=6,
    )
    # same selected action every tick
    assert _actions(tr_l) == _actions(tr_z)
    # identical NON-MORAL global-state curves (moral states are decoupled at zero gain; dt is unchanged)
    for s in NON_MORAL_STATES:
        assert trajectory(tr_l, s) == trajectory(tr_z, s), f"curve drift on {s}"


def test_gate_b_no_moral_action_and_empty_ledger():
    sc = load_scenario(INSULT)
    cfg = load_persona(WOJSLAW, DEFAULTS, param_overrides=zero_gain_overrides())
    rt, tr = run_scenario(cfg, sc, n_ticks=6)
    assert not (set(_actions(tr)) & MORAL_POTENTIALS)  # no moral action ever selected
    assert rt.moral_ledger.is_empty()  # no ledger writes at zero gain
    # the moral states are present (overlay enabled) but stay flat at 0
    for s in MORAL_STATES:
        assert all(v == 0.0 for v in trajectory(tr, s))


def test_gate_b_nonmoral_relations_match_legacy():
    sc = load_scenario(INSULT)
    _, tr_l = run_scenario(load_persona(WOJSLAW, DEFAULTS), sc, n_ticks=6)
    _, tr_z = run_scenario(
        load_persona(WOJSLAW, DEFAULTS, param_overrides=zero_gain_overrides()),
        sc,
        n_ticks=6,
    )

    def rel(tr):
        out = {}
        for tk in tr.ticks:
            for src, dims in tk.state_after_post.relations.items():
                for d in RELATION_DIMS:
                    if (
                        d in dims and d != "suspicion"
                    ):  # suspicion is the opt-in moral dim
                        out.setdefault((src, d), []).append(round(dims[d], 9))
        return out

    assert rel(tr_l) == rel(tr_z)


# --- GATE C: a couple of consolidated moral invariants (spec 9.2) -----------------------


def test_invariant_outburst_is_not_guilt_alone():
    """spec 9.2: 'outburst != guilt alone'. A guilt-prone persona under a SELF moral cue (wrongdoing) +
    questioning never erupts in an `outburst` -- guilt/exposure drive confession/concealment, not the burst
    latch (the moral states only FEED anger, they don't open a new burst gate)."""
    cfg = load_persona(
        HALGRIM, DEFAULTS, param_overrides=moral_overrides({"guilt_proneness": 0.9})
    )
    _, tr = run_scenario(cfg, load_scenario(PROBE), n_ticks=16)
    assert "outburst" not in _actions(tr)


def test_invariant_moral_states_stay_bounded_over_a_run():
    """spec 9.2 'no degenerate loop': every moral state stays within [0,1] across a full moral run."""
    cfg = load_persona(
        HALGRIM, DEFAULTS, param_overrides=moral_overrides({"guilt_proneness": 0.8})
    )
    _, tr = run_scenario(cfg, load_scenario(PROBE), n_ticks=16)
    for s in MORAL_STATES:
        assert all(0.0 <= v <= 1.0 for v in trajectory(tr, s))
