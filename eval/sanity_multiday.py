"""eval/sanity_multiday.py -- automated GENERAL-sanity gate over the multi-day corpus.

Runs multi-day scenarios (load_eval_persona_timescale + the standard mock-world, per-dawn world reset) and
checks that the model BEHAVES SENSIBLY over many days at the believable timescale -- NOT that personas
differ (proven elsewhere). The deterministic half of "does the output make sense":

  clamped        every state in [0,1] every tick, no NaN
  hunger_sane    not "starving in minutes" (hunger still low early) AND he actually gets fed (hunger is
                 cut below ~0.5 at some point -- meals work), and never pegged at the ceiling all run
  sleeps         every night has a SLEEP stretch
  night_reset    the fast temper drains overnight (each night's anger trough is low)
  not_saturated  stress is not pegged near 1.0 for most of the run (no runaway loop)
  recovers       he is calm by most dawns (the day's heat didn't accumulate without bound)
  not_stuck      he is not frozen in a single mode the whole run

Per scenario -> a pass/fail per check; aggregate pass-rates per persona + the worst offenders. This is the
hard gate; a per-scenario fresh-agent JUDGE (eval/judge_multiday_render.py) adds the "reads believably / not
wrong for the persona" half.

Run:  PYTHONPATH=. python eval/sanity_multiday.py            # sample
      PYTHONPATH=. python eval/sanity_multiday.py --all       # all 700 (slow)
"""

from __future__ import annotations

import sys
from collections import Counter, defaultdict
from pathlib import Path

from engine.debug import DebugTrace
from engine.runtime import init_runtime
from engine.schema import Mode
from engine.simulation import tick
from engine.yaml_io import load_scenario
from eval.calibrated import believable_day_layout, load_eval_persona_timescale
from eval.render_narration import _world

ROOT = Path(__file__).resolve().parents[1]
PERSONAS = ["halgrim", "wojslaw", "cichy", "branic", "lutek", "welf", "edda"]
_L = believable_day_layout()
DAY_TICKS, WAKING = _L["day_ticks"], _L["waking_ticks"]
CHECKS = [
    "clamped",
    "hunger_sane",
    "sleeps",
    "night_reset",
    "not_saturated",
    "recovers",
    "not_stuck",
]


def run_multiday(cfg, scenario, n_days):
    """Closed seeking loop with a per-DAWN world reset (each day a comparable, fresh day)."""
    world = _world()
    runtime = init_runtime(cfg, scenario.initial_overrides)
    base = {ev.t: ev for ev in scenario.events}
    world.reset()
    tr = DebugTrace(persona=cfg.id, scenario=scenario.id, dt=cfg.dt)
    for t in range(n_days * DAY_TICKS):
        if t > 0 and t % DAY_TICKS == 0:
            world.reset()
        ev = base.get(t)
        if ev is None and runtime.mode == Mode.SEEKING:
            ev = world.offer(t, runtime.seeking_since)
        tr.emit(tick(runtime, t, ev))
        if runtime.mode not in (Mode.SEEKING, Mode.BUSY):
            world.replenish()
    return tr


def evaluate(tr, n_days) -> dict:
    ticks = tr.ticks
    G = [tk.state_after_post.global_state for tk in ticks]
    modes = [tk.state_after_post.mode for tk in ticks]

    # clamped + no NaN
    clamped = all(0.0 <= v <= 1.0 and v == v for g in G for v in g.values())

    # hunger: no STARVING-IN-MINUTES (hunger must not SPIKE early -- a persona may legitimately START mildly
    # hungry, but it can't rocket), he actually gets fed (cut below ~0.5 sometime -> meals work), never pegged
    hunger = [g["hunger"] for g in G]
    no_spike = (max(hunger[:16]) - hunger[0]) < 0.12 and hunger[
        0
    ] < 0.70  # ~30 min: gentle rise, not starving
    fed = min(hunger) < 0.50  # meals actually cut hunger
    not_pegged = sum(1 for h in hunger if h > 0.97) < 0.30 * len(hunger)
    hunger_sane = no_spike and fed and not_pegged

    # per-day windows
    def day_win(d):
        return [
            i
            for i in range(len(ticks))
            if d * DAY_TICKS <= ticks[i].t < (d + 1) * DAY_TICKS
        ]

    sleeps = all(any(modes[i] == Mode.SLEEP for i in day_win(d)) for d in range(n_days))
    night_troughs = []
    for d in range(n_days):
        night = [
            G[i]["anger"] for i in day_win(d) if ticks[i].t >= d * DAY_TICKS + WAKING
        ]
        if night:
            night_troughs.append(min(night))
    night_reset = bool(night_troughs) and max(night_troughs) < 0.25

    stress = [g["stress"] for g in G]
    not_saturated = (sum(1 for s in stress if s > 0.98) < 0.15 * len(stress)) and (
        sum(stress) / len(stress) < 0.80
    )

    # recovers: most dawns calm (anger low at the first tick of each day after the first)
    dawn_anger = [G[day_win(d)[0]]["anger"] for d in range(1, n_days)] or [0.0]
    recovers = sum(1 for a in dawn_anger if a < 0.35) >= 0.6 * len(dawn_anger)

    # not stuck in one mode (sleep is expected ~25-35%, but he should also be awake-active)
    mc = Counter(modes)
    top = mc.most_common(1)[0][1] / len(modes)
    not_stuck = len(mc) >= 2 and top < 0.92

    return {
        "clamped": clamped,
        "hunger_sane": hunger_sane,
        "sleeps": sleeps,
        "night_reset": night_reset,
        "not_saturated": not_saturated,
        "recovers": recovers,
        "not_stuck": not_stuck,
        "_vals": {
            "stress_mean": round(sum(stress) / len(stress), 2),
            "hunger_min": round(min(hunger), 2),
            "hunger_early": round(max(hunger[:6]), 2),
            "night_trough_max": round(max(night_troughs), 2) if night_troughs else None,
        },
    }


def main():
    import yaml

    do_all = "--all" in sys.argv
    burst = "--burst" in sys.argv  # arm the M20.1 outburst overlay (opt-in; default off = unchanged)
    n_per = 100 if do_all else 10
    cfgs = {p: load_eval_persona_timescale(p, burst=burst) for p in PERSONAS}
    print(
        f"Multi-day sanity over {n_per}/persona ({n_per * 7} scenarios), believable timescale "
        f"(dt={cfgs['branic'].dt:.0f}s, {DAY_TICKS} ticks/day){', OUTBURST ARMED' if burst else ''}.\n"
    )
    agg = {
        c: defaultdict(lambda: [0, 0]) for c in CHECKS
    }  # check -> persona -> [pass, total]
    failures = []
    for p in PERSONAS:
        for i in range(1, n_per + 1):
            path = (
                ROOT / "eval" / "scenarios" / "multiday" / p / f"{p}_multi_{i:03d}.yaml"
            )
            sc = load_scenario(path)
            n_days = len(yaml.safe_load(path.read_text(encoding="utf-8"))["day_plan"])
            res = evaluate(run_multiday(cfgs[p], sc, n_days), n_days)
            for c in CHECKS:
                a = agg[c][p]
                a[1] += 1
                a[0] += 1 if res[c] else 0
            bad = [c for c in CHECKS if not res[c]]
            if bad:
                failures.append((sc.id, bad, res["_vals"]))
    # report
    print(f"  {'persona':9} " + " ".join(f"{c[:9]:>10}" for c in CHECKS))
    for p in PERSONAS:
        cells = []
        for c in CHECKS:
            pa, to = agg[c][p]
            cells.append(f"{100 * pa // to:>9}%")
        print(f"  {p:9} " + " ".join(cells))
    tot = {
        c: [sum(agg[c][p][0] for p in PERSONAS), sum(agg[c][p][1] for p in PERSONAS)]
        for c in CHECKS
    }
    print(
        f"  {'ALL':9} "
        + " ".join(f"{100 * tot[c][0] // tot[c][1]:>9}%" for c in CHECKS)
    )
    print(f"\n  {len(failures)} scenario(s) failed >=1 check.")
    for sid, bad, vals in failures[:25]:
        print(f"    {sid}: {', '.join(bad)}   {vals}")


if __name__ == "__main__":
    main()
