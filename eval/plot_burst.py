"""eval/plot_burst.py — verification & comparison plots for the burst mechanism.

Every figure runs the SAME scenario in two (or three) engine variants and overlays the traces,
so the difference the burst machinery makes is visible directly:

  F1 grinding_day      escalation + extinction: a day of sourceless grind (hungry + tired + rain +
                       fruitless seeking, no one to reply to). OFF = today's linear loop (settles);
                       ON = k_esc-escalated loop (spirals to the ceiling, latches, then the
                       extinction cools it slowly after the grind stops). Spike-hold-cool vs settle.
  F2 spike_vs_plateau  latch discrimination: anger spike (stress low) vs loop plateau (both high),
                       both with the latch enabled — only the PLATEAU arms it (shaded band).
  F3 displacement      who the burst lands on: hot start, kind Marta brings a meal at t=5.
                       OFF: the gate stays shut, no reply. ON: displaced outburst at Marta —
                       and her resentment does NOT step (discount 0) vs the runaway variant
                       (discount 1: every discharge books a grudge on the innocent).
  F4 loop2_sign        the relief-seeking loop's environmental sign: one config, rich vs barren
                       world — stress descends vs climbs.

Burst parameters here are EVAL-AUTHORED demo values (shipped defaults stay neutral).
Run:  PYTHONPATH=. python eval/plot_burst.py     -> eval/plots/burst/*.png
"""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from engine.schema import Mode, RawEvent, Scenario
from engine.simulation import run_scenario
from engine.yaml_io import load_persona
from eval.mock_world import MockWorld, run_with_world

ROOT = Path(__file__).resolve().parents[1]
DEFAULTS = ROOT / "calibration" / "defaults.yaml"
OUT = ROOT / "eval" / "plots" / "burst"

LATCH = {
    "burst_enter.anger": 0.80,
    "burst_enter.stress": 0.60,
    "burst_exit": 0.30,
    "burst_confirm_ticks": 2,
}
# F1 demo point, probed for the right story: k_esc=1.5 escalates wojslaw's loop past the linear
# band under the grind, and extinction 0.15 DOMINATES the escalated coupling at the ceiling so the
# trajectory returns (the spec's boundedness condition). Probed counter-example, kept on record:
# k_esc=3 with extinction 0.08 is SELF-SUSTAINING at the ceiling (coupling 0.16/tick in vs
# decay+extinction 0.147/tick out) -> the latch never releases -> the boundedness gate REJECTS it.
ESCALATION = {
    "coupling_escalation": {"anger": {"stress": 1.5}, "stress": {"anger": 1.5}}
}
EXTINCTION = {"burst_extinction": {"anger": 0.15, "stress": 0.15}}
F3_EXTINCTION = {
    "burst_extinction": {"anger": 0.02, "stress": 0.02}
}  # slow: keep the spring loaded
LOOP2 = {
    "derived_weights": {"urge_boredom": {"stress": 0.60}},
    "action_params": {"seek_stimulus": {"per_tick": {"stress": 0.015}}},
}


def _cfg(persona: str, *overlays: dict):
    ov: dict = {}
    for o in overlays:
        for k, v in o.items():
            if isinstance(v, dict):
                cur = ov.setdefault(k, {})
                for kk, vv in v.items():
                    if isinstance(vv, dict):
                        cur.setdefault(kk, {}).update(vv)
                    else:
                        cur[kk] = vv
            else:
                ov[k] = v
    return load_persona(
        ROOT / "data" / "personas" / f"{persona}.yaml",
        DEFAULTS,
        param_overrides=ov or None,
    )


def _series(tr, state):
    return [tk.state_after_post.global_state[state] for tk in tr.ticks]


def _latch_spans(tr):
    spans, start = [], None
    for i, tk in enumerate(tr.ticks):
        if tk.burst_latched and start is None:
            start = i
        if not tk.burst_latched and start is not None:
            spans.append((start, i))
            start = None
    if start is not None:
        spans.append((start, len(tr.ticks)))
    return spans


def _explain(fig, text: str):
    """On-screen explanation (project rule: every plot carries one)."""
    fig.text(
        0.01,
        0.01,
        text,
        fontsize=8.2,
        va="bottom",
        ha="left",
        wrap=True,
        bbox=dict(facecolor="#fffbe6", edgecolor="#c9b458", boxstyle="round,pad=0.4"),
    )


def _save(fig, name):
    OUT.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT / f"{name}.png", dpi=120)
    plt.close(fig)
    print(f"  -> eval/plots/burst/{name}.png")


# ------------------------------- F1: the grinding day -------------------------------


def fig_grinding_day():
    # Panel A — ONE episode in isolation: hot start, no further input. The cleanest view of what
    # the mechanism changes about a single bout of fury.
    n_a = 72
    hot = {"global_state": {"anger": 0.95, "stress": 0.90}}
    sc_a = Scenario(id="episode", persona="wojslaw", initial_overrides=hot, events=())
    off_a = run_scenario(_cfg("wojslaw"), sc_a, n_ticks=n_a)[1]
    # episode-regime extinction (0.045): slow enough that the escalated coupling visibly props the
    # fury up against decay (the plateau), strong enough that the trajectory returns (boundedness).
    on_a = run_scenario(
        _cfg(
            "wojslaw",
            {"thresholds": LATCH},
            ESCALATION,
            {"burst_extinction": {"anger": 0.045, "stress": 0.045}},
        ),
        sc_a,
        n_ticks=n_a,
    )[1]

    # Panel B — a grinding day: a mild relentless drizzle on a persona whose baseline stays up.
    grind_until, n_b = 120, 260
    events = tuple(
        RawEvent(t=t, type="weather", intensity=0.2) for t in range(0, grind_until, 10)
    )
    init = {
        "global_state": {"hunger": 0.1, "fatigue": 0.2, "boredom": 0.2, "stress": 0.25}
    }
    sc_b = Scenario(
        id="grind", persona="halgrim", initial_overrides=init, events=events
    )
    off_b = run_scenario(_cfg("halgrim"), sc_b, n_ticks=n_b)[1]
    on_b = run_scenario(
        _cfg("halgrim", {"thresholds": LATCH}, ESCALATION, EXTINCTION),
        sc_b,
        n_ticks=n_b,
    )[1]

    fig, (ax_a, ax_b) = plt.subplots(
        1, 2, figsize=(12.5, 5.4), gridspec_kw={"width_ratios": [1, 2.2]}
    )
    for ax, off, on, title in (
        (
            ax_a,
            off_a,
            on_a,
            "one episode in isolation\n(hot start, nothing further happens)",
        ),
        (
            ax_b,
            off_b,
            on_b,
            "a grinding day (cold drizzle until the dotted line)\nhalgrim, same inputs to both engines",
        ),
    ):
        ax.plot(
            _series(off, "anger"),
            color="#7f7f7f",
            lw=1.9,
            label="burst OFF (today's linear loop)",
        )
        ax.plot(
            _series(on, "anger"),
            color="#d62728",
            lw=1.9,
            label="burst ON (k_esc + latch + extinction)",
        )
        for a, b in _latch_spans(on):
            ax.axvspan(a, b, color="#d62728", alpha=0.10)
        ax.axhline(
            LATCH["burst_enter.anger"], color="#d62728", ls="--", lw=0.9, alpha=0.7
        )
        ax.axhline(LATCH["burst_exit"], color="#d62728", ls=":", lw=0.9, alpha=0.7)
        ax.set_ylim(-0.03, 1.05)
        ax.grid(alpha=0.25)
        ax.set_title(title, fontsize=9.5)
        ax.set_xlabel("tick (dt = 3 s)")
    ax_b.axvline(grind_until, color="#444", ls=":", lw=1.2)
    ax_a.set_ylabel("anger")
    ax_a.legend(fontsize=7.5, loc="upper right")
    fig.suptitle("F1 — What the burst machinery changes", y=0.99)
    fig.subplots_adjust(bottom=0.34, top=0.86, wspace=0.15)
    _explain(
        fig,
        "LEFT, one episode: from the same white-hot start, the linear engine (GREY) just decays exponentially and\n"
        "settles; the burst engine (RED, extinction 0.045) is LATCHED (shading) — the escalated coupling props the\n"
        "fury up against decay (the plateau), then extinction walks it down: longer, flatter, and it ends LOWER\n"
        "than the linear engine — spent, not reset. Release at the exit bar (dotted).\n"
        "RIGHT, a grinding day: under a mild drizzle nobody caused, the linear engine carries the day at a flat\n"
        "simmer and never does anything about it. The burst engine repeatedly ESCALATES over the enter bar\n"
        "(dashed), bursts, cools, and re-ignites while the grind lasts — recurring fits of temper (a relaxation\n"
        "oscillation), each one spike-hold-cool. Probed counter-example, rejected by the boundedness gate:\n"
        "k_esc=3 + extinction 0.08 self-sustains at the ceiling (coupling in > decay+extinction out) and never\n"
        "releases — extinction must dominate the escalated coupling outside the saturated region.",
    )
    _save(fig, "F1_episode_and_grinding_day")


# ------------------------------- F2: spike vs plateau -------------------------------


def fig_spike_vs_plateau():
    # latch + extinction ONLY (no escalation): this figure isolates the ARMING question; with
    # escalation on, the spike itself would pump stress up and blur the discrimination.
    cfg = _cfg(
        "wojslaw",
        {"thresholds": LATCH},
        {"burst_extinction": {"anger": 0.045, "stress": 0.045}},
    )
    n = 60
    runs = {
        "loop plateau (anger 0.95 AND stress 0.90)": {"anger": 0.95, "stress": 0.90},
        "single-state spike (anger 0.95, stress 0.10)": {"anger": 0.95, "stress": 0.10},
    }
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.9), sharey=True)
    for ax, (title, init) in zip(axes, runs.items()):
        sc = Scenario(
            id="latch",
            persona="wojslaw",
            initial_overrides={"global_state": init},
            events=(),
        )
        tr = run_scenario(cfg, sc, n_ticks=n)[1]
        ax.plot(_series(tr, "anger"), color="#d62728", lw=1.8, label="anger")
        ax.plot(_series(tr, "stress"), color="#9467bd", lw=1.8, label="stress")
        for a, b in _latch_spans(tr):
            ax.axvspan(a, b, color="#d62728", alpha=0.12)
        ax.axhline(
            LATCH["burst_enter.anger"], color="#d62728", ls="--", lw=0.9, alpha=0.7
        )
        ax.axhline(
            LATCH["burst_enter.stress"], color="#9467bd", ls="--", lw=0.9, alpha=0.7
        )
        latched = any(tk.burst_latched for tk in tr.ticks)
        ax.set_title(
            f"{title}\nlatch armed: {'YES' if latched else 'NO'}", fontsize=9.5
        )
        ax.set_xlabel("tick")
        ax.grid(alpha=0.25)
    axes[0].set_ylabel("state")
    axes[0].legend(fontsize=8)
    fig.suptitle(
        "F2 — What arms the burst latch: the LOOP plateau, not a spike", y=0.99
    )
    fig.subplots_adjust(bottom=0.30, top=0.84)
    _explain(
        fig,
        "Both panels run the SAME engine with the latch enabled; only the starting state differs. LEFT: both loop\n"
        "states sit above their enter bars (dashed lines, matching colours) for the confirm window -> the latch SETS\n"
        "(shaded) and extinction begins. RIGHT: anger alone spikes just as high, but stress is low -> the LOOP is not\n"
        "saturated, the latch never arms, and the spike just decays. An ordinary flash of temper is not a burst.",
    )
    _save(fig, "F2_spike_vs_plateau_latch")


# ------------------------------- F3: displacement -------------------------------


def fig_displacement():
    n = 12
    base_th = dict(LATCH, theta_displace=0.55, reactive_window_ticks=1)
    appraisal_off_kindness = {
        "appraisal": {"gesture_channels": [], "kindness_pressure": 0.0}
    }
    init = {"global_state": {"anger": 0.95, "stress": 0.90}}
    events = (
        RawEvent(
            t=5, type="food_given", source="marta", item="warm_meal", intensity=0.8
        ),
    )
    sc = Scenario(id="disp", persona="wojslaw", initial_overrides=init, events=events)

    variants = {
        "burst OFF (today): gate shut, no reply": (
            _cfg("wojslaw", appraisal_off_kindness),
            "#7f7f7f",
        ),
        "burst ON, discount 0 (spec): snaps, NO grudge": (
            _cfg(
                "wojslaw",
                {"thresholds": base_th},
                F3_EXTINCTION,
                appraisal_off_kindness,
            ),
            "#d62728",
        ),
        "burst ON, discount 1 (runaway): snaps, grudge steps": (
            _cfg(
                "wojslaw",
                {"thresholds": base_th},
                F3_EXTINCTION,
                {
                    "appraisal": {
                        "gesture_channels": [],
                        "kindness_pressure": 0.0,
                        "displaced_relational_discount": 1.0,
                    }
                },
            ),
            "#1f77b4",
        ),
    }
    fig, (ax_a, ax_r) = plt.subplots(1, 2, figsize=(11, 4.9))
    for label, (cfg, color) in variants.items():
        tr = run_scenario(cfg, sc, n_ticks=n)[1]
        # the two burst-ON variants have IDENTICAL anger (they differ only relationally): dash the
        # runaway variant so the spec variant stays visible underneath
        ls = "--" if "discount 1" in label else "-"
        ax_a.plot(_series(tr, "anger"), color=color, lw=1.8, ls=ls, label=label)
        res = [
            tk.state_after_post.relations.get("marta", {}).get("resentment", 0.0)
            for tk in tr.ticks
        ]
        ax_r.plot(res, color=color, lw=1.8)
        tk5 = tr.ticks[5]
        if tk5.selection.kind.value == "reactive":
            ax_a.plot(5, _series(tr, "anger")[5], "v", color=color, ms=9)
    for ax, ttl, yl in (
        (ax_a, "anger (v = visible reply at Marta's tick)", "anger"),
        (ax_r, "resentment toward MARTA", "resentment[marta]"),
    ):
        ax.axvline(5, color="#444", ls=":", lw=1.2)
        ax.set_title(ttl, fontsize=10)
        ax.set_xlabel("tick")
        ax.set_ylabel(yl)
        ax.grid(alpha=0.25)
    ax_a.legend(fontsize=7.6, loc="lower left")
    fig.suptitle(
        "F3 — The loaded spring: kind Marta brings a meal at t=5 (dotted)", y=0.99
    )
    fig.subplots_adjust(bottom=0.32, top=0.84)
    _explain(
        fig,
        "A man pinned white-hot by a morning nobody here caused. GREY (today): a kind meal from a non-resented\n"
        "source is no provocation, the gate stays shut — he does NOTHING (the loaded spring stays loaded). RED\n"
        "(the spec'd mechanism): over theta_displace the burst latch widens the gate — he SNAPS at Marta (marker),\n"
        "but the displaced discharge books a TRANSIENT cost: her resentment curve does not step. BLUE (the rejected\n"
        "runaway, discount=1): the same snap mints a durable grudge on the innocent — the start of the measured\n"
        "fabricated-nemesis spiral the discount exists to exclude. Marta starts at 0.2 resentment: wojslaw's seeded relation.",
    )
    _save(fig, "F3_displacement_grudge")


# ------------------------------- F4: loop-2 sign -------------------------------


def fig_loop2_sign():
    n = 80
    cfg = _cfg("lutek", LOOP2)
    init = {"global_state": {"stress": 0.60, "boredom": 0.50, "fatigue": 0.10}}
    sc = Scenario(id="loop2", persona="lutek", initial_overrides=init, events=())
    rich = run_with_world(
        cfg, sc, MockWorld(novelty_start=1.0, replenish_per_tick=0.02), n
    )
    barren = run_with_world(cfg, sc, MockWorld(novelty_start=0.0), n)

    fig, ax = plt.subplots(figsize=(11, 5.0))
    for tr, color, label in (
        (
            rich,
            "#2ca02c",
            "RICH world: finds an activity -> relief (negative feedback)",
        ),
        (
            barren,
            "#d62728",
            "BARREN world: fruitless looking -> wind-up (positive feedback)",
        ),
    ):
        ax.plot(_series(tr, "stress"), color=color, lw=1.9, label=label)
        for tk in tr.ticks:
            if (
                tk.snapshot.mode == Mode.IDLE
                and tk.state_after_post.mode == Mode.SEEKING
            ):
                ax.plot(tk.t, _series(tr, "stress")[tk.t], "^", color=color, ms=7)
            if (
                tk.snapshot.mode == Mode.SEEKING
                and tk.state_after_post.mode == Mode.BUSY
            ):
                ax.plot(tk.t, _series(tr, "stress")[tk.t], "*", color=color, ms=12)
    ax.set_xlabel("tick")
    ax.set_ylabel("stress")
    ax.set_ylim(-0.03, 1.05)
    ax.grid(alpha=0.25)
    ax.legend(fontsize=8.5, loc="center right")
    ax.set_title(
        "F4 — Loop 2's sign is the ENVIRONMENT: one persona, one config, two worlds"
    )
    fig.subplots_adjust(bottom=0.27)
    _explain(
        fig,
        "The SAME stressed persona with the SAME relief-seeking edges (stress drives the urge to find a\n"
        "distraction; fruitless looking costs stress). ^ = starts looking, * = the world confirms an activity.\n"
        "GREEN: a rich world confirms one -> engaging RECOVERS stress: the loop closes as negative feedback.\n"
        "RED: a barren world never confirms -> every search times out and the looking itself wears him down:\n"
        "the IDENTICAL edges close as a positive loop, feeding the operating point the burst escalation acts on.",
    )
    _save(fig, "F4_loop2_environmental_sign")


def main():
    print("burst comparison plots:")
    fig_grinding_day()
    fig_spike_vs_plateau()
    fig_displacement()
    fig_loop2_sign()


if __name__ == "__main__":
    main()
