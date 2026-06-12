"""eval/measure_cooccurrence.py — Gate G6: MEASURE the input co-occurrence distribution.

The burst spec (section 8) requires that the stability verification cover the MEASURED frequent
input combinations — which drives actually hit the anger/stress loop together in real play — and
that >=3-way coincidences be accepted as the (bounded) burst trigger. "Which pairs are common" is
data, not assumption: this script runs a sample of the multiday corpus (the same closed-loop
runner the sanity gate uses) and counts, per WAKING tick, which loop drives are simultaneously
active, then reports single/pair/triple+ frequencies.

Drive operationalization (per tick; thresholds below are MEASUREMENT bins, not engine config —
they discretize "this drive is meaningfully pushing the loop" for counting):
  hungry      hunger >= 0.5         (hunger -> stress coupling active at strength)
  tired       fatigue >= 0.5        (fatigue -> stress)
  bored       boredom >= 0.7        (boredom -> frustration -> anger chain)
  provoked    a SOURCED provoking-class event (insult/command) within the reactive window
  weather     a SOURCELESS stressor event (weather) within the same window
  seeking     mode == SEEKING       (the fruitless-looking cost, Loop 2's forward edge)

Run:  PYTHONPATH=. python eval/measure_cooccurrence.py [--per-persona N]
Output: eval/burst_cooccurrence_report.md
"""

from __future__ import annotations

import sys
from collections import Counter
from pathlib import Path

from engine.yaml_io import load_scenario
from eval.calibrated import believable_day_layout, load_eval_persona_timescale
from eval.sanity_multiday import run_multiday

ROOT = Path(__file__).resolve().parents[1]
PERSONAS = ["halgrim", "wojslaw", "cichy", "branic", "lutek", "welf", "edda"]
REPORT = ROOT / "eval" / "burst_cooccurrence_report.md"

# measurement bins (counting discretization, not engine config)
H_HUNGRY, H_TIRED, H_BORED = 0.5, 0.5, 0.7
PROVOKING_TYPES = {"insult", "command"}
STRESSOR_TYPES = {"weather"}


def drives_per_tick(tr, waking: int, day_ticks: int, window: int) -> list[frozenset]:
    out: list[frozenset] = []
    last_prov = None
    last_weather = None
    for tk in tr.ticks:
        t = tk.t
        ev = tk.event
        if ev is not None and ev.source is not None and ev.type in PROVOKING_TYPES:
            last_prov = t
        if ev is not None and ev.source is None and ev.type in STRESSOR_TYPES:
            last_weather = t
        if (t % day_ticks) >= waking:
            continue  # waking hours only: the night reset is not an operating point
        g = tk.state_after_post.global_state
        active = set()
        if g["hunger"] >= H_HUNGRY:
            active.add("hungry")
        if g["fatigue"] >= H_TIRED:
            active.add("tired")
        if g["boredom"] >= H_BORED:
            active.add("bored")
        if last_prov is not None and (t - last_prov) <= window:
            active.add("provoked")
        if last_weather is not None and (t - last_weather) <= window:
            active.add("weather")
        if tk.state_after_post.mode.value == "SEEKING":
            active.add("seeking")
        out.append(frozenset(active))
    return out


def main() -> None:
    per = 3
    if "--per-persona" in sys.argv:
        per = int(sys.argv[sys.argv.index("--per-persona") + 1])
    layout = believable_day_layout()
    day_ticks, waking = layout["day_ticks"], layout["waking_ticks"]

    combo_counts: Counter = Counter()
    order_counts: Counter = Counter()
    total_ticks = 0
    runs = 0
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
            for combo in drives_per_tick(tr, waking, day_ticks, window):
                total_ticks += 1
                order_counts[len(combo)] += 1
                if combo:
                    combo_counts[combo] += 1
            runs += 1
            print(f"  {p} {i:03d}: done ({n_days} day(s))")

    lines = [
        "# G6 — measured input co-occurrence (burst spec section 8)",
        "",
        f"Sample: {runs} multiday corpus runs ({per}/persona, the sanity-gate runner), waking ticks "
        f"only, n = {total_ticks} tick-observations. Drive bins documented in "
        "`eval/measure_cooccurrence.py` (measurement discretization, not engine config).",
        "",
        "## How many loop drives coincide per tick",
        "",
        "| simultaneous drives | ticks | share |",
        "|---|---|---|",
    ]
    for k in sorted(order_counts):
        n = order_counts[k]
        lines.append(f"| {k} | {n} | {n / total_ticks:.1%} |")
    lines += [
        "",
        "## Most frequent combinations (the ones the stability verification must cover)",
        "",
        "| combination | ticks | share |",
        "|---|---|---|",
    ]
    for combo, n in combo_counts.most_common(15):
        lines.append(f"| {' + '.join(sorted(combo))} | {n} | {n / total_ticks:.1%} |")
    n3 = sum(n for k, n in order_counts.items() if k >= 3)
    lines += [
        "",
        f"**>=3-way coincidences: {n3} ticks ({n3 / total_ticks:.2%}).** Per the spec these are the",
        "accepted rare-risk region: when they push the escalated loop past linear stability, that IS",
        "the burst, and saturation + the latch bound it by construction. The PAIRS above are the",
        "operating points the k_esc calibration must verify linear stability at.",
        "",
    ]
    REPORT.write_text("\n".join(lines), encoding="utf-8")
    print(f"\nreport -> {REPORT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
