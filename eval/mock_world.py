"""eval/mock_world.py -- a closed-loop "mock world" driver for the M7 Step 2 activity model.

The persona engine is open-loop (events in -> actions out). The proactive activity loop only CLOSES if
something outside supplies an `activity` confirmation when the NPC is SEEKING. In the product that's the
game engine; here it's this driver. It REACTS to the NPC -- it watches the mode each tick and, in WHATEVER
tick the NPC is SEEKING (different per persona), decides whether to confirm an activity. It never scripts a
fixed moment.

"What's nearby" is a DEPLETING NOVELTY BUDGET: each engagement uses up nearby novelty; it slowly replenishes
when the NPC isn't consuming it. When the budget runs low the world offers nothing -> the NPC keeps seeking
-> times out -> frustration ("looked, found nothing because it's all too repetitive nearby").

Deterministic: the only randomness (the work-vs-leisure kind pick) is a seeded numpy Generator.

Run a demo:  PYTHONPATH=. python eval/mock_world.py
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

from engine.debug import DebugTrace
from engine.runtime import init_runtime
from engine.schema import Mode, PersonaConfig, RawEvent, Scenario
from engine.simulation import tick

ROOT = Path(__file__).resolve().parents[1]
DEFAULTS = ROOT / "calibration" / "defaults.yaml"


@dataclass
class MockWorld:
    """A reactive world: offers activities to a SEEKING NPC from a depleting novelty budget.

    Parameters are the world's "richness", not engine config -- they shape what the NPC can find.
    """

    novelty_start: float = 1.0  # how much fresh stimulation is available at the start
    deplete_per_offer: float = 0.20  # each engagement consumes nearby novelty
    replenish_per_tick: float = (
        0.004  # new options appear over time when the NPC isn't consuming them
    )
    min_novelty: float = (
        0.25  # below this, nothing NEW is nearby -> the world offers nothing
    )
    offer_latency: int = 2  # let the NPC look for a moment before the world confirms
    work_fraction: float = (
        0.0  # P(an offer is `external` work) vs `self_activity` leisure
    )
    seed: int = 0
    budget: float = field(init=False, default=0.0)
    _rng: np.random.Generator = field(init=False, default=None)

    def reset(self) -> None:
        self.budget = self.novelty_start
        self._rng = np.random.default_rng(self.seed)

    def offer(self, t: int, seeking_since: int | None) -> RawEvent | None:
        """Decide this tick's `activity` confirmation for a SEEKING NPC (or None = found nothing)."""
        if seeking_since is None or (t - seeking_since) < self.offer_latency:
            return None  # let it look a moment first
        if self.budget < self.min_novelty:
            return None  # nothing new nearby -> NPC keeps seeking -> timeout
        novelty = float(min(1.0, self.budget))
        kind = (
            "external" if self._rng.random() < self.work_fraction else "self_activity"
        )
        self.budget = max(0.0, self.budget - self.deplete_per_offer)
        return RawEvent(
            type="activity", t=t, context={"kind": kind, "novelty": round(novelty, 3)}
        )

    def replenish(self) -> None:
        self.budget = min(self.novelty_start, self.budget + self.replenish_per_tick)


def run_with_world(
    cfg: PersonaConfig, scenario: Scenario, world: MockWorld, n_ticks: int
) -> DebugTrace:
    """Closed-loop run: the scenario supplies base world events; `world` injects `activity` confirmations
    REACTIVELY whenever the NPC is SEEKING. Returns a DebugTrace (same shape as run_scenario)."""
    runtime = init_runtime(cfg, scenario.initial_overrides)
    base = {ev.t: ev for ev in scenario.events}
    world.reset()
    trace = DebugTrace(persona=cfg.id, scenario=f"{scenario.id}+world", dt=cfg.dt)
    for t in range(n_ticks):
        event = base.get(t)  # a real world event takes priority
        if event is None and runtime.mode == Mode.SEEKING:
            event = world.offer(
                t, runtime.seeking_since
            )  # the world reacts to the NPC seeking
        trace.emit(tick(runtime, t, event))
        if runtime.mode not in (
            Mode.SEEKING,
            Mode.BUSY,
        ):  # options regenerate when not being consumed
            world.replenish()
    return trace


# ============================ demo ============================


def _arc(tag: str, tr: DebugTrace) -> None:
    ticks = tr.ticks
    g0, gN = ticks[0].snapshot.global_state, ticks[-1].state_after_post.global_state
    engaged = [
        tk.selection.action
        for tk in ticks
        if tk.snapshot.mode == Mode.SEEKING and tk.state_after_post.mode == Mode.BUSY
    ]
    timeouts = sum(
        1
        for tk in ticks
        if tk.snapshot.mode == Mode.SEEKING
        and tk.state_after_post.mode == Mode.IDLE
        and tk.selection.kind.name != "REACTIVE"
    )
    outcome = (
        f"ENGAGED {engaged[0]}" if engaged else f"NEVER engaged ({timeouts} give-up(s))"
    )
    print(f"  {tag}: {outcome}")
    print(
        f"     boredom {g0['boredom']:.2f}->{gN['boredom']:.2f}   stress {g0['stress']:.2f}->{gN['stress']:.2f}"
        f"   frustration {g0['frustration']:.2f}->{gN['frustration']:.2f}"
    )


def plot(tr: DebugTrace, path: Path) -> None:
    """Mode band + the day's states, with seek-start (^) and engage (*) markers."""
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    dt = tr.dt
    ts = [tk.t * dt for tk in tr.ticks]
    band = {Mode.IDLE: 0, Mode.SEEKING: 1, Mode.BUSY: 2, Mode.COOLDOWN: 0.5}
    fig, (ax_m, ax_s) = plt.subplots(
        2, 1, figsize=(11, 6), sharex=True, gridspec_kw={"height_ratios": [1, 2]}
    )
    ax_m.step(
        ts,
        [band[tk.state_after_post.mode] for tk in tr.ticks],
        where="post",
        color="#333",
        lw=1.4,
    )
    ax_m.set_yticks([0, 0.5, 1, 2])
    ax_m.set_yticklabels(["IDLE", "COOLDOWN", "SEEKING", "BUSY"])
    ax_m.set_ylabel("mode")
    ax_m.set_title(f"{tr.persona} :: {tr.scenario} (closed loop, dt={dt:.1f}s)")
    for s, c in [
        ("boredom", "#8c564b"),
        ("stress", "#9467bd"),
        ("frustration", "#ff7f0e"),
        ("satisfaction", "#2ca02c"),
    ]:
        ax_s.plot(
            ts,
            [tk.state_after_post.global_state[s] for tk in tr.ticks],
            label=s,
            color=c,
            lw=1.6,
        )
    for tk in tr.ticks:
        if tk.snapshot.mode == Mode.IDLE and tk.state_after_post.mode == Mode.SEEKING:
            ax_s.annotate(
                "^", (tk.t * dt, 1.02), color="#1f77b4", ha="center", fontsize=9
            )  # seek start
        if tk.snapshot.mode == Mode.SEEKING and tk.state_after_post.mode == Mode.BUSY:
            ax_s.annotate(
                "*", (tk.t * dt, 1.02), color="#d62728", ha="center", fontsize=12
            )  # engage
    ax_s.set_ylim(-0.03, 1.08)
    ax_s.set_ylabel("state")
    ax_s.set_xlabel("game time (s)")
    ax_s.legend(loc="upper right", ncol=4, fontsize=8)
    fig.tight_layout()
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=110)
    plt.close(fig)


def main() -> None:
    from eval.calibrated import (
        load_eval_persona,  # M7.5 Part A: believable-day (calibrated+recovery) dynamics
    )

    cfg = load_eval_persona("lutek")  # fast-borer
    primed = {
        "global_state": {
            "boredom": 0.85,
            "stress": 0.50,
            "fatigue": 0.10,
            "frustration": 0.0,
        }
    }
    sc = Scenario(id="primed", persona="lutek", initial_overrides=primed, events=())

    print(
        "Closed loop, the three arcs (short controlled runs isolate the mechanism):\n"
    )
    _arc(
        "LEISURE  (rich world, self_activity)",
        run_with_world(cfg, sc, MockWorld(novelty_start=1.0, work_fraction=0.0), 25),
    )
    _arc(
        "WORK     (rich world, external)",
        run_with_world(cfg, sc, MockWorld(novelty_start=1.0, work_fraction=1.0), 25),
    )
    _arc(
        "CAN'T FIND (empty world -> timeout)",
        run_with_world(cfg, sc, MockWorld(novelty_start=0.0), 30),
    )

    # A fuller day, plotted (the long-day BALANCE is calibration -- placeholders -- but the closed-loop
    # cycle seek->confirm->engage->end->idle->bored->seek is visible).
    day = Scenario(
        id="day",
        persona="lutek",
        initial_overrides={"global_state": {"boredom": 0.4, "fatigue": 0.15}},
        events=(),
    )
    tr = run_with_world(
        cfg,
        day,
        MockWorld(novelty_start=1.0, replenish_per_tick=0.02, work_fraction=0.0),
        300,
    )
    out = ROOT / "eval" / "plots" / "lutek.closed_loop_day.png"
    plot(tr, out)
    print(f"\n  full-day plot -> {out.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
