"""Invariant (spec section 1): equation/summation order must NOT change the result. The
engine sorts keys before summing couplings/gains, so reordering config dict keys yields a
bit-identical trace.
"""

import dataclasses
from pathlib import Path

from engine.simulation import run_scenario
from engine.yaml_io import load_persona, load_scenario

ROOT = Path(__file__).resolve().parents[1]
DEFAULTS = ROOT / "calibration" / "defaults.yaml"


def _reverse_nested(d):
    return {k: dict(reversed(list(v.items()))) for k, v in reversed(list(d.items()))}


def test_coupling_key_order_does_not_change_trace():
    cfg = load_persona(ROOT / "data" / "personas" / "halgrim.yaml", DEFAULTS)
    sc = load_scenario(ROOT / "data" / "scenarios" / "same_soup_good_day.yaml")

    base = run_scenario(cfg, sc)[1].to_json()

    shuffled = dataclasses.replace(
        cfg,
        couplings=_reverse_nested(cfg.couplings),
        gains=_reverse_nested(cfg.gains),
    )
    other = run_scenario(shuffled, sc)[1].to_json()

    assert base == other
