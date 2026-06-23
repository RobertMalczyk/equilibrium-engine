"""Tests for the control-interpretation docs + the deterministic state-response diagnostic.

These assert (a) the documentation states the correct control reading (event = finite discrete
impulse, NOT a Dirac; additive gains are per-tick, not auto per_second*dt), and (b) the diagnostic
computes the engine's actual decay/steady-state math and flags clamp reliance + anger<->stress loop
stability. Pure/offline -- no engine state mutated, no LLM, fully deterministic.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from engine.stability import (
    anger_stress_loop_report,
    decay_from,
    exceeds_clamp,
    impulse_response,
    state_response,
    state_response_report,
    steady_state_drift,
)
from engine.yaml_io import load_persona

ROOT = Path(__file__).resolve().parents[1]
DOC = ROOT / "docs" / "control_interpretation.md"
UPDATE_DOC = ROOT / "docs" / "diagrams" / "update.md"


# --- documentation contracts --------------------------------------------------------


def test_control_interpretation_doc_exists():
    assert DOC.exists(), "docs/control_interpretation.md must exist"
    assert DOC.stat().st_size > 0


def test_doc_describes_event_as_finite_impulse_not_dirac():
    txt = DOC.read_text(encoding="utf-8").lower()
    assert "finite" in txt and "impulse" in txt
    assert "dirac" in txt  # it must explicitly address (and reject) the Dirac reading
    # the doc must say it is NOT a (true) Dirac delta, not assert one is stored
    assert "not" in txt and "delta" in txt


def test_doc_does_not_claim_additive_gains_are_continuous_rates():
    """update.md must clarify that additive terms are per-tick, NOT automatically per_second*dt."""
    txt = UPDATE_DOC.read_text(encoding="utf-8").lower()
    assert "per tick" in txt or "per-tick" in txt
    assert (
        "per_second" in txt
    )  # the clarification explicitly names and bounds this reading
    assert "decay" in txt and "2 ** (-dt / half_life)".lower() in txt.replace(" ", " ")


# --- diagnostic math ----------------------------------------------------------------


def test_decay_matches_engine_formula():
    # decay = 2 ** (-dt / half_life), exactly as engine/yaml_io builds it.
    assert decay_from(half_life=30.0, dt=3.0) == pytest.approx(2.0 ** (-3.0 / 30.0))
    cfg = load_persona("data/personas/halgrim.yaml", "calibration/defaults.yaml")
    for s, hl in cfg.half_lives.items():
        assert decay_from(hl, cfg.dt) == pytest.approx(cfg.decay[s])


def test_steady_state_drift_formula():
    assert steady_state_drift(0.9, 0.05) == pytest.approx(0.05 / (1 - 0.9))
    assert steady_state_drift(0.5, 0.0) == 0.0


def test_impulse_response_is_bounded_decaying_tail():
    ir = impulse_response(0.9, gain=1.0, n=5)
    assert ir[0] == pytest.approx(1.0)
    # strictly decreasing, bounded -- an exponential tail, not a persistent spike
    assert all(b < a for a, b in zip(ir, ir[1:]))
    assert all(0.0 <= v <= 1.0 for v in ir)


def test_exceeds_clamp_flags_drift_saturation():
    # drift too strong for the leak -> x_inf > 1 -> relies on clamp
    x_inf = steady_state_drift(decay_from(3000.0, 3.0), 0.001)
    assert x_inf > 1.0
    assert exceeds_clamp(x_inf) is True
    assert exceeds_clamp(0.4) is False


def test_state_response_record_shape_and_clamp_flag():
    r = state_response("hunger", half_life=3000.0, dt=3.0, drift=0.001)
    assert r["state"] == "hunger"
    assert r["decay"] == pytest.approx(2.0 ** (-3.0 / 3000.0))
    assert r["relies_on_clamp"] is True
    assert r["warning"]  # non-empty warning text when clamp-reliant


def test_state_response_report_covers_all_global_states():
    cfg = load_persona("data/personas/halgrim.yaml", "calibration/defaults.yaml")
    rows = state_response_report(cfg)
    from engine.schema import GLOBAL_STATES, MORAL_STATES

    # The report covers exactly the states PRESENT for this persona. A legacy (non-moral) persona has
    # the canonical states and NONE of the opt-in moral states (the moral overlay is absent).
    expected = {s for s in GLOBAL_STATES if s not in MORAL_STATES}
    assert {r["state"] for r in rows} == expected
    for r in rows:
        assert r["x_inf_drift"] == pytest.approx(
            steady_state_drift(r["decay"], r["drift"])
        )


# --- anger<->stress loop report -----------------------------------------------------


def test_anger_stress_report_has_jury_margin_and_dominant_pole():
    cfg = load_persona("data/personas/halgrim.yaml", "calibration/defaults.yaml")
    rep = anger_stress_loop_report(cfg.decay, cfg.couplings, dt=cfg.dt)
    assert "jury_margin" in rep and "dominant_pole" in rep
    assert "dominant_eigenvalue" in rep
    # shipped config is stable: positive margin, pole inside the unit circle
    assert rep["jury_margin"] > 0.0
    assert rep["dominant_pole"] < 1.0
    assert rep["stable"] is True
    # tail half-time is finite and positive for a stable loop
    assert rep["tail_half_time_ticks"] > 0.0


def test_anger_stress_report_flags_instability():
    # construct an unstable 2-cycle: product of cross-gains exceeds the Jury bound
    decay = {"stress": 0.95, "anger": 0.93}
    couplings = {"stress": {"anger": 0.9}, "anger": {"stress": 0.9}}
    rep = anger_stress_loop_report(decay, couplings)
    assert rep["stable"] is False
    assert any("UNSTABLE" in w for w in rep["warnings"])


def test_generator_builds_markdown(tmp_path):
    from eval.state_response_report import build_report

    md = build_report(
        str(ROOT / "data/personas/halgrim.yaml"),
        str(ROOT / "calibration/defaults.yaml"),
    )
    assert "State-response diagnostic" in md
    assert "anger <-> stress loop stability" in md
    assert "Jury margin" in md
    assert "impulse response" in md
