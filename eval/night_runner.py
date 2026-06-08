"""eval/night_runner.py -- a multi-day day/night runner for the sleep dynamics (M7.5 Part B).

Builds a multi-day scenario (per-day event bursts + a `nightfall`) and runs it through the engine so the
sleep cycle can be observed over 2 days (short) or several (long): the FAST states reset each night while
the SLOW relational causes (a grudge built from insults AND from one's own outbursts at the provoker)
PERSIST across nights and compound day over day. Personas stay STATIC -- this only schedules world events;
no trait/param change. Deterministic.

Run a demo:  PYTHONPATH=. python eval/night_runner.py
"""

from __future__ import annotations

from pathlib import Path
from typing import Callable

from engine.schema import Mode, RawEvent, Scenario
from engine.simulation import run_scenario
from engine.yaml_io import load_persona

ROOT = Path(__file__).resolve().parents[1]
DEFAULTS = ROOT / "calibration" / "defaults.yaml"

DAY_LEN = 260  # ticks per day (dt=3s): room for a morning of events + settle + a night of sleep
NIGHTFALL_OFFSET = 120  # tick within the day when night falls (well after the morning provocations settle)


def build_scenario(
    persona: str,
    days: int,
    day_events: Callable[[int], list[tuple[int, dict]]],
    day_len: int = DAY_LEN,
    nightfall_offset: int = NIGHTFALL_OFFSET,
    initial: dict | None = None,
) -> Scenario:
    """day_events(day_index) -> [(offset_within_day, event_dict)]; a `nightfall` is appended each day."""
    evs: list[RawEvent] = []
    for d in range(days):
        base = d * day_len
        for off, e in day_events(d):
            evs.append(
                RawEvent(
                    type=e["type"],
                    t=base + off,
                    source=e.get("source"),
                    item=e.get("item"),
                    intensity=e.get("intensity", 1.0),
                    context=e.get("context", {}),
                )
            )
        evs.append(RawEvent(type="nightfall", t=base + nightfall_offset, intensity=1.0))
    evs.sort(key=lambda e: e.t)
    return Scenario(
        id=f"{persona}_{days}day",
        persona=persona,
        initial_overrides=initial or {},
        events=tuple(evs),
    )


def run_nights(
    persona: str,
    days: int,
    day_events: Callable[[int], list[tuple[int, dict]]] | None = None,
    day_len: int = DAY_LEN,
    nightfall_offset: int = NIGHTFALL_OFFSET,
    initial: dict | None = None,
    defaults=DEFAULTS,
):
    cfg = load_persona(ROOT / "data" / "personas" / f"{persona}.yaml", defaults)
    sc = build_scenario(
        persona, days, day_events or (lambda d: []), day_len, nightfall_offset, initial
    )
    _, tr = run_scenario(cfg, sc, n_ticks=days * day_len)
    return cfg, tr


def day_summaries(
    tr, days: int, source: str | None = None, day_len: int = DAY_LEN
) -> list[dict]:
    """Per-day digest: did it sleep, peak vs dawn anger, and (optional) resentment[source] at dusk/dawn."""
    out = []
    for d in range(days):
        win = [tk for tk in tr.ticks if d * day_len <= tk.t < (d + 1) * day_len]
        anger = [tk.state_after_post.global_state["anger"] for tk in win]
        rec = {
            "day": d,
            "slept": any(tk.state_after_post.mode == Mode.SLEEP for tk in win),
            "outbursts": sum(1 for tk in win if tk.selection.action == "outburst"),
            "peak_anger": round(max(anger), 3),
            "min_anger": round(min(anger), 3),  # the sleep-bottom -- the night's reset
            "dawn_anger": round(
                anger[0], 3
            ),  # first tick of the day = just after the prior night
            "dusk_anger": round(anger[-1], 3),
        }
        if source is not None:
            res = [
                tk.state_after_post.relations.get(source, {}).get("resentment", 0.0)
                for tk in win
            ]
            rec["resentment_dawn"] = round(res[0], 3)
            rec["resentment_dusk"] = round(res[-1], 3)
        out.append(rec)
    return out


# ============================ demo ============================


def _insults(
    source: str, n: int, start: int = 6, gap: int = 7
) -> Callable[[int], list[tuple[int, dict]]]:
    """A day where `source` provokes the NPC `n` times (each a public insult -> a likely outburst)."""
    return lambda d: [
        (
            start + i * gap,
            {
                "type": "insult",
                "source": source,
                "intensity": 0.9,
                "context": {"public": True},
            },
        )
        for i in range(n)
    ]


def main() -> None:
    print(
        "Few-day night cycle -- Wojsław provoked daily by Marta (numerous outbursts -> a hardening grudge):\n"
    )
    cfg, tr = run_nights(
        "wojslaw",
        days=4,
        day_events=_insults("marta", 4),
        initial={"global_state": {"fatigue": 0.5}},
    )
    for r in day_summaries(tr, 4, source="marta"):
        print(
            f"  day {r['day']}: slept={r['slept']} outbursts={r['outbursts']:2}  "
            f"anger peak={r['peak_anger']} dawn={r['dawn_anger']} dusk={r['dusk_anger']}  "
            f"resentment[marta] dawn={r['resentment_dawn']} dusk={r['resentment_dusk']}"
        )
    print(
        "\n  -> anger resets every night (low dawn); resentment[marta] climbs and never falls back: the"
    )
    print(
        "     grudge built from the day's outbursts survives each night and compounds (the 'hate' hardens)."
    )


if __name__ == "__main__":
    main()
