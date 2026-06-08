"""Seeded generator for MULTI-DAY persona-dynamics scenarios (the believable timescale).

100 per persona x 7 = 700 files, each a stretch of **3-6 days** at the believable per-dimension timescale
(DAY_TICKS ~717 at dt ~120 s). Each day is a Sapkowski/Witcher-keep-flavoured **DAY TYPE** that reshapes the
day's event mix (still only the engine's verbs + nightfall + the new `weather`):

  ordinary       a normal watch
  feast          a name-day / festival -- extra meals + help, no slights, good cheer
  drill          a hard sergeant drilling the garrison -- many commands, some friction, fewer meals
  bad_blood      a sour day -- slights and harsh orders pile up
  short_rations  a lean stretch (siege / deep winter) -- fewer, thinner meals (hunger climbs over days)
  visitors       a merchant / traveller in -- help + commands from outside (the `player`)
  quiet          an empty, idle stretch -- almost nothing (boredom -> seek over a long day)
  foul_weather   cold rain on watch -- a sustained `weather` stressor through the day

This corpus is FORCING INPUT for a GENERAL-SANITY check (eval/sanity_multiday.py + a per-scenario fresh-agent
judge): does the model behave SENSIBLY over many days at the believable timescale -- the NPC is not starving
in minutes, not saturating, sleeps each night, recovers, reacts in a way that fits the persona? It is NOT a
test of persona DIFFERENCES (that is proven elsewhere). Lore informs the day-type mix; mechanics stay the
engine's. Deterministic: seed = sha256(MULTI_SEED:persona:index). Parse-validated via load_scenario.

Run:  PYTHONPATH=. python eval/generate_multiday_scenarios.py
"""

from __future__ import annotations

import dataclasses
import hashlib
from pathlib import Path

import numpy as np
import yaml

from engine.yaml_io import load_scenario
from eval.calibrated import believable_day_layout
from eval.generate_day_scenarios import (
    PROFILES,
    Channel,
    _build_overrides,
    _draw_count,
    _draw_intensity,
    _routine_ticks,
    _trigger_ticks,
)

ROOT = Path(__file__).resolve().parents[1]
SCENARIOS_PER_PERSONA = 100
MULTI_SEED = 20260608  # generator-wide salt (distinct from the single-day corpus)
DAYS_MIN, DAYS_MAX = 3, 6  # length of the stretch
_LAYOUT = believable_day_layout()
DAY_TICKS = _LAYOUT["day_ticks"]  # ~717 (24 h)
WAKING_TICKS = _LAYOUT["waking_ticks"]  # ~508 (events live here)
RAIN_OFFSETS = tuple(
    range(20, WAKING_TICKS - 20, 60)
)  # a sustained drizzle across a foul-weather day

# Per-verb count multipliers (+ food intensity scale + rain) for each lore-flavoured day type.
DAY_TYPES: dict[str, dict] = {
    "ordinary": dict(
        food_given=1.0, help=1.0, command=1.0, insult=1.0, food_int=1.0, rain=0.0
    ),
    "feast": dict(
        food_given=1.6, help=1.5, command=0.5, insult=0.0, food_int=1.0, rain=0.0
    ),
    "drill": dict(
        food_given=0.9, help=0.7, command=2.0, insult=1.2, food_int=1.0, rain=0.0
    ),
    "bad_blood": dict(
        food_given=1.0, help=0.5, command=1.2, insult=2.2, food_int=1.0, rain=0.0
    ),
    "short_rations": dict(
        food_given=0.5, help=0.8, command=1.0, insult=1.0, food_int=0.55, rain=0.0
    ),
    "visitors": dict(
        food_given=1.1, help=1.8, command=1.3, insult=0.6, food_int=1.0, rain=0.0
    ),
    "quiet": dict(
        food_given=0.9, help=0.3, command=0.3, insult=0.3, food_int=1.0, rain=0.0
    ),
    "foul_weather": dict(
        food_given=1.0, help=0.8, command=1.0, insult=1.0, food_int=1.0, rain=0.6
    ),
}

# Lore-appropriate day types per persona (their world + role).
PERSONA_DAY_TYPES: dict[str, tuple[str, ...]] = {
    "cichy": ("ordinary", "short_rations", "bad_blood", "quiet", "foul_weather"),
    "wojslaw": ("ordinary", "feast", "bad_blood", "visitors", "drill"),
    "halgrim": ("ordinary", "drill", "bad_blood", "visitors", "quiet", "foul_weather"),
    "edda": ("ordinary", "feast", "visitors", "drill", "quiet"),
    "branic": ("ordinary", "drill", "bad_blood", "feast", "quiet", "foul_weather"),
    "lutek": ("ordinary", "feast", "visitors", "quiet"),
    "welf": ("ordinary", "visitors", "short_rations", "quiet", "foul_weather"),
}


def _seed_for(persona: str, index: int) -> int:
    raw = f"{MULTI_SEED}:{persona}:{index}".encode("utf-8")
    return int.from_bytes(hashlib.sha256(raw).digest()[:8], "big")


def _scaled(ch: Channel, dt: dict) -> Channel:
    """A copy of a channel with its day count (and food intensity) scaled by the day type."""
    mult = dt.get(ch.type, 1.0)
    kw = {"count_mean": ch.count_mean * mult}
    if ch.count_min:
        kw["count_min"] = ch.count_min if mult > 0 else 0
    if ch.type == "food_given":
        kw["intensity_mean"] = ch.intensity_mean * dt.get("food_int", 1.0)
    return dataclasses.replace(ch, **kw)


def _day_events(
    rng: np.random.Generator, profile, daytype: str, base: int
) -> list[dict]:
    """One day's events (absolute ticks = base + offset in the waking window), for the given day type."""
    dt = DAY_TYPES[daytype]
    events: list[dict] = []
    for ch0 in profile.channels:
        ch = _scaled(ch0, dt)
        n = _draw_count(rng, ch)
        if n == 0:
            continue
        is_routine = ch.type == "food_given" and bool(ch.schedule)
        ticks = (
            _routine_ticks(rng, ch, n, WAKING_TICKS)
            if is_routine
            else _trigger_ticks(rng, n, WAKING_TICKS)
        )
        for t in ticks:
            if ch.source_weights:
                p = np.asarray(ch.source_weights, dtype=float)
                source = ch.sources[int(rng.choice(len(ch.sources), p=p / p.sum()))]
            else:
                source = ch.sources[int(rng.integers(0, len(ch.sources)))]
            ev: dict = {
                "type": ch.type,
                "t": base + int(t),
                "source": source,
                "intensity": round(_draw_intensity(rng, ch), 3),
            }
            if ch.type == "food_given":
                ev["item"] = ch.item
                ev["context"] = {"public": False}
            elif ch.type == "insult":
                ev["context"] = {"public": bool(rng.random() < ch.public_p)}
            elif ch.type == "command":
                ev["context"] = {"has_authority": ch.has_authority}
            else:
                ev["context"] = {}
            events.append(ev)
    # foul weather: a sustained drizzle across the waking day (intensity jittered around the day-type level)
    if dt["rain"] > 0:
        for off in RAIN_OFFSETS:
            inten = float(min(1.0, max(0.1, rng.normal(dt["rain"], 0.08))))
            events.append(
                {"type": "weather", "t": base + off, "intensity": round(inten, 3)}
            )
    return events


def _dedupe(events: list[dict]) -> list[dict]:
    """One event per tick (the runner keys events by tick). Shift collisions forward to the next free tick."""
    events = sorted(events, key=lambda e: (e["t"], e["type"], e.get("source", "")))
    used: set[int] = set()
    for e in events:
        t = e["t"]
        while t in used:
            t += 1
        e["t"] = t
        used.add(t)
    return events


def _scenario_dict(persona: str, profile, index: int) -> dict:
    rng = np.random.default_rng(_seed_for(persona, index))
    n_days = int(rng.integers(DAYS_MIN, DAYS_MAX + 1))
    types = PERSONA_DAY_TYPES[persona]
    day_plan = [types[int(rng.integers(0, len(types)))] for _ in range(n_days)]
    events: list[dict] = []
    for d, daytype in enumerate(day_plan):
        base = d * DAY_TICKS
        events += _day_events(rng, profile, daytype, base)
        events.append({"type": "nightfall", "t": base + WAKING_TICKS, "intensity": 1.0})
    events = _dedupe(events)
    return {
        "id": f"{persona}_multi_{index:03d}",
        "persona": persona,
        "n_days": n_days,
        "day_plan": day_plan,  # metadata: the lore-flavoured day types (for the judge)
        "initial_overrides": _build_overrides(profile),
        "events": events,
    }


def _write(path: Path, sc: dict) -> None:
    header = (
        f"# GENERATED multi-day scenario (eval/generate_multiday_scenarios.py).\n"
        f"# Persona: {sc['persona']}. {sc['n_days']} days, believable timescale ({DAY_TICKS} ticks/day,\n"
        f"# dt ~120 s); each day a Sapkowski-keep day-type: {', '.join(sc['day_plan'])}.\n"
        f"# Run via load_eval_persona_timescale for n_days*{DAY_TICKS} ticks. Vocabulary {{food_given, insult,\n"
        f"# help, command, weather, nightfall}}. Deterministic: seed = sha256(MULTI_SEED:persona:index).\n"
    )
    body = yaml.safe_dump(
        sc, sort_keys=False, default_flow_style=False, allow_unicode=False
    )
    path.write_text(header + body, encoding="utf-8")


def main() -> None:
    out_root = ROOT / "eval" / "scenarios" / "multiday"
    out_root.mkdir(parents=True, exist_ok=True)
    total = parsed = 0
    failures: list[str] = []
    for persona, profile in PROFILES.items():
        pdir = out_root / persona
        pdir.mkdir(parents=True, exist_ok=True)
        for index in range(1, SCENARIOS_PER_PERSONA + 1):
            sc = _scenario_dict(persona, profile, index)
            path = pdir / f"{persona}_multi_{index:03d}.yaml"
            _write(path, sc)
            total += 1
            try:
                loaded = load_scenario(
                    path
                )  # parse + schema check only (never run here)
                assert loaded.id == sc["id"] and loaded.persona == persona
                parsed += 1
            except Exception as exc:  # noqa: BLE001
                failures.append(f"{path.name}: {exc}")
    print(
        f"Generated {total} multi-day files across {len(PROFILES)} personas ({DAYS_MIN}-{DAYS_MAX} days each)."
    )
    print(f"Parsed cleanly via load_scenario: {parsed}/{total}.")
    for f in failures[:20]:
        print(f"  FAIL {f}")


if __name__ == "__main__":
    main()
