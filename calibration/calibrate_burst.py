"""M20.1 burst calibration — staged, deterministic, provenance-tracked (plan §4).

STAGE C1 (this file, so far): the k_esc feasibility frontier. Reads the frozen Layer-2 loop
(couplings + decays) and the MEASURED operating-point envelope (eval/burst_operating_points.json,
produced by eval/measure_operating_points.py) and chooses the per-edge escalation k_esc analytically:

  escalated 2-cycle Jury margin at (a*, s*):
      margin(k) = (1-d_s)(1-d_a) - g_as*(1+k*a*) * g_sa*(1+k*s*)
  stable iff margin >= 0. The escalation product (1+k*a*)(1+k*s*) may grow up to
      R = (1-d_s)(1-d_a) / (g_as*g_sa)
  before the loop goes locally unstable (the spiral = the burst).

KEY MEASURED FINDING (C1): the corpus >=3-way coincidences do NOT reach a higher (anger, stress)
operating point than the frequent <=2-way ones — BOTH top out near anger~0.70 / stress~0.52. So k_esc
CANNOT gate the burst on "coincidence count": there is no (anger,stress) threshold separating triples
from pairs. This is the plan §8 feasibility tension, now measured. Resolution (topology-now rule):
k_esc is set so the loop stays linearly stable across the ENTIRE observed operating envelope (every
frequent pair, up to the observed max) and only spirals once BOTH states are pushed into the
SATURATION BAND above that envelope (anger>=0.80, stress>=0.60). The latch band thresholds (stage C3)
therefore carry the "rare and earned" selectivity; k_esc only supplies the in-band spiral.

  feasible window:  k_lo = smallest k that spirals at the band entry (BAND_ENTRY)
                    k_hi = largest k that keeps the MAX observed frequent pair stable
  choice: the low end of the window (max stability margin at the frequent operating points).

Deterministic; no optimizer needed (closed-form). Run:
  PYTHONPATH=. python eval/measure_operating_points.py   # produce the envelope first
  PYTHONPATH=. python calibration/calibrate_burst.py     # choose k_esc, write calibrated_burst.yaml
"""

from __future__ import annotations

import json
from pathlib import Path

import yaml

from eval.calibrated import load_eval_persona

ROOT = Path(__file__).resolve().parents[1]
ENV_JSON = ROOT / "eval" / "burst_operating_points.json"
OUT = ROOT / "calibration" / "calibrated_burst.yaml"

# the saturation band the latch will sit on (stage C3 will pin these; C1 uses them as the spiral
# target). Chosen just ABOVE the measured frequent-pair ceiling (anger max ~0.70, stress max ~0.53).
BAND_ENTRY = {"anger": 0.80, "stress": 0.60}


def _loop_constants():
    c = load_eval_persona(
        "wojslaw"
    )  # couplings/decays are persona-independent (frozen Layer-2)
    d = c.decay
    g_as = c.couplings["stress"]["anger"]  # anger -> stress
    g_sa = c.couplings["anger"]["stress"]  # stress -> anger
    bound = (1.0 - d["stress"]) * (1.0 - d["anger"])
    return bound, g_as, g_sa, d


def _factor(a: float, s: float, k: float) -> float:
    return (1.0 + k * a) * (1.0 + k * s)


def _k_for_factor(a: float, s: float, target: float) -> float:
    """Smallest k>=0 with (1+k a)(1+k s) = target. Solve the quadratic k^2(a s)+k(a+s)+(1-target)=0."""
    A, B, C = a * s, a + s, 1.0 - target
    disc = B * B - 4 * A * C
    return (-B + disc**0.5) / (2 * A)


def solve_c1() -> dict:
    bound, g_as, g_sa, d = _loop_constants()
    R = bound / (g_as * g_sa)  # max escalation factor before instability
    env = json.loads(ENV_JSON.read_text(encoding="utf-8"))

    # k_hi: keep the MAX observed frequent (<=2-way) pair linearly stable.
    a_pair, s_pair = env["le2_anger_max"], env["le2_stress_max"]
    k_hi = _k_for_factor(a_pair, s_pair, R)
    # k_lo: spiral at the saturation-band entry.
    k_lo = _k_for_factor(BAND_ENTRY["anger"], BAND_ENTRY["stress"], R)

    # choose the LOW end of [k_lo, k_hi] (max stability margin at the frequent operating points),
    # rounded to 2 dp toward the stable side. If the window is empty/inverted, flag it.
    feasible = k_lo <= k_hi
    import math

    k = (
        math.floor(k_lo * 100 + 0.5) / 100
    )  # round k_lo to 2dp; it already spirals at the band
    if k < k_lo:  # rounding dipped below the spiral floor -> nudge up one step
        k += 0.01
    if k > k_hi:
        k = round((k_lo + k_hi) / 2, 2)

    return {
        "bound": bound,
        "g_as": g_as,
        "g_sa": g_sa,
        "R": R,
        "pair": (a_pair, s_pair),
        "k_lo": k_lo,
        "k_hi": k_hi,
        "feasible": feasible,
        "k": k,
        "env": env,
    }


def write_yaml(res: dict) -> None:
    k = res["k"]
    prov = (
        f"C1 feasibility frontier (calibration/calibrate_burst.py). Frozen Layer-2: "
        f"bound=(1-d_s)(1-d_a)={res['bound']:.6f}, g_as*g_sa={res['g_as'] * res['g_sa']:.6f}, "
        f"max escalation factor R={res['R']:.4f}. Measured envelope "
        f"(eval/burst_operating_points.json): max frequent <=2-way pair "
        f"(anger={res['pair'][0]:.3f}, stress={res['pair'][1]:.3f}); >=3-way operating points do NOT "
        f"exceed the pair ceiling, so k_esc cannot gate on coincidence count (the latch band does). "
        f"Feasible window [k_lo={res['k_lo']:.3f} (spiral at band entry "
        f"anger>={BAND_ENTRY['anger']}/stress>={BAND_ENTRY['stress']}), "
        f"k_hi={res['k_hi']:.3f} (max observed pair stays stable)]; chose the low end for max "
        f"stability margin at the frequent operating points."
    )
    doc = {
        "layer": "burst (M20.1)",
        "reads_on_top_of": (
            "calibrated_layer2.yaml + calibrated_recovery.yaml + defaults.yaml (all untouched)"
        ),
        "anchor": (
            "the frozen Layer-2 2-cycle Jury bound + the measured corpus operating-point envelope; "
            "every burst number is expressed RELATIVE to these, none chosen by hand"
        ),
        "free_set": [
            "coupling_escalation.anger.stress",
            "coupling_escalation.stress.anger",
        ],
        "calibrated": {
            "coupling_escalation.anger.stress": {
                "value": k,
                "kind": "k_esc",
                "status": "calibrated-C1",
                "provenance": prov,
            },
            "coupling_escalation.stress.anger": {
                "value": k,
                "kind": "k_esc",
                "status": "calibrated-C1",
                "provenance": "symmetric with coupling_escalation.anger.stress (no data to split "
                "the two edges; one shared k, the absolute anchor for the burst layer)",
            },
        },
        "band_entry_used_for_C1": BAND_ENTRY,
        "stages_pending": [
            "C2 burst_extinction (return-and-stay within T_cool)",
            "C3 latch geometry (theta_burst_enter/exit/confirm — pins BAND_ENTRY)",
            "C4 Loop-2 sign (urge_boredom.stress, seek stress-cost)",
            "C5 theta_displace + displaced discount",
            "refractory edge weight (potential_weights.outburst.refractory_x_resent_src)",
        ],
    }
    OUT.write_text(
        "# GENERATED by calibration/calibrate_burst.py — do not hand-edit (provenance record).\n"
        "# Read ON TOP OF defaults.yaml; defaults stay neutral/placeholder. Wired into the eval\n"
        "# loader at plan step 4 (burst overlay, opt-in) — until then this is a provenance artifact.\n\n"
        + yaml.safe_dump(doc, sort_keys=False, default_flow_style=False, width=100),
        encoding="utf-8",
    )


def main() -> None:
    if not ENV_JSON.exists():
        raise SystemExit(
            "missing eval/burst_operating_points.json — run "
            "`python eval/measure_operating_points.py` first"
        )
    res = solve_c1()
    print("C1 — k_esc feasibility frontier\n" + "=" * 50)
    print(
        f"frozen loop: bound={res['bound']:.6f}  g_as*g_sa={res['g_as'] * res['g_sa']:.6f}"
    )
    print(f"max escalation factor before instability R = {res['R']:.4f}")
    print(
        f"max observed frequent pair: anger={res['pair'][0]:.3f} stress={res['pair'][1]:.3f}"
    )
    print(
        f"feasible window: k_lo={res['k_lo']:.3f}  k_hi={res['k_hi']:.3f}  feasible={res['feasible']}"
    )
    print(f"CHOSEN k_esc = {res['k']:.2f} (both edges)\n")
    # show the margin table at the chosen k
    bound, g_as, g_sa = res["bound"], res["g_as"], res["g_sa"]
    pts = {
        "p99 pair": (res["env"]["le2_anger_p99"], res["env"]["le2_stress_p99"]),
        "MAX observed pair": res["pair"],
        f"band entry ({BAND_ENTRY['anger']},{BAND_ENTRY['stress']})": (
            BAND_ENTRY["anger"],
            BAND_ENTRY["stress"],
        ),
        "full saturation (1,1)": (1.0, 1.0),
    }
    for nm, (a, s) in pts.items():
        m = bound - g_as * g_sa * _factor(a, s, res["k"])
        print(f"  {nm:28s} margin={m:+.6f}  {'SPIRAL' if m < 0 else 'stable'}")
    write_yaml(res)
    print(f"\nwrote -> {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
