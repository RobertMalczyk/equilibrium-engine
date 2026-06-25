"""eval/reactivity.py -- which persona is most NEUTRAL (least reactive)?

For each persona, run a sample of day scenarios through the closed seeking loop and measure how much
the NPC actually *reacts*:
  resp_rate   : fraction of forcing events that draw a non-neutral action within 3 ticks
  act_rate    : fraction of ALL ticks that carry a non-neutral action
  mean_stress : average global stress over the run
  peak_anger  : average per-scenario max anger
Lower across the board = more neutral. Deterministic; no LLM.

    PYTHONPATH=. python eval/reactivity.py [N]
"""

from __future__ import annotations

import sys
from pathlib import Path

import eval.mock_world as mw
from engine.yaml_io import load_scenario
from eval.calibrated import believable_day_layout, load_eval_persona_timescale

ROOT = Path(__file__).resolve().parents[1]
PERSONAS = ["halgrim", "wojslaw", "cichy", "branic", "lutek", "welf", "edda"]
DAY_TICKS = believable_day_layout()["day_ticks"]


def _world() -> mw.MockWorld:
    return mw.MockWorld(
        novelty_start=1.0, replenish_per_tick=0.012, work_fraction=0.35, seed=7
    )


def analyse(persona: str, n: int) -> dict:
    cfg = load_eval_persona_timescale(persona)
    tot_ticks = act_ticks = ev_total = ev_resp = 0
    stress_sum = stress_cnt = 0.0
    peak_anger_sum = 0.0
    runs = 0
    for i in range(1, n + 1):
        path = (
            ROOT
            / "eval"
            / "scenarios"
            / "day"
            / persona
            / f"{persona}_day_{i:03d}.yaml"
        )
        if not path.exists():
            continue
        sc = load_scenario(path)
        tr = mw.run_with_world(cfg, sc, _world(), DAY_TICKS)
        ticks = tr.ticks
        runs += 1
        by_t = {tk.t: idx for idx, tk in enumerate(ticks)}
        for tk in ticks:
            tot_ticks += 1
            if tk.selection.action != "neutral":
                act_ticks += 1
            g = tk.state_after_post.global_state
            stress_sum += g.get("stress", 0.0)
            stress_cnt += 1
        peak_anger_sum += max(
            tk.state_after_post.global_state.get("anger", 0.0) for tk in ticks
        )
        for ev in sc.events:
            ev_total += 1
            start = by_t.get(ev.t)
            if start is None:
                continue
            for j in range(start, min(start + 4, len(ticks))):
                if ticks[j].selection.action != "neutral":
                    ev_resp += 1
                    break
    return {
        "persona": persona,
        "runs": runs,
        "resp_rate": ev_resp / ev_total if ev_total else 0.0,
        "act_rate": act_ticks / tot_ticks if tot_ticks else 0.0,
        "mean_stress": stress_sum / stress_cnt if stress_cnt else 0.0,
        "peak_anger": peak_anger_sum / runs if runs else 0.0,
    }


def main() -> None:
    n = int(sys.argv[1]) if len(sys.argv) > 1 and sys.argv[1].isdigit() else 25
    rows = [analyse(p, n) for p in PERSONAS]
    rows.sort(key=lambda r: r["resp_rate"])
    print(f"Reactivity over {n} day scenarios/persona (sorted: most neutral first)\n")
    print(
        f"  {'persona':9} {'resp_rate':>10} {'act_rate':>9} {'mean_stress':>12} {'peak_anger':>11}"
    )
    for r in rows:
        print(
            f"  {r['persona']:9} {r['resp_rate']:>10.1%} {r['act_rate']:>9.1%} "
            f"{r['mean_stress']:>12.3f} {r['peak_anger']:>11.3f}"
        )
    most = rows[0]
    print(f"\nMost neutral (lowest response rate): {most['persona']}")


if __name__ == "__main__":
    main()
