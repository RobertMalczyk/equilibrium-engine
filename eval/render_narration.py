"""eval/render_narration.py -- render one day of a persona's life as a PLAIN-LANGUAGE,
OBSERVABLE narration, for the BLIND believability judge (eval/blind_judge_plan.md, Phase 1).

The judge must rate a *character*, not an engine. So this renderer emits ONLY what a bystander
in the room could see: what happened around the persona, what the persona did, and a coarse read
of their mood as it drifts. It MUST NOT leak any of the engine's vocabulary -- no state/action
mechanism names, no trait numbers, no "expected" behaviour. Every mechanism is mapped to neutral
plain language (the tables below).

Deterministic: the calibrated+recovery eval dynamics (eval.calibrated.load_eval_persona) driven
through the standard "mixed" mock-world (eval.mock_world), exactly the path eval/judge_corpus.py
uses. Day selection is deterministic too (lowest-numbered day matching the persona's characteristic
event mix, else day_001).

Run:  PYTHONPATH=. python eval/render_narration.py
"""

from __future__ import annotations

from pathlib import Path

import eval.mock_world as mw
from engine.schema import RawEvent, Scenario
from engine.yaml_io import load_scenario
from eval.calibrated import load_eval_persona

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "eval" / "narrations"

PERSONAS = ["halgrim", "wojslaw", "cichy", "branic", "lutek", "welf", "edda"]
DISPLAY = {
    "halgrim": "Halgrim",
    "wojslaw": "Wojsław",
    "cichy": "Cichy",
    "branic": "Branic",
    "lutek": "Lutek",
    "welf": "Welf",
    "edda": "Edda",
}
# How an onlooker would name the other people in the fort (no roles that give away the test).
WHO = {
    "halgrim": "Halgrim",
    "wojslaw": "Wojsław",
    "cichy": "Cichy",
    "branic": "Branic",
    "lutek": "Lutek",
    "welf": "Welf",
    "edda": "Edda",
    "marta": "Marta",
    "player": "a stranger",
    "guard": "one of the guards",
}

N_TICKS = 4800  # ~4 game-hours at dt=3s (08:00 -> 12:00)
MOOD_EVERY = 600  # a coarse mood read every ~30 game-min (600 ticks * 3s = 1800s)
START_HOUR = 8  # notional 08:00 start

# Pronouns per persona (so Edda, the castellan, isn't narrated as "he").
PRON = {p: ("he", "him", "himself", "his") for p in PERSONAS}
PRON["edda"] = ("she", "her", "herself", "her")

# --- mechanism -> plain language (the de-biasing maps; observable only) ----------------
# {r} = reflexive pronoun (himself/herself), filled per persona at render time.

# Reactive actions are RESPONSES (they only fire within ~10 ticks of a provocation). So they are
# rendered ONLY attached to the event that provoked them -- never as a free-standing "he snaps at
# nothing" line (a delayed discharge of an already-shown event would misread as unmotivated). Proactive
# actions (seek/activity/rest) are self-driven and DO render standalone. This split keeps each reaction
# tied to its visible cause; it is an honest rendering choice (noted here so it's auditable).
REACTIVE = {
    "cold_response",
    "outburst",
    "complain",
    "refuse",
    "cooperate",
    "positive_response",
}

# M2 -- positive-valence events. A kindness (soup, a hand) that lands while the persona happens to be
# resting / busy gets no REACTIVE action that tick, so it used to fall to the slight-style "lets it pass,
# no notable reaction" -- reading a benign act as a snub. These events are instead acknowledged mildly
# (a nod), never the slight phrase. (If the persona DOES warm up, the reactive `positive_response` line
# above already fires; this branch is only the no-hostile-reaction fallback.)
POSITIVE_EVENTS = {"food_given", "help"}

ACTION_PLAIN = {
    "neutral": None,  # nothing notable -> no line
    "cold_response": "answers curtly and coldly",
    "outburst": "flares up and snaps angrily",
    "refuse": "refuses -- won't do it",
    "cooperate": "does as asked",
    "complain": "grumbles and complains",
    "positive_response": "takes the kindness warmly, with a word of thanks",  # Theme A: warm reply
    "seek_stimulus": "grows restless, casting about for something to do",
    "self_activity": "occupies {r} -- tinkering, pacing, passing the time",
    "external": "busies {r} with work",
    "rest": "sits down to rest",
    "command_other": "takes charge -- sets the watch in order and directs the others to their tasks",
}

# Fix 2 -- GRADED reaction intensity at the EXPRESSION seam (D11 "one volume"). The engine already carries
# the reaction's magnitude as the potential score (ActionSelection.score); nothing in the ENGINE changes --
# the narration just EXPRESSES that magnitude in tiers instead of one fixed phrase, so a barely-crossed
# reply reads milder than a full one. Tiers are an expression choice (ascending score cutoffs); the score
# bands are presentation placeholders, not engine parameters.
REACTIVE_TIERS = {
    "cold_response": [
        (0.0, "answers a shade curtly"),
        (0.62, "answers curtly and coldly"),
        (0.80, "answers with cold, cutting contempt"),
    ],
    "outburst": [
        (0.0, "bristles, on the edge of anger"),
        (0.62, "flares up and snaps angrily"),
        (0.80, "erupts, shouting in fury"),
    ],
    "complain": [
        (0.0, "mutters a complaint"),
        (0.55, "grumbles and complains"),
        (0.78, "complains loudly and bitterly"),
    ],
    "refuse": [
        (0.0, "declines to"),
        (0.60, "refuses -- won't do it"),
        (0.82, "flatly, defiantly refuses"),
    ],
    "cooperate": [(0.0, "does as asked"), (0.70, "sets to it at once")],
    "positive_response": [
        (0.0, "gives a nod of thanks"),
        (0.55, "takes the kindness warmly, with a word of thanks"),
        (0.80, "is visibly warmed, and thanks them gladly"),
    ],
}


def reaction_phrase(action: str, score: float) -> str | None:
    """The graded expression of a reactive action, by its potential score (Fix 2). Falls back to the flat
    phrasing for anything without tiers."""
    tiers = REACTIVE_TIERS.get(action)
    if not tiers:
        return ACTION_PLAIN.get(action)
    phrase = tiers[0][1]
    for thr, ph in tiers:
        if score >= thr:
            phrase = ph
    return phrase


def _person(src: str | None) -> str:
    if not src:
        return "someone"
    return WHO.get(src, src.capitalize())


def event_phrase(ev: RawEvent, obj: str) -> str:
    """What an onlooker sees happen TO the persona (no mechanism, no expected reaction).
    `obj` = object pronoun (him/her)."""
    who = _person(ev.source)
    public = bool(ev.context.get("public"))
    if ev.type == "insult":
        where = " in front of the others" if public else ""
        return f"{who} mocks {obj}, a barbed remark{where}"
    if ev.type == "command":
        return f"{who} orders {obj} to get something done"
    if ev.type == "food_given":
        item = (ev.item or "food").replace("_", " ")
        return f"{who} brings {obj} a bowl of {item}"
    if ev.type == "help":
        return f"{who} lends {obj} a hand, does {obj} a small kindness"
    return f"{who} {ev.type}s {obj}"


# M1 -- the bearing read must weigh residual ANGER, not just stress. After an outburst the stress base
# can ebb while anger is still high; keying only on stress then prints "settled, at ease" minutes after a
# flare-up (the settled<->fury contradiction the blind judge flagged). These bands are EXPRESSION constants
# (presentation cutoffs on the observable state), not engine parameters: a body still carrying high anger
# reads as seething regardless of a low stress base; a moderate residual keeps the bearing off "settled".
ANGER_SEETHING = 0.60  # residual anger this high reads as still-seething whatever the stress base
ANGER_TENSE = 0.30  # this much residual anger keeps the bearing off "settled, at ease"
# M1 refinement -- "still seething" is ACTIVE fury and only reads right when a provocation is RECENT.
# A slow-decaying residual sampled by the ~hourly mood heartbeat, far from any visible cause, must read as
# a LINGERING temper, not seething-at-nothing (the over-surfacing the re-judge flagged: 117/144 burst-ON
# "seething with no visible provocation"). Freshness window + what counts as a provocation, expression-side.
ANGER_FRESH_SECS = 3600.0  # a provocation within ~1 game-hour justifies the active "seething" read
HOSTILE_REACTIONS = {"outburst", "cold_response", "complain", "refuse"}


def mood_phrase(g: dict, anger_fresh: bool = True) -> str:
    """A bystander's read of the persona's bearing -- NO numbers. The boredom/frustration colouring must not
    CONTRADICT the stress base: a calm (low-stress) body that is bored/frustrated reads 'restless'/'out of
    sorts', NOT 'settled, at ease, and plainly out of sorts' (the self-contradiction the blind judge flagged).
    Residual ANGER overrides a low-stress base (M1): one does not read 'at ease' while still angry. But high
    anger reads as ACTIVE fury ("still seething") only when a provocation is recent (`anger_fresh`); a stale
    residual reads as a LINGERING temper instead, so it never looks like seething-at-nothing."""
    s = g.get("stress", 0.0)
    anger = g.get("anger", 0.0)
    bored = g.get("boredom", 0.0) > 0.60
    out_of_sorts = g.get("frustration", 0.0) > 0.55
    # High residual anger dominates the read -- the body is still visibly angry even if stress has ebbed.
    if anger >= ANGER_SEETHING:
        base = (
            "is still seething, jaw tight"
            if anger_fresh
            else "still hasn't quite shaken off an earlier temper"
        )
        if bored:
            base += ", restless with it"
        elif out_of_sorts:
            base += ", and plainly out of sorts"
        return base
    # calm body -- low stress AND no lingering anger; the colouring REPLACES "at ease", not appends
    if s < 0.30 and anger < ANGER_TENSE:
        if bored:
            return "looks restless and a little bored, though not on edge"
        if out_of_sorts:
            return "seems a touch out of sorts, though outwardly calm"
        return "looks settled, at ease"
    # tense band -- driven by the stress base OR a moderate residual anger
    base = (
        "looks tense, a little on edge"
        if s < 0.60
        else "is wound tight, clearly on edge"
    )
    if bored:
        base += ", visibly restless and bored"
    elif out_of_sorts:
        base += ", and plainly out of sorts"
    return base


def clock(t: int, dt: float) -> str:
    total = int(round(t * dt))
    hh = START_HOUR + total // 3600
    mm = (total % 3600) // 60
    return f"{hh:02d}:{mm:02d}"


# --- deterministic, informative day selection -----------------------------------------


def _has(evs, etype, source=None) -> bool:
    return any(e.type == etype and (source is None or e.source == source) for e in evs)


def _day_is_informative(persona: str, evs) -> bool:
    if persona == "halgrim":
        return (
            _has(evs, "command", "edda")
            and _has(evs, "command", "wojslaw")
            and _has(evs, "insult", "wojslaw")
        )
    if persona in ("wojslaw", "cichy", "edda"):
        return _has(evs, "insult") and (_has(evs, "command") or _has(evs, "food_given"))
    if persona == "branic":
        return _has(evs, "command", "halgrim") and _has(evs, "insult", "halgrim")
    if persona in ("lutek", "welf"):
        return _has(evs, "insult")
    return False


def select_day(persona: str) -> tuple[int, Scenario]:
    """Lowest-numbered day whose events carry the persona's characteristic mix; else day_001."""
    for idx in range(1, 101):
        sc = load_scenario(
            ROOT
            / "eval"
            / "scenarios"
            / "day"
            / persona
            / f"{persona}_day_{idx:03d}.yaml"
        )
        if _day_is_informative(persona, sc.events):
            return idx, sc
    return 1, load_scenario(
        ROOT / "eval" / "scenarios" / "day" / persona / f"{persona}_day_001.yaml"
    )


def _world() -> mw.MockWorld:
    # The standard "mixed" world (same as judge_corpus.py): some leisure, some work.
    return mw.MockWorld(
        novelty_start=1.0, replenish_per_tick=0.012, work_fraction=0.35, seed=7
    )


# --- the narration --------------------------------------------------------------------


def render(persona: str) -> tuple[str, int]:
    cfg = load_eval_persona(persona)
    day_idx, scenario = select_day(persona)
    tr = mw.run_with_world(cfg, scenario, _world(), N_TICKS)
    dt = cfg.dt
    ticks = tr.ticks
    name = DISPLAY[persona]
    subj, obj, refl, _poss = PRON[persona]
    Subj = subj.capitalize()

    lines: list[str] = [f"# {name} -- a day", ""]
    lines.append(
        f"An account of one ordinary day, hour by hour: what happened around {obj} and how {subj}"
    )
    lines.append(f"carried {refl} through it. (Times are the clock on the wall.)")
    lines.append("")

    prev_act = "neutral"
    last_window = -1
    window_emitted: set[str] = set()
    last_prov_secs: float | None = None  # game-time of the last visible provocation (M1 recency gate)

    for i, tk in enumerate(ticks):
        t = tk.t
        # mood heartbeat at each ~30-min window boundary
        win = t // MOOD_EVERY
        if win != last_window:
            last_window = win
            window_emitted = set()
            if t > 0:
                g = tk.state_after_post.global_state
                anger_fresh = (
                    last_prov_secs is not None
                    and (t * dt - last_prov_secs) <= ANGER_FRESH_SECS
                )
                lines.append(
                    f"- **{clock(t, dt)}** -- {Subj} {mood_phrase(g, anger_fresh)}."
                )

        ev = tk.event
        act = tk.selection.action

        # a real forcing event (not a world activity-confirmation)
        if ev is not None and ev.type != "activity":
            # the visible reaction: the first REACTIVE action at/within ~3 ticks of the event
            # (a coincidental proactive action nearby is NOT a response -> "lets it pass").
            reaction, reaction_score = "neutral", 0.0
            for j in range(i, min(i + 4, len(ticks))):
                # Don't reach PAST a later forcing event -- its reaction belongs to IT, not to this one.
                # (Theme A: stops a subsequent insult's outburst being stapled onto an earlier benign soup.)
                if (
                    j > i
                    and ticks[j].event is not None
                    and ticks[j].event.type != "activity"
                ):
                    break
                if ticks[j].selection.action in REACTIVE:
                    reaction, reaction_score = (
                        ticks[j].selection.action,
                        ticks[j].selection.score,
                    )
                    break
            # M1 recency: a visible provocation (an insult, or a hostile reaction) refreshes the
            # window in which "still seething" reads as motivated.
            if ev.type == "insult" or reaction in HOSTILE_REACTIONS:
                last_prov_secs = t * dt
            phrase = event_phrase(ev, obj)
            phrase = (
                phrase[0].upper() + phrase[1:]
            )  # sentence-start capital ("One of the guards ...")
            tail = reaction_phrase(
                reaction, reaction_score
            )  # Fix 2: graded by the reaction's score
            if tail:
                lines.append(
                    f"- **{clock(t, dt)}** -- {phrase}. {Subj} {tail.format(r=refl)}."
                )
                window_emitted.add(
                    ACTION_PLAIN.get(reaction)
                )  # don't echo the same reaction as a bare line next tick
            elif ev.type in POSITIVE_EVENTS:
                # M2: a kindness with no hostile reaction is acknowledged, never the slight-style phrase.
                # Composes with M1: if still angry, the next mood heartbeat reads "still seething" --
                # "takes it ... still tense" rather than feigned warmth.
                lines.append(
                    f"- **{clock(t, dt)}** -- {phrase}. {Subj} takes it without fuss, a small nod."
                )
            else:
                lines.append(
                    f"- **{clock(t, dt)}** -- {phrase}. {Subj} lets it pass, no notable reaction."
                )
            prev_act = reaction
            continue

        # a change of what he's DOING -- proactive only (reactive actions render with their event,
        # above). Collapse repeats within the same ~30-min window.
        if act != prev_act:
            plain = ACTION_PLAIN.get(act)
            if act not in REACTIVE and plain and plain not in window_emitted:
                lines.append(f"- **{clock(t, dt)}** -- {Subj} {plain.format(r=refl)}.")
                window_emitted.add(plain)
            prev_act = act

    lines.append("")
    return "\n".join(lines), day_idx


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    print("Rendering blind-judge narrations (observable-only):\n")
    for p in PERSONAS:
        text, day_idx = render(p)
        path = OUT / f"{p}_day.md"
        path.write_text(text, encoding="utf-8")
        n = text.count("\n- ")
        print(
            f"  {p:9} day_{day_idx:03d}  ->  {path.relative_to(ROOT)}  ({n} timeline lines)"
        )


if __name__ == "__main__":
    main()
