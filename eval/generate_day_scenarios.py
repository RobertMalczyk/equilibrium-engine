"""Seeded generator for "normal day" persona-dynamics scenarios (PREPARE ONLY).

Emits ~100 scenarios per persona (7 personas -> ~700 YAML files), each a 3-4 hour
"normal day" for that persona. Events are drawn from a PER-PERSONA distribution that
reflects the persona's social role (see PROFILES below).

This script ONLY generates + parse-validates files; it NEVER runs them through the
engine (no run_scenario / simulation). Validation = engine.yaml_io.load_scenario, which
parses and schema-checks each file.

EVENT VOCABULARY (the engine rejects anything else; see engine/mapper.py):
    food_given : a meal/feeding         (item, intensity ~1.0)
    insult     : a slight               (context {public: bool})
    help       : someone assists        (intensity)
    command    : someone orders the NPC (context {has_authority: bool})
The persona is always the SUBJECT; every event is something done TO it by a `source`.
A "normal day" has no neutral "meeting"/"social" event in the catalog, so social
contact is expressed through these four verbs (mostly help/command for benign contact,
meals for routine, the occasional insult for friction). See README.md for the mapping.

TIME: dt = 3.0 game-seconds/tick. A 3-4 h day = ~3600..4800 ticks. Event `t` is an
INTEGER tick index; most ticks carry NO event; events are spread across the day and
sorted by t (load_scenario also re-sorts).

DETERMINISM (a project pillar): every persona+index pair derives its own seed from a
fixed scheme (see _seed_for); all sampling goes through numpy's Generator. Re-running
the generator reproduces byte-identical files.

SOURCES: only an `initial_relations` source the persona actually has a relation with may
appear as an event `source` (the engine reads relation[source]). cichy is the sole
exception: like prisoner_bias_resentful.yaml it introduces a `guard` via a minimal
initial_overrides.relations block, so the guard is a valid related source for that day.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import yaml

from engine.yaml_io import load_scenario
from eval.calibrated import believable_day_layout

# --- day layout (the BELIEVABLE timescale; see calibration/calibrated_timescale.yaml + timescale_keeper) ---
# Events sit across the WAKING day (dawn -> nightfall); a `nightfall` closes the day so the night/sleep
# reset runs. Run each scenario through load_eval_persona_timescale for DAY_TICKS ticks (one 24 h day).
SCENARIOS_PER_PERSONA = 100
_LAYOUT = believable_day_layout()
DAY_TICKS = _LAYOUT["day_ticks"]  # ~24 h (one full day + night) at dt ~120 s
WAKING_TICKS = _LAYOUT[
    "waking_ticks"
]  # ~17 h dawn->nightfall; events live in [0, WAKING_TICKS]
GLOBAL_SEED = 20260605  # generator-wide salt for reproducibility


@dataclass(frozen=True)
class Channel:
    """One event channel in a per-persona day profile.

    A channel produces events of a single `type` from a chosen `source`. The number of
    events is drawn per day; meals use a roughly scheduled count (Normal around a routine
    baseline) while slights/help/commands use Poisson counts (sparse, bursty triggers
    layered ON TOP of the routine). Timing is sampled across the day window.
    """

    type: str  # one of {food_given, insult, help, command}
    sources: tuple[str, ...]  # candidate sources (relation must exist)
    count_dist: str  # "normal" (routine) | "poisson" (triggers)
    count_mean: float  # mean number of events per day
    count_sd: float = 0.0  # SD for the "normal" count distribution
    item: str | None = None  # for food_given (affinity lookup)
    intensity_mean: float = 1.0
    intensity_sd: float = 0.0
    public_p: float = 0.0  # P(public) for insults
    has_authority: bool = False  # command authority flag
    schedule: tuple[float, ...] = ()  # fractional day positions for routine meals
    source_weights: tuple[
        float, ...
    ] = ()  # optional per-source weights (default = uniform)
    count_min: int = 0  # floor on the per-day event count (default = none)


@dataclass(frozen=True)
class Profile:
    """A persona's whole-day event mix + a minimal mood/relation baseline."""

    persona: str
    channels: tuple[Channel, ...]
    # Minimal, justified initial_overrides (kept sparse per CLAUDE.md "less is more").
    global_overrides: dict[str, float] = field(default_factory=dict)
    relation_overrides: dict[str, dict[str, float]] = field(default_factory=dict)


# =====================================================================================
# PER-PERSONA DAY PROFILES
# Roles + relation graph from docs/rpg_persona_dynamics_persony.md; sources restricted to
# each persona's initial_relations (cichy adds `guard` via overrides, as prisoner_bias does).
# Counts: meals = Normal around a routine baseline; slights/help/commands = Poisson triggers.
# =====================================================================================
PROFILES: dict[str, Profile] = {
    # Prisoner: mostly NOTHING. Long idle stretches; ~2-3 meals, the occasional guard
    # slight, rare help. A resented guard (overrides, like prisoner_bias_resentful).
    "cichy": Profile(
        persona="cichy",
        channels=(
            Channel(
                "food_given",
                ("guard",),
                "normal",
                2.5,
                0.5,
                item="cabbage_soup",
                intensity_mean=1.0,
                schedule=(0.15, 0.5, 0.85),
            ),
            Channel(
                "insult",
                ("guard",),
                "poisson",
                1.2,
                intensity_mean=0.7,
                intensity_sd=0.15,
                public_p=0.1,
            ),
            Channel(
                "help",
                ("player",),
                "poisson",
                0.4,
                intensity_mean=0.6,
                intensity_sd=0.18,
            ),
        ),
        global_overrides={"boredom": 0.30, "frustration": 0.10},
        relation_overrides={
            "guard": {"trust": 0.05, "respect": 0.10, "resentment": 0.85}
        },
    ),
    # Proud noble: SOCIAL all day. Frequent commands he gives/receives, help, meals; plus
    # slights layered under a Normal-count baseline (easily slighted). Sources: marta, player.
    "wojslaw": Profile(
        persona="wojslaw",
        channels=(
            Channel(
                "food_given",
                ("marta",),
                "normal",
                3.0,
                0.7,
                item="cabbage_soup",
                schedule=(0.1, 0.45, 0.8),
            ),
            Channel(
                "help",
                ("marta", "player"),
                "poisson",
                3.5,
                intensity_mean=0.8,
                intensity_sd=0.18,
            ),
            Channel(
                "command",
                ("player",),
                "poisson",
                2.0,
                intensity_mean=0.72,
                intensity_sd=0.20,
                has_authority=True,
            ),
            Channel(
                "insult",
                (
                    "player",
                ),  # COHERENCE: the warm cook (marta) feeds/helps -- she does NOT also mock
                # him. Friction comes from the player/stranger; pairing insults with the
                # kind-giver produced the incoherent "Marta mocks then feeds you" -> the
                # engine correctly resents her -> her later soup gall read as "snaps at soup".
                "normal",
                2.5,
                0.8,
                intensity_mean=0.7,
                intensity_sd=0.2,
                public_p=0.5,
            ),
        ),
        global_overrides={},
    ),
    # Watch sergeant: duty rhythm. Commands from Edda, some friction from Wojslaw, meals.
    "halgrim": Profile(
        persona="halgrim",
        channels=(
            Channel(
                "food_given",
                ("marta",),
                "normal",
                2.5,
                0.5,
                item="cabbage_soup",
                schedule=(0.12, 0.5, 0.88),
            ),
            Channel(
                "command",
                ("edda", "wojslaw"),
                "poisson",
                2.5,
                intensity_mean=0.72,
                intensity_sd=0.20,
                has_authority=True,
                source_weights=(2.0, 1.0),
            ),  # ~1/3 of orders from RESENTED Wojslaw -> refuse days appear
            Channel(
                "insult",
                ("wojslaw",),
                "poisson",
                1.0,
                intensity_mean=0.6,
                intensity_sd=0.15,
                public_p=0.3,
            ),
            Channel(
                "help",
                ("player", "marta"),
                "poisson",
                1.5,
                intensity_mean=0.7,
                intensity_sd=0.18,
            ),
        ),
        global_overrides={},
    ),
    # Castellan (authority): runs the fort. Gives orders (commands TO her are rare; she is
    # consulted/helped), meals, occasional friction. Sources: halgrim, marta, player.
    "edda": Profile(
        persona="edda",
        channels=(
            Channel(
                "food_given",
                ("marta",),
                "normal",
                3.0,
                0.5,
                item="cabbage_soup",
                schedule=(0.1, 0.45, 0.8),
            ),
            Channel(
                "help",
                ("halgrim", "marta", "player"),
                "poisson",
                3.0,
                intensity_mean=0.8,
                intensity_sd=0.18,
            ),
            Channel(
                "command",
                ("player",),
                "poisson",
                0.6,
                intensity_mean=0.72,
                intensity_sd=0.20,
                has_authority=True,
            ),
            Channel(
                "insult",
                ("player",),
                "poisson",
                0.5,
                intensity_mean=0.5,
                intensity_sd=0.15,
                public_p=0.4,
            ),
        ),
        global_overrides={},
    ),
    # Recruit: bores fast on watch; mentored/commanded by Halgrim, slight resentment at his
    # harshness. Meals, commands from halgrim, help, occasional sharp word. Sources: halgrim, marta, player.
    "branic": Profile(
        persona="branic",
        channels=(
            Channel(
                "food_given",
                ("marta",),
                "normal",
                2.5,
                0.5,
                item="cabbage_soup",
                schedule=(0.13, 0.5, 0.85),
            ),
            Channel(
                "command",
                ("halgrim",),
                "poisson",
                3.0,
                intensity_mean=0.72,
                intensity_sd=0.20,
                has_authority=True,
            ),
            Channel(
                "help",
                (
                    "marta",
                    "player",
                ),  # COHERENCE: Halgrim is the harsh MENTOR (commands + sharp words,
                # below). The warm "lends a hand" gestures come from marta/player,
                # not from the sergeant who's been on his back -- so a kindness no
                # longer galls because its giver just mocked/ordered him.
                "poisson",
                2.0,
                intensity_mean=0.75,
                intensity_sd=0.18,
            ),
            Channel(
                "insult",
                ("halgrim",),
                "poisson",
                1.2,
                intensity_mean=0.6,
                intensity_sd=0.15,
                public_p=0.2,
            ),
        ),
        global_overrides={"boredom": 0.20},
    ),
    # Wandering poet: bores fastest; neutral-warm to all, turns insults into jokes (MVP: no
    # burst). Light social day: meals, help, rare slights. Sources: player, marta.
    "lutek": Profile(
        persona="lutek",
        channels=(
            Channel(
                "food_given",
                ("marta",),
                "normal",
                2.5,
                0.6,
                item="cabbage_soup",
                schedule=(0.15, 0.5, 0.85),
            ),
            Channel(
                "help",
                ("player", "marta"),
                "poisson",
                2.5,
                intensity_mean=0.8,
                intensity_sd=0.18,
            ),
            Channel(
                "insult",
                ("player",),
                "poisson",
                0.8,
                intensity_mean=0.6,
                intensity_sd=0.2,
                public_p=0.3,
            ),
        ),
        global_overrides={"boredom": 0.25},
    ),
    # Merchant stranded by weather: transactional, composed; high boredom in idleness. Sparse
    # social contact (only player as a relation): a few meals, occasional help, rare slight.
    "welf": Profile(
        persona="welf",
        channels=(
            Channel(
                "food_given",
                ("player",),
                "normal",
                2.5,
                0.6,
                item="cabbage_soup",
                schedule=(0.15, 0.5, 0.85),
            ),
            Channel(
                "help",
                ("player",),
                "poisson",
                1.5,
                intensity_mean=0.7,
                intensity_sd=0.18,
                count_min=1,
            ),  # floor: every Welf day has >=1 reactive event
            Channel(
                "insult",
                ("player",),
                "poisson",
                0.4,
                intensity_mean=0.5,
                intensity_sd=0.15,
                public_p=0.2,
            ),
        ),
        global_overrides={"boredom": 0.30},
    ),
}


def _seed_for(persona: str, index: int) -> int:
    """Deterministic per-(persona, index) seed.

    A stable hash of "persona:index" mixed with GLOBAL_SEED, so the stream for one file is
    independent of generation order and reproducible across runs/machines.
    """
    raw = f"{GLOBAL_SEED}:{persona}:{index}".encode("utf-8")
    digest = hashlib.sha256(raw).digest()
    return int.from_bytes(digest[:8], "big")


def _draw_count(rng: np.random.Generator, ch: Channel) -> int:
    """Number of events for a channel on this day (>= count_min, >= 0)."""
    if ch.count_dist == "poisson":
        n = int(rng.poisson(ch.count_mean))
    elif ch.count_dist == "normal":
        n = int(max(0, round(rng.normal(ch.count_mean, ch.count_sd))))
    else:
        raise ValueError(f"unknown count_dist: {ch.count_dist}")
    return max(ch.count_min, n)


def _draw_intensity(rng: np.random.Generator, ch: Channel) -> float:
    """Intensity in [0, 1] (Normal around the channel mean, then clamped)."""
    val = (
        rng.normal(ch.intensity_mean, ch.intensity_sd)
        if ch.intensity_sd > 0
        else ch.intensity_mean
    )
    return float(min(1.0, max(0.0, val)))


def _routine_ticks(
    rng: np.random.Generator, ch: Channel, n: int, day_ticks: int
) -> list[int]:
    """Ticks for routine (scheduled) events: jitter the day-fraction schedule slots."""
    ticks: list[int] = []
    for i in range(n):
        frac = (
            ch.schedule[i % len(ch.schedule)] if ch.schedule else (i + 0.5) / max(n, 1)
        )
        jitter = rng.normal(0.0, 0.03)  # +/- ~3% of the day around the slot
        t = int(round((frac + jitter) * day_ticks))
        ticks.append(min(day_ticks - 1, max(0, t)))
    return ticks


def _trigger_ticks(rng: np.random.Generator, n: int, day_ticks: int) -> list[int]:
    """Ticks for stochastic triggers (slights/help/commands): uniform across the day."""
    if n == 0:
        return []
    return [int(rng.integers(0, day_ticks)) for _ in range(n)]


def _build_events(
    rng: np.random.Generator, profile: Profile, day_ticks: int
) -> list[dict]:
    """Assemble one day's event list (unsorted; load_scenario sorts by t)."""
    events: list[dict] = []
    for ch in profile.channels:
        n = _draw_count(rng, ch)
        if n == 0:
            continue
        is_routine = ch.type == "food_given" and bool(ch.schedule)
        ticks = (
            _routine_ticks(rng, ch, n, day_ticks)
            if is_routine
            else _trigger_ticks(rng, n, day_ticks)
        )
        for t in ticks:
            if ch.source_weights:  # weighted pick (e.g. Halgrim: 2/3 Edda, 1/3 Wojslaw)
                p = np.asarray(ch.source_weights, dtype=float)
                source = ch.sources[int(rng.choice(len(ch.sources), p=p / p.sum()))]
            else:
                source = ch.sources[int(rng.integers(0, len(ch.sources)))]
            ev: dict = {
                "type": ch.type,
                "t": int(t),
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
            else:  # help
                ev["context"] = {}
            events.append(ev)
    events.sort(key=lambda e: (e["t"], e["type"], e["source"]))
    return events


def _dedupe_ticks(events: list[dict], max_tick: int) -> list[dict]:
    """One event per tick: the runner keys events by tick, so same-tick events would be DROPPED. Shift any
    collision forward to the next free tick (rare with a handful of events across the waking day)."""
    events = sorted(events, key=lambda e: (e["t"], e["type"], e.get("source", "")))
    used: set[int] = set()
    for e in events:
        t = e["t"]
        while t in used and t < max_tick - 1:
            t += 1
        e["t"] = t
        used.add(t)
    return events


def _build_overrides(profile: Profile) -> dict:
    """Minimal initial_overrides block (omitted entirely when empty)."""
    overrides: dict = {}
    if profile.global_overrides:
        overrides["global_state"] = dict(profile.global_overrides)
    if profile.relation_overrides:
        overrides["relations"] = {
            s: dict(d) for s, d in profile.relation_overrides.items()
        }
    return overrides


def _scenario_dict(profile: Profile, index: int) -> dict:
    rng = np.random.default_rng(_seed_for(profile.persona, index))
    events = _build_events(
        rng, profile, WAKING_TICKS
    )  # placed across the WAKING day (dawn->nightfall)
    events = _dedupe_ticks(events, WAKING_TICKS)  # one event per tick
    events.append(
        {"type": "nightfall", "t": WAKING_TICKS, "intensity": 1.0}
    )  # close the day -> night/sleep
    events.sort(key=lambda e: (e["t"], e["type"]))
    return {
        "id": f"{profile.persona}_day_{index:03d}",
        "persona": profile.persona,
        "initial_overrides": _build_overrides(profile),
        "events": events,
    }


def _write_yaml(path: Path, scenario: dict) -> None:
    header = (
        f"# GENERATED 'normal day' scenario (eval/generate_day_scenarios.py).\n"
        f"# Persona: {scenario['persona']}. A believable 24 h day: events across the ~17 h WAKING day\n"
        f"# (meals at meal-times, sparse triggers), then a `nightfall` -> the night/sleep reset. Run via\n"
        f"# load_eval_persona_timescale for {DAY_TICKS} ticks (dt ~120 s). Deterministic: seed =\n"
        f"# sha256(GLOBAL_SEED:persona:index). Vocabulary {{food_given, insult, help, command, nightfall}}.\n"
    )
    body = yaml.safe_dump(
        scenario, sort_keys=False, default_flow_style=False, allow_unicode=False
    )
    path.write_text(header + body, encoding="utf-8")


def main() -> None:
    out_root = Path(__file__).resolve().parent / "scenarios" / "day"
    out_root.mkdir(parents=True, exist_ok=True)

    total = 0
    parsed_ok = 0
    failures: list[str] = []

    for persona, profile in PROFILES.items():
        persona_dir = out_root / persona
        persona_dir.mkdir(parents=True, exist_ok=True)
        for index in range(1, SCENARIOS_PER_PERSONA + 1):
            scenario = _scenario_dict(profile, index)
            path = persona_dir / f"{persona}_day_{index:03d}.yaml"
            _write_yaml(path, scenario)
            total += 1
            # Parse-validate ONLY (never run_scenario).
            try:
                loaded = load_scenario(path)
                assert loaded.id == scenario["id"]
                assert loaded.persona == persona
                parsed_ok += 1
            except Exception as exc:  # noqa: BLE001 -- report any validation failure
                failures.append(f"{path.name}: {exc}")

    print(f"Generated {total} files across {len(PROFILES)} personas.")
    print(f"Parsed cleanly via load_scenario: {parsed_ok}/{total}.")
    if failures:
        print(f"FAILURES ({len(failures)}):")
        for f in failures:
            print(f"  - {f}")
    else:
        print("All files parsed cleanly.")


if __name__ == "__main__":
    main()
