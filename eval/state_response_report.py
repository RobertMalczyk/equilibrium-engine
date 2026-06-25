"""eval/state_response_report.py -- deterministic state-response diagnostic (markdown).

Reads a loaded PersonaConfig and reports, for each state, how it behaves as a bounded first-order
leaky integrator (docs/control_interpretation.md): half-life, dt, per-tick decay, unit finite-event
impulse-response samples, the unconstrained drift steady state x_inf = drift/(1-decay), and whether
that steady state would rely on clamp saturation. Also emits the anger<->stress loop stability report
(Jury margin, dominant pole/eigenvalue, tail half-time, knife-edge warning).

DETERMINISTIC and LLM-FREE: pure config arithmetic via engine.stability. Generated artifact, not a
golden; changes no runtime behavior. Run:

    python -m eval.state_response_report                 # default halgrim -> stdout
    python -m eval.state_response_report --write report.md
"""

from __future__ import annotations

import argparse
from pathlib import Path

from engine.stability import anger_stress_loop_report, state_response_report
from engine.yaml_io import load_persona

ROOT = Path(__file__).resolve().parents[1]


def build_report(persona: str, defaults: str, n: int = 6) -> str:
    cfg = load_persona(persona, defaults)
    rows = state_response_report(cfg, n=n)
    loop = anger_stress_loop_report(cfg.decay, cfg.couplings, dt=cfg.dt)

    lines: list[str] = []
    lines.append(f"# State-response diagnostic -- {cfg.id}")
    lines.append("")
    lines.append(
        "Each state is a bounded first-order leaky integrator "
        "`x[n+1] = decay*x[n] + gain*event[n] + drift`, `decay = 2**(-dt/half_life)`. "
        "An event is a **finite single-tick deposit**, not a Dirac delta; the impulse response is the "
        "bounded exponential tail. `x_inf = drift/(1-decay)` is the unconstrained drift steady state "
        "(before couplings/clamp); a flagged state relies on clamp saturation."
    )
    lines.append("")
    lines.append(f"`dt = {cfg.dt:.6g}` (derived from `min(half_life)/nyquist`).")
    lines.append("")
    lines.append(
        "| state | half_life | decay | drift | x_inf (drift) | clamp-reliant | impulse response (unit event) |"
    )
    lines.append("|---|---|---|---|---|---|---|")
    for r in rows:
        ir = ", ".join(f"{v:.3f}" for v in r["impulse_response"])
        flag = "**YES**" if r["relies_on_clamp"] else "no"
        lines.append(
            f"| {r['state']} | {r['half_life']:.6g} | {r['decay']:.4f} | "
            f"{r['drift']:.4g} | {r['x_inf_drift']:.4g} | {flag} | {ir} |"
        )
    lines.append("")

    flagged = [r["state"] for r in rows if r["relies_on_clamp"]]
    if flagged:
        lines.append(
            f"> **Clamp-reliance warning:** {', '.join(flagged)} "
            "have a drift steady state outside [0,1] -- they pin at the clamp. "
            "(Expected for the *accumulator* role -- hunger/fatigue/sleep_pressure are "
            "designed to ride toward the ceiling and are reset by eat/sleep; a clamp-reliant "
            "*emotion* state, by contrast, would be a calibration smell.)"
        )
    else:
        lines.append(
            "> No state relies on clamp saturation for its drift steady state."
        )
    lines.append("")

    lines.append("## anger <-> stress loop stability")
    lines.append("")
    ev = loop["dominant_eigenvalue"]
    lines.append(
        f"- Jury margin: `{loop['jury_margin']:.6g}` (bound `{loop['jury_bound']:.6g}`, "
        f"ratio `{loop['margin_ratio']:.3f}`)"
    )
    lines.append(
        f"- dominant eigenvalue/pole: `{ev.real:.4f}{ev.imag:+.4f}i` -> |pole| = "
        f"`{loop['dominant_pole']:.4f}`"
    )
    th = loop["tail_half_time_ticks"]
    ts = loop["tail_half_time_seconds"]
    th_s = f"{th:.1f} ticks" + (f" (~{ts:.0f}s)" if ts is not None else "")
    lines.append(f"- effective tail half-time: `{th_s}`")
    lines.append(f"- stable: `{loop['stable']}`")
    if loop["warnings"]:
        for w in loop["warnings"]:
            lines.append(f"- WARNING: {w}")
    lines.append("")
    return "\n".join(lines)


def main() -> None:
    ap = argparse.ArgumentParser(
        description="State-response diagnostic (deterministic)."
    )
    ap.add_argument("--persona", default=str(ROOT / "data/personas/halgrim.yaml"))
    ap.add_argument("--defaults", default=str(ROOT / "calibration/defaults.yaml"))
    ap.add_argument("--samples", type=int, default=6)
    ap.add_argument("--write", default=None, help="path to write the markdown report")
    args = ap.parse_args()
    md = build_report(args.persona, args.defaults, n=args.samples)
    if args.write:
        Path(args.write).write_text(md, encoding="utf-8")
        print(f"wrote {args.write}")
    else:
        print(md)


if __name__ == "__main__":
    main()
