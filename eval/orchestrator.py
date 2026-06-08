"""eval/orchestrator.py -- the multi-agent cross-agent ROUTER (live-multi-agency FIRST SLICE).

The per-persona engine is a pure function (`tick(runtime, t, event)`) -- it never reaches into another
persona's runtime. This orchestrator is the generalization of `eval/mock_world.py` (the single-agent
reactive injector) to a ROSTER, and it is the ONE place cross-agent wiring lives. It realizes the authority
verb: when an issuer's engine SELECTS `command_other`, the orchestrator turns it into an inbound `command`
event for a chosen subordinate -- who then resolves it through the EXISTING, untouched obedience pipeline
(`command_pressure` -> per-source `cooperate`/`refuse`, spec section 8).

Discipline (spec section 8 / `docs/diagrams/orchestrator.md`):
  * TWO PHASE, frozen-then-deliver. Phase READ ticks every agent against its own inbox for t (each engine
    reads only its own snapshot). Phase ROUTE (after ALL agents ticked) converts each selected
    `command_other` into a `command` event enqueued for delivery at t+1 -- a ONE-TICK DELAY. So no agent's
    within-tick state depends on another agent's same-tick output: the synchronous / single-frozen-snapshot
    invariant holds ACROSS agents, and the run is bit-for-bit deterministic (sorted roster + deterministic
    target pick).
  * BACK-EDGE OFF: a subordinate's cooperate/refuse does NOT feed back to the issuer. The cross-agent path
    is pure feedforward (command -> obedience) -- no new loop. (The authority<->resentment back-edge is the
    deferred stage-2 step; see Ideas/stage2_multiagency_authority.md.)

Run a demo:  PYTHONPATH=. python eval/orchestrator.py
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import eval.mock_world as mw
from engine.debug import DebugTrace
from engine.runtime import init_runtime
from engine.schema import Mode, PersonaConfig, RawEvent, Scenario
from engine.simulation import tick

ROOT = Path(__file__).resolve().parents[1]


def _route_target(issuer: str, candidates: list[str], n_issued: int) -> str | None:
    """Deterministic target pick: round-robin over the issuer's ordered subordinate list (the issuer's
    n-th order goes to candidates[n mod len]). No randomness; reproducible. An in-engine target *policy*
    (command the lowest-respect subordinate, etc.) is deferred (spec section 8 open decision #2)."""
    if not candidates:
        return None
    return candidates[n_issued % len(candidates)]


def _enqueue(inbox: dict[int, RawEvent], ev: RawEvent, t_deliver: int) -> None:
    """Deliver at t_deliver, but never clobber an already-queued event (decision #5: world event wins,
    the command re-queues to the next free tick). Deterministic."""
    t = t_deliver
    while t in inbox:
        t += 1
    inbox[t] = RawEvent(
        type=ev.type,
        t=t,
        source=ev.source,
        target=ev.target,
        intensity=ev.intensity,
        context=ev.context,
    )


@dataclass
class Roster:
    """A multi-agent run: per-persona runtimes + per-persona inboxes + a per-persona activity world.

    `targets[issuer]` is the ordered list of subordinates that issuer's `command_other` is routed to
    (round-robin). `order_intensity` is the command's strength (-> command_pressure for the subordinate).
    """

    configs: dict[str, PersonaConfig]
    targets: dict[str, list[str]] = field(default_factory=dict)
    order_intensity: float = 1.0
    world_kwargs: dict = field(default_factory=dict)

    def run(
        self, scenarios: dict[str, Scenario], n_ticks: int
    ) -> dict[str, DebugTrace]:
        agents = sorted(self.configs)  # canonical (sorted) iteration -> determinism
        runtimes = {
            a: init_runtime(
                self.configs[a],
                scenarios[a].initial_overrides if a in scenarios else None,
            )
            for a in agents
        }
        inboxes: dict[str, dict[int, RawEvent]] = {a: {} for a in agents}
        for a in agents:  # seed inboxes with each agent's world events
            for ev in scenarios[a].events if a in scenarios else ():
                inboxes[a][ev.t] = ev
        worlds = {a: mw.MockWorld(**self.world_kwargs) for a in agents}
        for w in worlds.values():
            w.reset()
        traces = {
            a: DebugTrace(
                persona=self.configs[a].id, scenario="roster", dt=self.configs[a].dt
            )
            for a in agents
        }
        issued: dict[str, int] = {
            a: 0 for a in agents
        }  # per-issuer order count (round-robin index)

        for t in range(n_ticks):
            # PHASE READ -- tick every agent against its own inbox (each reads only its own snapshot).
            commanders: list[str] = []
            for a in agents:
                rt = runtimes[a]
                event = inboxes[a].pop(
                    t, None
                )  # a delivered event (world or a routed command)
                if event is None and rt.mode == Mode.SEEKING:
                    event = worlds[a].offer(
                        t, rt.seeking_since
                    )  # the world reacts to a seeking NPC
                tk = tick(rt, t, event)
                traces[a].emit(tk)
                if tk.selection.action == "command_other":
                    commanders.append(a)
                if rt.mode not in (Mode.SEEKING, Mode.BUSY):
                    worlds[a].replenish()
            # PHASE ROUTE -- turn each selected command_other into a subordinate's command event at t+1.
            for issuer in commanders:  # `commanders` is in sorted order already
                tgt = _route_target(
                    issuer, self.targets.get(issuer, []), issued[issuer]
                )
                issued[issuer] += 1
                if tgt is not None and tgt in inboxes:
                    _enqueue(
                        inboxes[tgt],
                        RawEvent(
                            type="command",
                            t=t + 1,
                            source=issuer,
                            intensity=self.order_intensity,
                            context={"has_authority": True},
                        ),
                        t + 1,
                    )
        return traces


# ============================ demo ============================


def main() -> None:
    from eval.calibrated import load_eval_persona

    agents = (
        ["edda", "halgrim", "marta"]
        if (ROOT / "data" / "personas" / "marta.yaml").exists()
        else ["edda", "halgrim"]
    )
    configs = {a: load_eval_persona(a) for a in agents}
    scenarios = {
        a: Scenario(
            id="idle",
            persona=a,
            initial_overrides={
                "global_state": {"boredom": 0.10, "fatigue": 0.20, "stress": 0.10}
            },
            events=(),
        )
        for a in agents
    }
    roster = Roster(
        configs=configs,
        targets={"edda": [a for a in agents if a != "edda"]},
        world_kwargs=dict(
            novelty_start=1.0, replenish_per_tick=0.012, work_fraction=0.35, seed=7
        ),
    )
    traces = roster.run(scenarios, n_ticks=2400)

    print(
        "Roster run (Edda commands; subordinates resolve via the EXISTING obedience pipeline):\n"
    )
    edda_orders = [
        tk.t for tk in traces["edda"].ticks if tk.selection.action == "command_other"
    ]
    print(
        f"  edda issued {len(edda_orders)} order(s) at ticks {edda_orders[:8]}{'...' if len(edda_orders) > 8 else ''}"
    )
    for a in agents:
        if a == "edda":
            continue
        reacts = [
            (tk.t, tk.selection.action)
            for tk in traces[a].ticks
            if tk.selection.action in ("cooperate", "refuse", "cold_response")
        ]
        print(
            f"  {a:8} reacted to orders: {reacts[:8]}{'...' if len(reacts) > 8 else ''}"
        )


if __name__ == "__main__":
    main()
