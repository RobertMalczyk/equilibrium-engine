"""M20.1 step 1 — verify the burst-calibration benchmark scenarios REACH the regions they target,
BEFORE any number is tuned (plan §6/§7 step 1). Runs each benchmark with burst OFF (shipped defaults)
and reports the operating point: the peak each drive reaches and the maximum number of drives
co-elevated at once (the co-occurrence depth). The acceptance for this stage:

  * bad_day_stack  -> a sustained ≥3-way drive coincidence (the burst trigger region);
  * loaded_spring  -> a hot anger operating point capable of a plateau (anger stays high);
  * ordinary_pair  -> stays a 2-way (the negative control: must NOT reach ≥3-way).

This is an INPUT-coincidence check. The spiral/latch itself is calibration's job (k_esc, C1) — here
we only prove the scenarios put the engine where calibration needs it. Deterministic; no LLM.

Run:  PYTHONPATH=. python eval/verify_burst_scenarios.py
"""

from __future__ import annotations

from pathlib import Path

from engine.simulation import run_scenario
from engine.yaml_io import load_scenario
from eval.calibrated import load_eval_persona

ROOT = Path(__file__).resolve().parents[1]

# the drive states whose coincidence the burst cares about (spec §8 loop + its inputs)
DRIVES = ("hunger", "fatigue", "stress", "frustration", "anger")
# "deep coincidence" = a drive sitting in the BAND region where the escalated loop gain actually
# matters (the eval burst demo arms the latch at anger>=0.80 / stress>=0.60). A mild 0.4 elevation is
# the everyday operating point, not the spiral trigger -- so the bar that defines a >=3-way coincidence
# is set at the band level, not at "above neutral".
BAR = 0.60
N_TICKS = 28


def _cfg(persona: str):
    # The CALIBRATED eval stack (layer1+2 + recovery): realistic, BOUNDED operating points that match
    # the day/multiday corpus the burst must not regress. Burst itself stays OFF (no burst overlay
    # loaded). NOT raw load_persona: on the litmus dt hunger+fatigue alone drive stress->1.0 (the D10
    # saturation finding), so every scenario would look like a deep coincidence -- the recovery
    # calibration is exactly what keeps the ordinary pair an honest 2-way.
    return load_eval_persona(persona)


def _measure(persona: str, scenario_id: str) -> dict:
    cfg = _cfg(persona)
    sc = load_scenario(ROOT / "data" / "scenarios" / "burst" / f"{scenario_id}.yaml")
    _, tr = run_scenario(cfg, sc, n_ticks=N_TICKS)
    peaks = {d: 0.0 for d in DRIVES}
    max_depth = 0
    for tk in tr.ticks:
        g = tk.state_after_post.global_state
        depth = 0
        for d in DRIVES:
            v = g.get(d, 0.0)
            peaks[d] = max(peaks[d], v)
            if v >= BAR:
                depth += 1
        max_depth = max(max_depth, depth)
    # how long the engine stays at >= 3 drives co-elevated
    sustained3 = sum(
        1
        for tk in tr.ticks
        if sum(1 for d in DRIVES if tk.state_after_post.global_state.get(d, 0.0) >= BAR)
        >= 3
    )
    anger_peak = peaks["anger"]
    return {
        "persona": persona,
        "scenario": scenario_id,
        "peaks": peaks,
        "max_depth": max_depth,
        "sustained_ge3_ticks": sustained3,
        "anger_peak": anger_peak,
    }


def main() -> None:
    checks = [
        ("wojslaw", "bad_day_stack"),
        ("halgrim", "bad_day_stack"),
        ("branic", "bad_day_stack"),
        ("wojslaw", "loaded_spring"),
        ("wojslaw", "ordinary_pair"),
    ]
    print(f"Burst-OFF operating points (bar={BAR}, {N_TICKS} ticks):\n")
    print(f"{'persona':9} {'scenario':14} depth  sus>=3  anger_pk  peaks")
    rows = []
    for persona, sid in checks:
        r = _measure(persona, sid)
        rows.append(r)
        pk = " ".join(f"{d[:4]}={r['peaks'][d]:.2f}" for d in DRIVES)
        print(
            f"{persona:9} {sid:14} {r['max_depth']:5d}  {r['sustained_ge3_ticks']:5d}  "
            f"{r['anger_peak']:7.2f}  {pk}"
        )

    print("\nAcceptance (step 1 — reach the region, before tuning):")
    ok = True

    def check(name, cond):
        nonlocal ok
        ok = ok and cond
        print(f"  [{'PASS' if cond else 'FAIL'}] {name}")

    bad = next(
        r for r in rows if r["scenario"] == "bad_day_stack" and r["persona"] == "wojslaw"
    )
    check(
        "bad_day_stack reaches a sustained 3+way coincidence",
        bad["max_depth"] >= 3 and bad["sustained_ge3_ticks"] >= 5,
    )
    spring = next(r for r in rows if r["scenario"] == "loaded_spring")
    check(
        "loaded_spring holds a hot anger operating point (plateau-capable)",
        spring["anger_peak"] >= 0.70,
    )
    ordin = next(r for r in rows if r["scenario"] == "ordinary_pair")
    check(
        "ordinary_pair stays a 2-way (negative control: never >=3-way)",
        ordin["max_depth"] <= 2,
    )
    print("\n" + ("ALL CHECKS PASS" if ok else "SOME CHECKS FAILED"))


if __name__ == "__main__":
    main()
