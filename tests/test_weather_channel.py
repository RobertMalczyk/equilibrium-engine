"""The `weather` channel (rain -> frustration + a little stress) -- merge-safety locks.

Guarantee for the merge: the channel is NEUTRAL by default (no/zero weather event -> no effect, so the
frozen goldens are unchanged), and it has the intended effect when present. It is a self/world signal (no
source), so it is not a provocation and opens no reactive reply -- it only sours the baseline mood.
"""

from pathlib import Path

from engine.schema import RawEvent, Scenario
from engine.simulation import run_scenario
from engine.yaml_io import load_persona

ROOT = Path(__file__).resolve().parents[1]
DEFAULTS = ROOT / "calibration" / "defaults.yaml"


def _run(events):
    cfg = load_persona(ROOT / "data" / "personas" / "branic.yaml", DEFAULTS)
    sc = Scenario(
        id="w",
        persona="branic",
        initial_overrides={"global_state": {"frustration": 0.0, "stress": 0.0}},
        events=events,
    )
    _, tr = run_scenario(cfg, sc, n_ticks=8)
    g = tr.ticks[4].state_after_post.global_state
    return g["frustration"], g["stress"]


def test_weather_raises_frustration_and_stress():
    f0, s0 = _run(())
    f1, s1 = _run((RawEvent(type="weather", t=2, intensity=1.0),))
    assert f1 > f0 + 0.05
    assert s1 > s0 + 0.02


def test_weather_intensity_zero_is_inert():
    """Intensity 0 -> channel value 0 -> no effect: bit-identical to no weather at all (neutral by default)."""
    assert _run((RawEvent(type="weather", t=2, intensity=0.0),)) == _run(())
