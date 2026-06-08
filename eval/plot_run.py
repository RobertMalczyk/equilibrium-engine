"""eval/plot_run.py -- run a (persona, scenario) through the deterministic engine and plot it.

Top panel: internal states over game-time. Bottom panel: the reactive action POTENTIALS vs their
visibility thresholds (so you can SEE why an action did/didn't fire). Both panels mark event TRIGGERS
(grey dotted) and FIRED actions (coloured solid, labelled). No LLM, no state mutation -- pure read of a
DebugTrace. Scenarios may live in data/scenarios (litmus) or eval/scenarios (LLM-generated, held-out).

Run:  PYTHONPATH=. python eval/plot_run.py
"""

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from scipy.interpolate import PchipInterpolator

from engine.simulation import run_scenario
from engine.yaml_io import load_persona, load_scenario

# DISPLAY-ONLY monotone smoothing (PCHIP: shape-preserving, no overshoot). It rounds the line BETWEEN
# the real samples; it does NOT change data, and every event/action MARKER stays at its exact tick. The
# engine's dt=3.0 (calibrated invariant) is untouched. Set False for raw piecewise-linear segments.
SMOOTH = True
DENSIFY = 12  # interpolation points inserted between each pair of real ticks

ROOT = Path(__file__).resolve().parents[1]
DEFAULTS = ROOT / "calibration" / "defaults.yaml"
OUT = ROOT / "eval" / "plots"

STATES = ["anger", "frustration", "stress", "boredom", "satisfaction"]
POTENTIALS = ["outburst", "cold_response", "complain", "cooperate", "refuse"]
SCOLOR = {
    "anger": "#d62728",
    "frustration": "#ff7f0e",
    "stress": "#9467bd",
    "boredom": "#8c564b",
    "satisfaction": "#2ca02c",
}
PCOLOR = {
    "outburst": "#d62728",
    "cold_response": "#1f77b4",
    "complain": "#ff7f0e",
    "cooperate": "#2ca02c",
    "refuse": "#9467bd",
}

# (scenario_id, scenarios_dir, persona, n_ticks, blurb)
RUNS = [
    ("same_soup_bad_day", "data", "wojslaw", 25, "same soup, bad day -> bursts"),
    ("same_soup_bad_day", "data", "halgrim", 25, "same soup, bad day -> suppresses"),
    (
        "command_from_edda",
        "data",
        "halgrim",
        6,
        "order from respected source -> cooperate",
    ),
    (
        "command_from_wojslaw",
        "data",
        "halgrim",
        6,
        "order from resented source -> refuse",
    ),
    ("prisoner_bias_resentful", "data", "cichy", 9, "resented guard -> cold_response"),
    ("prisoner_bias_neutral", "data", "cichy", 9, "neutral guard -> neutral"),
    (
        "eval_escalating_insults",
        "eval",
        "wojslaw",
        22,
        "LLM-gen: escalating public insults",
    ),
    (
        "eval_command_then_insult",
        "eval",
        "halgrim",
        14,
        "LLM-gen: obey order, then suppress insult",
    ),
]


def _scenario_path(scenario_id, where):
    base = ROOT / ("data/scenarios" if where == "data" else "eval/scenarios")
    return base / f"{scenario_id}.yaml"


def run(scenario_id, where, persona_id, n_ticks):
    cfg = load_persona(ROOT / "data" / "personas" / f"{persona_id}.yaml", DEFAULTS)
    sc = load_scenario(_scenario_path(scenario_id, where))
    _, trace = run_scenario(cfg, sc, n_ticks=n_ticks)
    return cfg, trace


def _curve(xs, ys):
    """Dense monotone interpolation for the drawn line (display only); raw points if too few."""
    xs = np.asarray(xs, float)
    ys = np.asarray(ys, float)
    if not SMOOTH or len(xs) < 3:
        return xs, ys
    xd = np.linspace(xs[0], xs[-1], (len(xs) - 1) * DENSIFY + 1)
    yd = PchipInterpolator(xs, ys)(xd).clip(0.0, 1.0)
    return xd, yd


def _mark(ax, t_sec, color, label, y, ls):
    ax.axvline(t_sec, color=color, ls=ls, lw=1.0, alpha=0.7)
    ax.annotate(
        label,
        xy=(t_sec, y),
        xytext=(2, 0),
        textcoords="offset points",
        rotation=90,
        va="top",
        ha="left",
        fontsize=7,
        color=color,
    )


def plot(cfg, trace, persona_id, scenario_id, blurb):
    dt = cfg.dt
    ts = [tk.t * dt for tk in trace.ticks]
    fig, (ax_s, ax_p) = plt.subplots(
        2, 1, figsize=(11, 7), sharex=True, gridspec_kw={"height_ratios": [1, 1]}
    )

    # --- top: states ---
    for s in STATES:
        ax_s.plot(
            *_curve(ts, [tk.state_after_post.global_state[s] for tk in trace.ticks]),
            label=s,
            color=SCOLOR[s],
            lw=1.6,
        )
    ax_s.set_ylabel("internal state")
    ax_s.set_ylim(-0.03, 1.03)
    ax_s.legend(loc="upper right", ncol=5, fontsize=8, framealpha=0.9)
    ax_s.set_title(
        f"{persona_id}  ::  {scenario_id}   —   {blurb}   (dt={dt:.2f}s)", fontsize=11
    )

    # --- bottom: potentials vs thresholds ---
    for p in POTENTIALS:
        ax_p.plot(
            *_curve(ts, [tk.potentials[p] for tk in trace.ticks]),
            label=p,
            color=PCOLOR[p],
            lw=1.5,
        )
        th = cfg.thresholds.get(f"react.{p}", 2.0)
        if th <= 1.0:
            ax_p.axhline(th, color=PCOLOR[p], ls=":", lw=1.0, alpha=0.6)
    ax_p.set_ylabel("action potential")
    ax_p.set_xlabel("game time (s)")
    ax_p.set_ylim(-0.03, 1.03)
    ax_p.legend(loc="upper right", ncol=5, fontsize=8, framealpha=0.9)

    # --- markers: event triggers (grey dotted) + fired actions (coloured solid) ---
    for tk in trace.ticks:
        t_sec = tk.t * dt
        if tk.event is not None:
            src = f"/{tk.event.source}" if tk.event.source else ""
            _mark(ax_s, t_sec, "#555555", f"{tk.event.type}{src}", 1.0, "dotted")
        act = tk.selection.action
        if act not in ("neutral", None):
            _mark(ax_p, t_sec, PCOLOR.get(act, "#000000"), act, 1.0, "solid")

    fig.tight_layout()
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / f"{persona_id}.{scenario_id}.png"
    fig.savefig(path, dpi=110)
    plt.close(fig)
    return path


def summary(trace):
    [tk.selection.action for tk in trace.ticks]
    fired = [
        (tk.t, tk.selection.action)
        for tk in trace.ticks
        if tk.selection.action not in ("neutral", None)
    ]
    peaks = {
        p: round(max(tk.potentials[p] for tk in trace.ticks), 3) for p in POTENTIALS
    }
    return fired, peaks


def main():
    print(f"{'persona':9} {'scenario':28} actions(t)            peak potentials")
    for scenario_id, where, persona_id, n, blurb in RUNS:
        cfg, trace = run(scenario_id, where, persona_id, n)
        path = plot(cfg, trace, persona_id, scenario_id, blurb)
        fired, peaks = summary(trace)
        fired_s = ",".join(f"{a}@{t}" for t, a in fired) or "(none fired)"
        print(f"{persona_id:9} {scenario_id:28} {fired_s:30} {peaks}")
        print(f"          -> {path.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
