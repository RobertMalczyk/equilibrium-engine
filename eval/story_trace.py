"""eval/story_trace.py -- extract a TIME-DOMAIN digest of one day per persona, for the LLM story seam.

For each persona it runs the SAME informative day the blind-judge renderer uses (deterministic:
load_eval_persona + the standard mixed mock-world), then prints a compact digest a writer can dramatize
WITHOUT touching the engine: the TRIGGERS (forcing events), the ACTION the persona took, and the LEVELS
(internal state) at that moment, plus the proactive rhythm and the day's arc. This is the expression seam
(deterministic trace -> text), not part of the loop.

Run:  PYTHONPATH=. python eval/story_trace.py
"""

from __future__ import annotations

from pathlib import Path

import eval.mock_world as mw
from engine.schema import Mode
from eval.calibrated import load_eval_persona
from eval.render_narration import (  # reuse day selection + clock
    DISPLAY,
    _world,
    clock,
    select_day,
)

ROOT = Path(__file__).resolve().parents[1]
PERSONAS = ["edda", "halgrim", "wojslaw", "cichy", "branic", "lutek", "welf"]

REACTIVE = {"cold_response", "outburst", "complain", "refuse", "cooperate"}
LVL = ["stress", "anger", "frustration", "boredom", "satisfaction"]


def _who(src):
    return {"player": "a passing stranger", "guard": "a gaoler", None: "someone"}.get(
        src, str(src).capitalize() if src else "someone"
    )


def _trigger(ev):
    pub = " (in front of others)" if ev.context.get("public") else ""
    if ev.type == "insult":
        return f"{_who(ev.source)} hurls a barbed insult{pub}"
    if ev.type == "command":
        return f"{_who(ev.source)} gives an order{pub}"
    if ev.type == "food_given":
        return f"{_who(ev.source)} brings a bowl of {(ev.item or 'food').replace('_', ' ')}"
    if ev.type == "help":
        return f"{_who(ev.source)} offers a hand / a small kindness"
    return f"{_who(ev.source)} {ev.type}"


def _lvls(g, with_duty=False):
    s = " ".join(f"{k[:4]}={g[k]:.2f}" for k in LVL)
    if with_duty:
        s += f" duty={g['duty']:.2f}"
    return s


def digest(persona: str) -> str:
    cfg = load_eval_persona(persona)
    day_idx, sc = select_day(persona)
    tr = mw.run_with_world(cfg, sc, _world(), 4800)
    ticks = tr.ticks
    dt = cfg.dt
    is_edda = persona == "edda"
    out = [f"### {DISPLAY[persona]} -- day {day_idx:03d}"]

    # --- forcing events: trigger -> reaction + levels at the moment ---
    out.append(
        "Triggers & reactions (clock | what happened to them | what they did | inner levels at that moment):"
    )
    for i, tk in enumerate(ticks):
        ev = tk.event
        if ev is None or ev.type == "activity":
            continue
        react = "no notable reaction"
        for j in range(i, min(i + 4, len(ticks))):
            if ticks[j].selection.action in REACTIVE:
                react = ticks[j].selection.action
                break
        g = tk.state_after_post.global_state
        out.append(
            f"  {clock(tk.t, dt)} | {_trigger(ev)} | {react} | {_lvls(g, is_edda)}"
        )

    # --- proactive rhythm (what they did on their own) ---
    prox = [
        (tk.t, tk.selection.action)
        for tk in ticks
        if tk.selection.action
        in ("seek_stimulus", "self_activity", "external", "rest", "command_other")
    ]
    # collapse consecutive repeats
    beats = []
    for t, a in prox:
        if not beats or beats[-1][1] != a:
            beats.append((t, a))
    label = {
        "seek_stimulus": "casts about, restless",
        "self_activity": "occupies self (tinkers/paces)",
        "external": "sets to work",
        "rest": "rests",
        "command_other": "TAKES CHARGE -- directs the others",
    }
    out.append("Proactive beats (self-driven, clock | what they chose to do):")
    for t, a in beats[:40]:
        out.append(f"  {clock(t, dt)} | {label.get(a, a)}")

    # --- the day's arc (levels) ---
    g0 = ticks[0].snapshot.global_state
    gN = ticks[-1].state_after_post.global_state
    peak = {k: max(tk.state_after_post.global_state[k] for tk in ticks) for k in LVL}
    seek = sum(
        1
        for tk in ticks
        if tk.snapshot.mode == Mode.IDLE and tk.state_after_post.mode == Mode.SEEKING
    )
    engage = sum(
        1
        for tk in ticks
        if tk.snapshot.mode == Mode.SEEKING and tk.state_after_post.mode == Mode.BUSY
    )
    n_cmd = sum(1 for tk in ticks if tk.selection.action == "command_other")
    arc = (
        f"Arc: stress {g0['stress']:.2f}->{gN['stress']:.2f} (peak {peak['stress']:.2f}); "
        f"anger peak {peak['anger']:.2f}; frustration peak {peak['frustration']:.2f}; "
        f"boredom {g0['boredom']:.2f}->{gN['boredom']:.2f} (peak {peak['boredom']:.2f}); "
        f"satisfaction peak {peak['satisfaction']:.2f}."
    )
    if seek:
        arc += f" Sought activity {seek}x, engaged {engage}x."
    if n_cmd:
        arc += f" Issued {n_cmd} orders over the day."
    out.append(arc)
    return "\n".join(out)


def _subtext(action: str, g: dict) -> str:
    """A short reading of HOW it felt under the surface (the level as subtext, not a number)."""
    a, s = g["anger"], g["stress"]
    if action == "outburst":
        return "boils over"
    if action == "cold_response":
        return "ice over fury" if a > 0.6 else "a cold, curt answer"
    if action == "cooperate":
        return "obeys though wound tight" if (s > 0.5 or a > 0.4) else "does as bid"
    if action == "refuse":
        return "flatly refuses"
    if action == "no notable reaction":
        return "lets it pass"
    return action


def persona_data(persona: str) -> dict:
    """Structured time-domain data for the interactive explorer: a sampled level SERIES + the EVENT markers
    (each a trigger + the action taken + the levels at that tick + a short faithful prose line)."""
    cfg = load_eval_persona(persona)
    day_idx, sc = select_day(persona)
    tr = mw.run_with_world(cfg, sc, _world(), 4800)
    ticks, dt = tr.ticks, cfg.dt
    name = DISPLAY[persona]
    keys = LVL + (["duty"] if persona == "edda" else [])

    # sampled series (every ~40 ticks -> ~120 points) for the plot lines
    series = []
    for i in range(0, len(ticks), 40):
        g = ticks[i].state_after_post.global_state
        series.append(
            {
                "t": ticks[i].t,
                "clock": clock(ticks[i].t, dt),
                **{k: round(g[k], 3) for k in keys},
            }
        )

    # event markers: each forcing event, its reaction, the levels, and a prose beat
    events = []
    for i, tk in enumerate(ticks):
        ev = tk.event
        if ev is None or ev.type == "activity":
            continue
        react = "no notable reaction"
        for j in range(i, min(i + 4, len(ticks))):
            if ticks[j].selection.action in REACTIVE:
                react = ticks[j].selection.action
                break
        g = tk.state_after_post.global_state
        trig = _trigger(ev)
        events.append(
            {
                "id": f"{persona}-{len(events)}",
                "t": tk.t,
                "clock": clock(tk.t, dt),
                "kind": "trigger",
                "etype": ev.type,
                "source": ev.source or "",
                "trigger": trig[0].upper() + trig[1:],
                "action": react,
                "subtext": _subtext(react, g),
                "prose": f"{trig[0].upper() + trig[1:]} — {name} {_subtext(react, g)}.",
                "levels": {k: round(g[k], 3) for k in keys},
            }
        )

    # FRAME beats: a beat can mark a TIME FRAME (an interval), not just a point. A frame carries t1 (and
    # clock1); the explorer shades that band on the plot. Used for sustained, self-driven stretches.
    def _frame_ticks(actions: set[str]):
        idxs = [tk.t for tk in ticks if tk.selection.action in actions]
        return (idxs[0], idxs[-1], len(idxs)) if idxs else None

    if persona == "edda":
        # the command pulse: one frame spanning all the orders (the duty sawtooth on the plot)
        fr = _frame_ticks({"command_other"})
        if fr:
            t0, t1, n = fr
            events.append(
                {
                    "id": f"{persona}-pulse",
                    "t": t0,
                    "t1": t1,
                    "clock": clock(t0, dt),
                    "clock1": clock(t1, dt),
                    "kind": "frame",
                    "etype": "command_other",
                    "source": "",
                    "trigger": "the command pulse",
                    "action": "command_other",
                    "subtext": "takes charge, ~every 20 min",
                    "prose": (
                        f"Through the morning, the steady pulse of command — {name} sets the watch in order "
                        f"roughly every twenty minutes ({n} times), the plain work of running the keep."
                    ),
                    "levels": {},
                }
            )
    if persona in ("branic", "lutek", "welf"):
        fr = _frame_ticks({"seek_stimulus", "self_activity", "external", "rest"})
        if fr:
            t0, t1, n = fr
            events.append(
                {
                    "id": f"{persona}-churn",
                    "t": t0,
                    "t1": t1,
                    "clock": clock(t0, dt),
                    "clock1": clock(t1, dt),
                    "kind": "frame",
                    "etype": "restless",
                    "source": "",
                    "trigger": "the restless churn",
                    "action": "seek/activity/rest",
                    "subtext": "never still",
                    "prose": (
                        f"Restless the whole morning — a ceaseless cycle of casting about, busying himself, "
                        f"resting, and rising again ({n} stretches), never still for long."
                    ),
                    "levels": {},
                }
            )
    events.sort(key=lambda e: e["t"])

    # ACTION LANE: what the persona was DOING, tick by tick, as a colour strip. Non-neutral runs only
    # (neutral = the blank background), run-length-encoded so it stays compact. This is where the proactive
    # actions live -- seek_stimulus ("looking for an activity"), self_activity, external (work), rest,
    # command_other -- alongside the reactive beats, so the doing is visible, not just the triggers.
    acts: list[dict] = []
    for tk in ticks:
        a = tk.selection.action
        if a == "neutral":
            continue
        if acts and acts[-1]["a"] == a and tk.t == acts[-1]["t1"] + 1:
            acts[-1]["t1"] = tk.t
        else:
            acts.append({"a": a, "t0": tk.t, "t1": tk.t})

    _g0, _gN = ticks[0].snapshot.global_state, ticks[-1].state_after_post.global_state
    peak = {
        k: round(max(tk.state_after_post.global_state[k] for tk in ticks), 3)
        for k in keys
    }
    return {
        "id": persona,
        "name": name,
        "day": day_idx,
        "dt": dt,
        "keys": keys,
        "traits": {k: round(v, 2) for k, v in cfg.traits.items()},
        "series": series,
        "events": events,
        "actions": acts,
        "peak": peak,
        "n_ticks": len(ticks),
    }


def dump_js(path: Path | None = None) -> Path:
    import json

    path = path or (
        ROOT / "eval" / "stories" / "sapkowski_keep" / "explorer" / "story_data.js"
    )
    data = {"personas": [persona_data(p) for p in PERSONAS]}
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "window.STORY_DATA = " + json.dumps(data, ensure_ascii=False) + ";\n",
        encoding="utf-8",
    )
    return path


def main() -> None:
    import sys

    if "--js" in sys.argv:
        p = dump_js()
        print(f"wrote {p.relative_to(ROOT)}  ({len(PERSONAS)} personas)")
        return
    print("TIME-DOMAIN DIGEST (deterministic engine trace -> for the story seam):\n")
    for p in PERSONAS:
        print(digest(p))
        print()


if __name__ == "__main__":
    main()
