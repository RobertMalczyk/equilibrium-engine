"""M20.1 C1 — measure the (anger, stress) OPERATING POINTS per coincidence depth.

The G6 report (eval/measure_cooccurrence.py) counts WHICH drives coincide; the k_esc feasibility
frontier (plan §4 C1) needs the actual loop-state operating points (anger*, stress*) at those
coincidences, because the escalated local gain is g*(1 + k_esc*y) evaluated at y*. This script reuses
the same corpus sample and the same drive bins, but records, per waking tick, the coincidence DEPTH
together with (anger, stress), then reports:

  * the <=2-way ENVELOPE  -- the binding stable operating point (high percentile of anger & stress
    among the frequent <=2-way ticks): k_esc must keep the escalated Jury margin >= 0 HERE;
  * the >=3-way operating points -- the rare region the burst is allowed to (and must, for G6*) cross.

Burst is OFF in the corpus, so these are the linear-loop operating points the local-gain argument
linearizes around (the known multi-operating-point method limit, recorded in spec §8). Deterministic.

Run:  PYTHONPATH=. python eval/measure_operating_points.py [--per-persona N]
Output: eval/burst_operating_points.md  (and prints the envelope used by calibrate_burst.py)
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from engine.yaml_io import load_scenario
from eval.calibrated import believable_day_layout, load_eval_persona_timescale
from eval.measure_cooccurrence import PERSONAS, drives_per_tick
from eval.sanity_multiday import run_multiday

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "eval" / "burst_operating_points.md"
DATA = ROOT / "eval" / "burst_operating_points.json"  # consumed by calibrate_burst.py


def _percentile(xs: list[float], q: float) -> float:
    if not xs:
        return 0.0
    s = sorted(xs)
    # nearest-rank percentile (deterministic, no interpolation surprises)
    k = max(0, min(len(s) - 1, int(round(q * (len(s) - 1)))))
    return s[k]


def main() -> None:
    per = 3
    if "--per-persona" in sys.argv:
        per = int(sys.argv[sys.argv.index("--per-persona") + 1])
    layout = believable_day_layout()
    day_ticks, waking = layout["day_ticks"], layout["waking_ticks"]

    le2 = {"anger": [], "stress": []}  # <=2-way ticks
    ge3 = {"anger": [], "stress": []}  # >=3-way ticks
    n_le2 = n_ge3 = 0
    for p in PERSONAS:
        cfg = load_eval_persona_timescale(p)
        window = int(cfg.thresholds.get("reactive_window_ticks", 10))
        for i in range(1, per + 1):
            path = (
                ROOT / "eval" / "scenarios" / "multiday" / p / f"{p}_multi_{i:03d}.yaml"
            )
            if not path.exists():
                continue
            sc = load_scenario(path)
            n_days = int(sc.events[-1].t // day_ticks) + 1 if sc.events else 1
            tr = run_multiday(cfg, sc, n_days)
            combos = drives_per_tick(tr, waking, day_ticks, window)
            # re-walk waking ticks in the SAME order drives_per_tick used, to align (anger,stress)
            waking_states = [
                tk.state_after_post.global_state
                for tk in tr.ticks
                if (tk.t % day_ticks) < waking
            ]
            for combo, g in zip(combos, waking_states):
                bucket = ge3 if len(combo) >= 3 else le2
                bucket["anger"].append(g["anger"])
                bucket["stress"].append(g["stress"])
                if len(combo) >= 3:
                    n_ge3 += 1
                else:
                    n_le2 += 1
            print(f"  {p} {i:03d}: done")

    # the binding <=2-way envelope: a high percentile of EACH loop state among frequent ticks. We use
    # the 99th percentile (robust to a stray tick) as the "worst frequent operating point" the loop
    # must remain linearly stable at.
    env = {
        "le2_anger_p99": _percentile(le2["anger"], 0.99),
        "le2_stress_p99": _percentile(le2["stress"], 0.99),
        "le2_anger_max": max(le2["anger"], default=0.0),
        "le2_stress_max": max(le2["stress"], default=0.0),
        "ge3_anger_p50": _percentile(ge3["anger"], 0.50),
        "ge3_stress_p50": _percentile(ge3["stress"], 0.50),
        "ge3_anger_max": max(ge3["anger"], default=0.0),
        "ge3_stress_max": max(ge3["stress"], default=0.0),
        "n_le2": n_le2,
        "n_ge3": n_ge3,
    }
    DATA.write_text(json.dumps(env, indent=2), encoding="utf-8")

    lines = [
        "# M20.1 C1 — measured loop operating points per coincidence depth",
        "",
        f"Corpus sample: {per}/persona, waking ticks. n(<=2-way)={n_le2}, n(>=3-way)={n_ge3}. "
        "Burst OFF (linear-loop operating points; the local-gain argument linearizes around these).",
        "",
        "| set | anger p99 | stress p99 | anger max | stress max |",
        "|---|---|---|---|---|",
        f"| <=2-way (must stay stable) | {env['le2_anger_p99']:.3f} | {env['le2_stress_p99']:.3f} "
        f"| {env['le2_anger_max']:.3f} | {env['le2_stress_max']:.3f} |",
        "",
        "| set | anger p50 | stress p50 | anger max | stress max |",
        "|---|---|---|---|---|",
        f"| >=3-way (burst-allowed) | {env['ge3_anger_p50']:.3f} | {env['ge3_stress_p50']:.3f} "
        f"| {env['ge3_anger_max']:.3f} | {env['ge3_stress_max']:.3f} |",
        "",
        "The <=2-way p99 (anger*, stress*) is the BINDING stable operating point: k_esc is chosen so",
        "the escalated 2-cycle Jury margin stays >= 0 there (with a safety fraction). The >=3-way",
        "points are where the burst is allowed to cross. Consumed by calibration/calibrate_burst.py.",
        "",
    ]
    REPORT.write_text("\n".join(lines), encoding="utf-8")
    print(f"\nreport -> {REPORT.relative_to(ROOT)}")
    print(f"data   -> {DATA.relative_to(ROOT)}")
    print("\nbinding <=2-way envelope (p99):", json.dumps(env, indent=2))


if __name__ == "__main__":
    main()
