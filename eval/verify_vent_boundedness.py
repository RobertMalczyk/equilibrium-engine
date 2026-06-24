"""eval/verify_vent_boundedness.py — the REFRAMED burst acceptance criterion (M20.1, 2026-06-14).

The vent (outburst latch) is a STABILITY SAFETY VALVE, not a per-loop dramatic feature. The design:
each MAIN PAIR of positive feedback loops is individually calibrated stable (poles inside the unit
circle). But a character is rarely under one pressure — an insult AND rain AND hunger AND a barren day
can excite several UNRELATED loops at once, and the stability of every such COMBINATION cannot be
pre-certified (combinatorial, nonlinear). The vent is the global safety mechanism that catches it:
when stacked pressures saturate the shared loop states, it latches, DISCHARGES, and returns the system
to bounded — so the whole character stays bounded even though only the individual pairs were proven.

The acceptance criterion this implies (REPLACES the earlier, mis-aimed cichy_multi_060 target — a
single relentless provoker is ONE stable loop and is SUPPOSED to stay bounded WITHOUT venting):

  (1) SILENT ON A SINGLE / ORDINARY LOAD: an ordinary 2-way load (the frequent hungry+tired pair +
      one mild slight) must NOT arm the vent — it is individually stable, so the safety valve stays
      shut.
  (2) FIRES + BOUNDS ON A COINCIDENCE: a genuine >=3-way bad-day stack (loaded state + a resented-
      provoker cluster) must arm the vent AND then RELEASE within the response window — the episode
      self-terminates (extinction discharges the saturation) rather than staying pegged.
  (3) (the corpus-wide form, run separately at step 5: NO scenario stays pegged at saturation — the
      vent is the backstop that keeps every combination bounded.)

MEASUREMENT WINDOW: the vent's guarantee is about the bounded RESPONSE TO THE FORCING, so each scenario
is measured over [0, last_event + TAIL]. (Running far past the forcing with no mock world leaves the
persona fruitlessly SEEKING, whose frustration->anger climb is a no-world artifact, not the vent.)

Run:  PYTHONPATH=. python eval/verify_vent_boundedness.py
"""

from __future__ import annotations

from pathlib import Path

from engine.simulation import run_scenario
from engine.yaml_io import load_scenario
from eval.calibrated import load_eval_persona

ROOT = Path(__file__).resolve().parents[1]
BURST = ROOT / "data" / "scenarios" / "burst"
TAIL = 14  # ticks of discharge window after the last forcing event (before any seeking artifact)


def vent_response(persona: str, scenario_id: str) -> dict:
    """Run a benchmark with the vent ON over [0, last_event + TAIL] and report whether the vent armed
    and whether the episode self-terminated (latch released = extinction discharged the saturation)."""
    sc = load_scenario(BURST / f"{scenario_id}.yaml")
    last_event = max((ev.t for ev in sc.events), default=0)
    n = last_event + TAIL
    cfg = load_eval_persona(persona, burst=True)
    _, tr = run_scenario(cfg, sc, n_ticks=n)
    latched = [tk.burst_latched for tk in tr.ticks]
    armed = any(latched)
    arm_t = next((i for i, x in enumerate(latched) if x), None)
    # released = a True -> False transition after arming (the episode self-terminated within the window)
    released = arm_t is not None and any(
        latched[i] and not latched[i + 1] for i in range(arm_t, len(latched) - 1)
    )
    anger = [tk.state_after_post.global_state["anger"] for tk in tr.ticks]
    return {
        "armed": armed,
        "arm_t": arm_t,
        "released": released,
        "anger_peak": max(anger),
        "n": n,
    }


# (scenario, persona, must_vent) — persona is informational (shared initial_overrides); wojslaw = the
# free-to-vent reference used by the other burst benchmarks.
CASES = [
    (
        "ordinary_pair",
        "wojslaw",
        False,
    ),  # (1) single/ordinary load -> vent stays SILENT
    (
        "bad_day_stack",
        "wojslaw",
        True,
    ),  # (2) >=3-way coincidence -> vent FIRES and self-terminates
]


def main() -> None:
    print(
        "Reframed vent acceptance (silent on single loads; fires+bounds on a coincidence):\n"
    )
    all_ok = True
    for sid, persona, must_vent in CASES:
        r = vent_response(persona, sid)
        if must_vent:
            ok = r["armed"] and r["released"]
            verdict = "vent FIRES + self-terminates" if ok else "FAILED to fire/release"
        else:
            ok = not r["armed"]
            verdict = (
                "vent SILENT (ordinary load stays bounded)" if ok else "WRONGLY VENTED"
            )
        all_ok = all_ok and ok
        print(
            f"  [{'PASS' if ok else 'FAIL'}] {sid:14} armed={r['armed']!s:5} "
            f"released={r['released']!s:5} anger_pk={r['anger_peak']:.2f}  -> {verdict}"
        )
    print("\n" + ("ALL CHECKS PASS" if all_ok else "SOME CHECKS FAILED"))


if __name__ == "__main__":
    main()
