"""eval/moral_multiday.py -- M-J.4.4 full-corpus stage: the MULTI-DAY moral runner.

The short litmus scenarios cannot discriminate the moral HALF-LIVES (over ~48s a 12h vs 72h half-life barely
differ). The half-life calibration only shows over MULTI-DAY arcs at the believable timescale (does a serious
wrong still weigh on a man days later?). This runner builds a multi-day moral arc on the believable day
layout (eval.calibrated) and reports the lingering trajectory of a moral state -- the signal the blind judge
(and the §10 objective) score for curve_plausibility.

Verified finding (see docs/moral_calibration_plan.md): with PRIVATE wrongdoing-reminders (no interrogation,
so no confession resolves it), the evening-guilt trajectory cleanly separates by half-life --
6h ~ [0.04, 0.05, 0.05] (forgotten by evening), 18h ~ [0.15, 0.21, 0.23], 72h ~ [0.23, 0.42, 0.56] (a
deepening burden). That separation IS the multi-day calibration signal.
"""

from __future__ import annotations

from pathlib import Path

from engine.schema import RawEvent, Scenario
from engine.simulation import run_scenario
from engine.yaml_io import _deep_merge, load_persona
from eval.calibrated import _merge, believable_day_layout, timescale_overrides
from eval.moral import moral_overrides

ROOT = Path(__file__).resolve().parents[1]
DEFAULTS = ROOT / "calibration" / "defaults.yaml"
HALGRIM = ROOT / "data" / "personas" / "halgrim.yaml"
_L = believable_day_layout()
DAY_TICKS, WAKING = _L["day_ticks"], _L["waking_ticks"]


def _cfg(traits: dict, half_life_overrides: dict | None = None):
    ov = _merge(timescale_overrides(), moral_overrides(traits))
    if half_life_overrides:
        ov = _deep_merge(ov, {"half_lives": half_life_overrides})
    return load_persona(HALGRIM, DEFAULTS, param_overrides=ov)


def reminder_arc(traits: dict, half_lives: dict, n_days: int = 3):
    """A multi-day arc: a PRIVATE wrongdoing-reminder each morning (a SELF cue -- raises guilt, opens no reply
    window, so nothing resolves it) + nightfall each evening. Returns (cfg, trace)."""
    ev: list[RawEvent] = []
    for d in range(n_days):
        ev.append(RawEvent(type="wrongdoing", t=d * DAY_TICKS + 8, intensity=1.0))
        ev.append(RawEvent(type="nightfall", t=d * DAY_TICKS + WAKING, intensity=1.0))
    cfg = _cfg(traits, half_lives)
    sc = Scenario(
        id="md_moral", persona="halgrim", initial_overrides={}, events=tuple(ev)
    )
    return cfg, run_scenario(cfg, sc, n_ticks=n_days * DAY_TICKS)[1]


def evening_guilt(traits: dict, guilt_half_life: int, n_days: int = 3) -> list[float]:
    """The lingering-guilt signal: guilt read each evening (just before nightfall) over n_days."""
    _, tr = reminder_arc(traits, {"guilt": guilt_half_life}, n_days)
    return [
        round(
            tr.ticks[d * DAY_TICKS + WAKING - 30].state_after_post.global_state[
                "guilt"
            ],
            3,
        )
        for d in range(n_days)
    ]


if __name__ == "__main__":
    traits = {"guilt_proneness": 0.9, "honesty_humility": 0.9}
    for hl, lbl in [(21600, "6h"), (64800, "18h"), (259200, "72h")]:
        print(f"{lbl:>4}: evening guilt by day = {evening_guilt(traits, hl)}")
