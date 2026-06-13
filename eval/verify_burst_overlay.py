"""eval/verify_burst_overlay.py — wire-up smoke check for the M20.1 burst overlay (plan step 4).

Runs the NAMED acceptance target cichy_multi_060 (the relentless same-source insult cluster) with the
burst overlay OFF vs ON and prints the reaction at every insult. It is a DIAGNOSTIC, not a gate.

FINDING (2026-06-13, step 4 wire-up): the overlay as calibrated does NOT yet fix cichy_multi_060 — it
regresses it. The relentless cluster drives ANGER (peaks ~0.74) but only modestly drives STRESS
(~0.57); the calibrated latch band (enter anger>=0.80 AND stress>=0.60, anchored ABOVE the frequent
<=2-way envelope in C3) is therefore NEVER reached DURING the cluster, so the latch does not arm there
-> the refractory edge / extinction / displacement never engage in the cluster, while the k_esc
escalation alone lifts every insult's anger to ~0.70 and turns MORE of them into full outbursts.

This is a TOPOLOGY gap, not a tuning task (CLAUDE.md: a qualitative bug present at every weight is a
topology fix): a relentless single-source provocation cluster does not saturate the anger<->stress loop
the latch keys on. Resolution options (a design decision, NOT silently tuned here): (a) give relentless
same-source provocation a stress/resentment accumulation path that lifts it into the band; (b) arm the
refractory brake on sustained high anger + high resentment[src] (the relentless-resented-provoker
signature) rather than the stress-saturation latch; (c) decouple the refractory gate from the burst
latch. See [[m20-1-outburst-calibration-plan]].

Run:  PYTHONPATH=. python eval/verify_burst_overlay.py
"""

from __future__ import annotations

from pathlib import Path

import yaml

from eval.calibrated import load_eval_persona_timescale
from eval.sanity_multiday import load_scenario, run_multiday

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "eval" / "scenarios" / "multiday" / "cichy" / "cichy_multi_060.yaml"


def _reactions(burst: bool) -> list[tuple[int, str, float, float, bool]]:
    n_days = len(yaml.safe_load(TARGET.read_text(encoding="utf-8"))["day_plan"])
    sc = load_scenario(TARGET)
    cfg = load_eval_persona_timescale("cichy", burst=burst)
    tr = run_multiday(cfg, sc, n_days)
    by_t = {tk.t: tk for tk in tr.ticks}
    out = []
    for ev in sc.events:
        if ev.type != "insult":
            continue
        tk = by_t.get(ev.t)
        if tk is None:
            continue
        g = tk.state_after_post.global_state
        out.append((ev.t, tk.selection.action, g["anger"], g["stress"], tk.burst_latched))
    return out


def main() -> None:
    for label, burst in (("BURST OFF", False), ("BURST ON", True)):
        print(f"\n--- cichy_multi_060 · {label} ---")
        n_out = 0
        for t, act, a, s, lat in _reactions(burst):
            n_out += act == "outburst"
            print(f"  t={t:5d}  {act:18s} anger={a:.2f} stress={s:.2f} latched={lat}")
        print(f"  => {n_out} outbursts")


if __name__ == "__main__":
    main()
