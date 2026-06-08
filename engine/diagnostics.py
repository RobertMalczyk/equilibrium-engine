"""diagnostics -- trajectory plots + debug tables for the calibration benchmark (M4).

DERIVED ARTIFACTS, not block diagrams (the spec section 12 directive is for DYNAMICS subsystems;
this is trajectory visualization) and not goldens (matplotlib output is not bit-stable -- fine,
it is diagnostic). Generated FROM the same DebugTrace the tests read, so a plot can never show
something the tests don't. Output goes to calibration/diagnostics/ (OUTSIDE the test path).

One-way dependency: diagnostics -> engine. The pure path (loss/simulate/engine) NEVER imports
diagnostics -- diagnostics must not feed calibration.

Plots ILLUSTRATE THE CONTRACTS (not a generic 11-state dump):
  * insult_decay  -- anger + resentment, with the anchor and the anger settle marked (C1 + anchor).
  * idle_boredom  -- boredom rise vs the urge start threshold (C4; where seek would fire).
  * before_after  -- anger decay at placeholder vs calibrated half-lives (the effect of run_layer1).
A compact per-tick debug table (CSV) is dumped alongside, so numbers and curves sit together.
"""

from __future__ import annotations

import csv
from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # headless; never opens a window
import matplotlib.pyplot as plt  # noqa: E402

from engine.loss import simulate  # one-way: diagnostics -> engine

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "calibration" / "diagnostics"


def _secs(tr):
    return [tk.t * tr.dt for tk in tr.ticks]


def _g(tr, s):
    return [tk.state_after_post.global_state[s] for tk in tr.ticks]


def _rel(tr, src, dim):
    return [tk.state_after_post.relations.get(src, {}).get(dim, 0.0) for tk in tr.ticks]


def _ensure(out_dir):
    p = Path(out_dir)
    p.mkdir(parents=True, exist_ok=True)
    return p


def _contribution(persona, scenario, horizon, state=None, rel=None, params=None):
    """(impulse - control) series for a state or relation dim, in game-seconds. Isolates the event's
    contribution from the ambient idle drift (the impulse-response method)."""
    cfg, imp = simulate(params, persona, scenario, horizon)
    _, ctl = simulate(params, persona, "quiet_control", horizon)
    if state is not None:
        diff = [a - b for a, b in zip(_g(imp, state), _g(ctl, state))]
    else:
        src, dim = rel
        diff = [a - b for a, b in zip(_rel(imp, src, dim), _rel(ctl, src, dim))]
    return cfg, _secs(imp), diff


def plot_impulse_contributions(out_dir=OUT, params=None):
    """The layer-1 timing contracts: satisfaction glow (anchor) + anger/resentment (C1), each as an
    impulse CONTRIBUTION (event minus no-event control), so the ambient idle drift is subtracted out."""
    cfg, t_s, sat = _contribution(
        "halgrim", "food_impulse", 180.0, state="satisfaction", params=params
    )
    _, t_a, ang = _contribution(
        "halgrim", "insult_impulse", 180.0, state="anger", params=params
    )
    _, t_r, res = _contribution(
        "halgrim", "insult_impulse", 180.0, rel=("player", "resentment"), params=params
    )
    anchor = float(cfg.calibration.get("satisfaction_halfdecay_seconds", 45.0))
    fig, ax = plt.subplots(figsize=(7, 4))
    ax.plot(t_s, sat, color="seagreen", label="satisfaction glow (anchor)")
    ax.plot(t_a, ang, color="crimson", label="anger (C1: halves)")
    ax.plot(t_r, res, color="navy", label="resentment (C1: persists)")
    ax.axvline(anchor, ls="--", color="gray", label=f"anchor {anchor:.0f}s half-decay")
    ax.axhline(max(sat) * 0.5, ls=":", color="seagreen", lw=0.8)
    ax.set(
        xlabel="game-time (s)",
        ylabel="contribution (impulse - control)",
        title="Layer-1 timing: satisfaction glow half-decays (anchor); anger halves, resentment lingers (C1)",
    )
    ax.legend(fontsize=8)
    fig.tight_layout()
    f = _ensure(out_dir) / "impulse_contributions.png"
    fig.savefig(f, dpi=90)
    plt.close(fig)
    return f


def plot_idle_boredom(out_dir=OUT, params=None):
    cfg, tr = simulate(params, "welf", "idle_watch", 180.0)
    theta = cfg.thresholds["urge_start"]
    fig, ax = plt.subplots(figsize=(7, 4))
    ax.plot(_secs(tr), _g(tr, "boredom"), color="darkorange", label="boredom")
    ax.plot(
        _secs(tr),
        [tk.urges.get("boredom", 0.0) for tk in tr.ticks],
        color="green",
        label="urge_boredom",
    )
    ax.axhline(theta, ls="--", color="gray", label=f"theta_start {theta}")
    ax.set(
        xlabel="game-time (s)",
        ylabel="level [0..1]",
        title="idle_watch: boredom creeps; urge vs start threshold (C4)",
    )
    ax.legend(fontsize=8)
    fig.tight_layout()
    f = _ensure(out_dir) / "idle_boredom.png"
    fig.savefig(f, dpi=90)
    plt.close(fig)
    return f


def plot_before_after(calibrated_half_lives, out_dir=OUT):
    """The effect of run_layer1: the satisfaction glow contribution at placeholder vs calibrated
    half-lives -- the half-life the layer actually steered, toward the anchored half-decay."""
    cfg0, t0, g0 = _contribution(
        "halgrim", "food_impulse", 180.0, state="satisfaction", params=None
    )
    _, t1, g1 = _contribution(
        "halgrim",
        "food_impulse",
        180.0,
        state="satisfaction",
        params={"half_lives": calibrated_half_lives},
    )
    anchor = float(cfg0.calibration.get("satisfaction_halfdecay_seconds", 45.0))
    fig, ax = plt.subplots(figsize=(7, 4))
    ax.plot(t0, g0, color="seagreen", ls=":", label="glow @ placeholder")
    ax.plot(t1, g1, color="seagreen", label="glow @ calibrated")
    ax.axvline(anchor, ls="--", color="gray", label=f"anchor {anchor:.0f}s half-decay")
    ax.set(
        xlabel="game-time (s)",
        ylabel="satisfaction contribution",
        title="run_layer1 effect: satisfaction glow half-decay placeholder vs calibrated",
    )
    ax.legend(fontsize=8)
    fig.tight_layout()
    f = _ensure(out_dir) / "before_after_glow.png"
    fig.savefig(f, dpi=90)
    plt.close(fig)
    return f


def dump_debug_table(label, persona, scenario, horizon, out_dir=OUT, params=None):
    _, tr = simulate(params, persona, scenario, horizon)
    f = _ensure(out_dir) / f"table_{label}.csv"
    with open(f, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(
            [
                "t",
                "sec",
                "action",
                "mode",
                "anger",
                "frustration",
                "stress",
                "boredom",
                "satisfaction",
                "urge_boredom",
            ]
        )
        for tk in tr.ticks:
            g = tk.state_after_post.global_state
            w.writerow(
                [
                    tk.t,
                    round(tk.t * tr.dt, 2),
                    tk.selection.action,
                    tk.state_after_post.mode.value,
                    round(g["anger"], 4),
                    round(g["frustration"], 4),
                    round(g["stress"], 4),
                    round(g["boredom"], 4),
                    round(g["satisfaction"], 4),
                    round(tk.urges.get("boredom", 0.0), 4),
                ]
            )
    return f


def generate_all(calibrated_half_lives=None, out_dir=OUT):
    """Generate the contract plots + debug tables for the layer-1 benchmark runs."""
    files = [plot_impulse_contributions(out_dir), plot_idle_boredom(out_dir)]
    if calibrated_half_lives:
        files.append(plot_before_after(calibrated_half_lives, out_dir))
    files.append(
        dump_debug_table("food_impulse", "halgrim", "food_impulse", 180.0, out_dir)
    )
    files.append(
        dump_debug_table("insult_impulse", "halgrim", "insult_impulse", 180.0, out_dir)
    )
    files.append(dump_debug_table("welf_idle", "welf", "idle_watch", 180.0, out_dir))
    return files
