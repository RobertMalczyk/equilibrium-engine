"""eval/verify_burst_overlay.py — wire-up smoke check for the M20.1 burst overlay (plan step 4).

Runs the NAMED acceptance target cichy_multi_060 (the relentless same-source insult cluster) with the
burst overlay OFF vs ON and prints the reaction at every insult. It is a DIAGNOSTIC, not a gate.

FINDING (2026-06-13) + RESOLUTION (2026-06-14, design clarification): the overlay does NOT make
cichy_multi_060 vent, and under the corrected philosophy THAT IS CORRECT, not a regression. A relentless
same-source insult cluster is ONE positive-feedback loop (provocation), individually stable — and a
single stable loop must NOT trip the vent. The vent is a STABILITY SAFETY VALVE for the un-certifiable
COMBINATION of several UNRELATED loops (insult AND rain AND hunger AND a barren day), not a per-loop
feature. So cichy correctly stays bounded WITHOUT venting; the cluster reaches anger~0.74/stress~0.57,
below the band, exactly as a single stable loop should.

The earlier framing of cichy_multi_060 as "the burst acceptance target" was therefore mis-aimed and is
RETIRED. The real vent criterion is now in eval/verify_vent_boundedness.py: silent on a single/ordinary
load, fires + self-terminates on a genuine >=3-way coincidence, whole corpus stays bounded.

REMAINING (separate from the vent): the same-provoker REPETITION texture ("re-shouts at the same guard")
is an expression concern handled by the latched-provoker refractory edge, which must be DECOUPLED from
the vent latch (fire on sustained anger + resentment[src], independent of the saturation latch a single
loop never reaches). See [[m20-1-outburst-calibration-plan]].

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
        out.append(
            (ev.t, tk.selection.action, g["anger"], g["stress"], tk.burst_latched)
        )
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
