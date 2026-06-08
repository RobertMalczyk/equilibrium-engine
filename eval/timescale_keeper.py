"""eval/timescale_keeper.py -- a PURE DEV TOOL: does the persona's time make sense?

Measures each persona-dynamics phenomenon's actual real-world duration and checks it against the
human-set GROUND TRUTH (`calibration/timescale_ground_truth.yaml`). Reports PASS/FAIL per phenomenon and,
on FAIL, the rough constant change that would fix it. Touches NO engine/runtime path and mutates no state;
it only loads configs and runs throwaway probes. Use it to verify a believable day after changing time
constants (the "time-scale keeper" milestone).

Measurement kinds:
  halflife      -- a fast emotion's fade time == its half-life in game-seconds (read straight off config).
  time_to_state -- an accumulator's rise to a level: the ISOLATED single-state drift dynamics
                   x_{t+1}=decay*x_t+drift (decay=2^(-dt/HL)), solved analytically (no rest-drive confound).
  time_to_seek  -- run the engine idle from boredom 0 and find the first tick it enters SEEKING.
  night         -- inject a nightfall and measure how long it stays in SLEEP (nightfall -> wake).
  giveup        -- the seeking timeout (ticks) x dt.

Run:  PYTHONPATH=. python eval/timescale_keeper.py            # current eval dynamics
      PYTHONPATH=. python eval/timescale_keeper.py --believable   # + the calibrated_timescale layer
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

import yaml

from engine.schema import Mode, RawEvent, Scenario
from engine.simulation import run_scenario
from eval.calibrated import load_eval_persona

ROOT = Path(__file__).resolve().parents[1]
GT = ROOT / "calibration" / "timescale_ground_truth.yaml"


def _fmt(s: float) -> str:
    if s == math.inf:
        return "  never"
    if s < 90:
        return f"{s:5.0f}s"
    if s < 5400:
        return f"{s / 60:5.1f}m"
    return f"{s / 3600:5.1f}h"


def _decay(dt: float, hl: float) -> float:
    return 2.0 ** (-dt / hl)


def time_to_state(cfg, state: str, level: float) -> float:
    """Seconds for an accumulator to rise from 0 to `level` under its isolated drift+decay (setpoint 0)."""
    dt = cfg.dt
    hl = cfg.half_lives[state]
    drift = cfg.drifts.get(state, 0.0)
    if drift <= 0:
        return math.inf
    decay = _decay(dt, hl)
    x_star = drift / (1.0 - decay)  # asymptote
    if level >= x_star:
        return math.inf  # never reaches the level
    t = math.log(1.0 - level / x_star) / math.log(decay)
    return t * dt


def time_to_seek(cfg) -> float:
    """Run idle from boredom 0 (fatigue 0 so the brake/rest don't interfere) and find the first SEEKING tick."""
    sc = Scenario(
        id="probe_seek",
        persona=cfg.id,
        initial_overrides={
            "global_state": {
                "boredom": 0.0,
                "fatigue": 0.0,
                "hunger": 0.0,
                "stress": 0.0,
                "anger": 0.0,
                "frustration": 0.0,
            }
        },
        events=(),
    )
    _, tr = run_scenario(cfg, sc, n_ticks=20000)
    for tk in tr.ticks:
        if tk.state_after_post.mode == Mode.SEEKING:
            return tk.t * cfg.dt
    return math.inf


def night_length(cfg) -> float:
    """Inject a nightfall into a calm persona and measure the SLEEP span (nightfall -> wake)."""
    sc = Scenario(
        id="probe_night",
        persona=cfg.id,
        initial_overrides={
            "global_state": {
                "fatigue": 0.5,
                "anger": 0.0,
                "stress": 0.0,
                "frustration": 0.0,
                "boredom": 0.0,
            }
        },
        events=(RawEvent(type="nightfall", t=2, intensity=1.0),),
    )
    _, tr = run_scenario(cfg, sc, n_ticks=20000)
    sleep_ticks = [tk.t for tk in tr.ticks if tk.state_after_post.mode == Mode.SLEEP]
    return (sleep_ticks[-1] - sleep_ticks[0] + 1) * cfg.dt if sleep_ticks else 0.0


def giveup(cfg) -> float:
    return cfg.thresholds.get("seeking_timeout_ticks", 20) * cfg.dt


def measure(cfg, name: str, spec: dict) -> float:
    how = spec["how"]
    if how == "halflife":
        return cfg.half_lives[spec["state"]]
    if how == "time_to_state":
        return time_to_state(cfg, spec["state"], spec["level"])
    if how == "time_to_seek":
        return time_to_seek(cfg)
    if how == "night":
        return night_length(cfg)
    if how == "giveup":
        return giveup(cfg)
    raise ValueError(how)


def run(believable: bool):
    gt = yaml.safe_load(GT.read_text(encoding="utf-8"))
    persona = gt["reference_persona"]
    if believable:
        # the believable per-dimension constants (built in calibration/calibrated_timescale.yaml)
        from eval.calibrated import (
            load_eval_persona_timescale,  # lazy: only when the layer exists
        )

        cfg = load_eval_persona_timescale(persona)
    else:
        cfg = load_eval_persona(persona)
    print(
        f"time-scale keeper -- reference persona '{persona}'  (dt={cfg.dt:.1f}s, "
        f"a 24 h day = {round(86400 / cfg.dt)} ticks){'  [believable layer]' if believable else '  [current eval]'}\n"
    )
    print(f"  {'phenomenon':22} {'actual':>7}  {'target':>7}   verdict   note")
    n_pass = 0
    for name, spec in gt["phenomena"].items():
        actual = measure(cfg, name, spec)
        target = spec["target_s"]
        tol = spec["tol"]
        lo, hi = target * (1 - tol), target * (1 + tol)
        ok = lo <= actual <= hi
        n_pass += ok
        verdict = " ok " if ok else ("TOO FAST" if actual < lo else "TOO SLOW")
        print(
            f"  {name:22} {_fmt(actual):>7}  {_fmt(target):>7}   {verdict:8}  {spec['note']}"
        )
    print(f"\n  {n_pass}/{len(gt['phenomena'])} within tolerance.")


if __name__ == "__main__":
    run("--believable" in sys.argv)
