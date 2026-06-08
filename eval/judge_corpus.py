"""eval/judge_corpus.py -- behavioral SIGNATURE extractor for believability review of the day corpus.

The day corpus (eval/scenarios/day/, 700 files) is QA FORCING INPUT: the "assertion" is a reviewer's
judgment of whether each persona lives a believable, in-character day -- NOT a numeric predicate. This
script does NOT pass/fail anything; it runs a sample of each persona's days (on the calibrated+recovery
eval dynamics + the closed-loop mock-world) and prints a per-persona behavioral SIGNATURE for the human/LLM
reviewer: the action mix, mode fractions, the state arcs, the seek/engage/timeout pattern, and -- crucially
-- how the persona RESPONDS to each kind of forcing event (the litmus contrasts, in the wild).

Deterministic (load_eval_persona + seeded mock-world). Run:  PYTHONPATH=. python eval/judge_corpus.py
"""

from __future__ import annotations

from collections import Counter, defaultdict
from pathlib import Path

import numpy as np

import eval.mock_world as mw
from engine.schema import Mode
from engine.yaml_io import load_scenario
from eval.calibrated import believable_day_layout, load_eval_persona_timescale

ROOT = Path(__file__).resolve().parents[1]
DAY_TICKS = believable_day_layout()[
    "day_ticks"
]  # one believable 24 h day (events + a night)
SAMPLE_DAYS = 20  # days per persona to sample for the signature (of 100)
PERSONAS = ["halgrim", "wojslaw", "cichy", "branic", "lutek", "welf", "edda"]


# A standard "mixed" world for the review (some leisure, some work). Non-seekers ignore it.
def _world() -> mw.MockWorld:
    return mw.MockWorld(
        novelty_start=1.0, replenish_per_tick=0.012, work_fraction=0.35, seed=7
    )


def _response_to_events(tr) -> dict:
    """For each forcing event, the NPC's action at that tick (or first non-neutral within 3 ticks)."""
    out: dict[str, Counter] = defaultdict(Counter)
    ticks = tr.ticks
    {tk.t: i for i, tk in enumerate(ticks)}
    for i, tk in enumerate(ticks):
        ev = tk.event
        if (
            ev is None or ev.type == "activity"
        ):  # only the world's forcing events, not activity confirms
            continue
        act = tk.selection.action
        if act == "neutral":
            for j in range(i + 1, min(i + 4, len(ticks))):
                if ticks[j].selection.action != "neutral":
                    act = ticks[j].selection.action
                    break
        key = f"{ev.type}/{ev.source}" if ev.source else ev.type
        out[key][act] += 1
    return out


def signature(persona: str) -> dict:
    cfg = load_eval_persona_timescale(persona)
    actions = Counter()
    modes = Counter()
    resp: dict[str, Counter] = defaultdict(Counter)
    stress, boredom, frustr, satis = [], [], [], []
    seek = engage = timeout = 0
    narration = None
    for idx in range(1, SAMPLE_DAYS + 1):
        sc = load_scenario(
            ROOT
            / "eval"
            / "scenarios"
            / "day"
            / persona
            / f"{persona}_day_{idx:03d}.yaml"
        )
        tr = mw.run_with_world(cfg, sc, _world(), DAY_TICKS)
        for tk in tr.ticks:
            actions[tk.selection.action] += 1
            modes[tk.state_after_post.mode.value] += 1
        g = [tk.state_after_post.global_state for tk in tr.ticks]
        stress += [s["stress"] for s in g]
        boredom += [s["boredom"] for s in g]
        frustr += [s["frustration"] for s in g]
        satis += [s["satisfaction"] for s in g]
        seek += sum(
            1
            for tk in tr.ticks
            if tk.snapshot.mode == Mode.IDLE
            and tk.state_after_post.mode == Mode.SEEKING
        )
        engage += sum(
            1
            for tk in tr.ticks
            if tk.snapshot.mode == Mode.SEEKING
            and tk.state_after_post.mode == Mode.BUSY
        )
        timeout += sum(
            1
            for tk in tr.ticks
            if tk.snapshot.mode == Mode.SEEKING
            and tk.state_after_post.mode == Mode.IDLE
            and tk.selection.kind.name != "REACTIVE"
        )
        for k, c in _response_to_events(tr).items():
            resp[k].update(c)
        if narration is None:
            narration = [
                (
                    tk.t,
                    (tk.event.type + "/" + str(tk.event.source)) if tk.event else "",
                    tk.selection.action,
                )
                for tk in tr.ticks
                if tk.event is not None or tk.selection.action not in ("neutral",)
            ][:14]
    return {
        "persona": persona,
        "traits": cfg.traits,
        "actions": actions,
        "modes": modes,
        "resp": resp,
        "stress": (np.mean(stress), np.max(stress)),
        "boredom": np.mean(boredom),
        "frustr": np.mean(frustr),
        "satis": np.mean(satis),
        "seek": seek,
        "engage": engage,
        "timeout": timeout,
        "narration": narration,
    }


def main() -> None:
    print(
        f"Behavioral signatures over {SAMPLE_DAYS} sampled days/persona (calibrated+recovery + mixed mock-world):\n"
    )
    for p in PERSONAS:
        s = signature(p)
        t = s["traits"]
        tot = sum(s["actions"].values())
        amix = ", ".join(
            f"{a} {100 * n / tot:.0f}%" for a, n in s["actions"].most_common() if n
        )
        mtot = sum(s["modes"].values())
        mmix = ", ".join(
            f"{m} {100 * n / mtot:.0f}%" for m, n in s["modes"].most_common()
        )
        print(
            f"== {p}  (nov={t['novelty_seeking']:.2f} stoic={t['stoicism']:.2f} pride={t['pride']:.2f} "
            f"self_ctrl={t['base_self_control']:.2f}) =="
        )
        print(f"  actions: {amix}")
        print(
            f"  modes:   {mmix}    seek={s['seek']} engage={s['engage']} timeout={s['timeout']}"
        )
        print(
            f"  state:   stress mean={s['stress'][0]:.2f} max={s['stress'][1]:.2f}  boredom={s['boredom']:.2f}  "
            f"frustr={s['frustr']:.2f}  satis={s['satis']:.2f}"
        )
        print("  responses to forcing events:")
        for k in sorted(s["resp"]):
            c = s["resp"][k]
            print(
                f"     {k:18} -> " + ", ".join(f"{a} {n}" for a, n in c.most_common())
            )
        print()


if __name__ == "__main__":
    main()
