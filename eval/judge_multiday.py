"""eval/judge_multiday.py -- the fresh-agent JUDGE layer for the multi-day corpus (the 'reads believably' half).

Renders a multi-day scenario as an OBSERVABLE, numbers-free, mechanism-free account (reusing the blind-judge
phrase helpers) and pairs it with the persona's plain-language profile + a rubric. A FRESH agent then judges:

  (a) does it MAKE SENSE as a stretch of days in a life? (sane pacing -- not starving in minutes, not enraged
      for no reason, sleeps at night and wakes recovered, the days feel like days; nothing absurd), and
  (b) is it NOT WRONG for this person? (consistent with the profile).

This is NOT a test of persona DIFFERENCES (proven elsewhere) -- only the general working of the model.

Run:  PYTHONPATH=. python eval/judge_multiday.py            # write a sample of judge prompts to disk
      PYTHONPATH=. python eval/judge_multiday.py --list      # list the sample
"""

from __future__ import annotations

from pathlib import Path

import yaml

from engine.schema import Mode
from engine.yaml_io import load_scenario
from eval.calibrated import believable_day_layout, load_eval_persona_timescale
from eval.render_narration import (
    ACTION_PLAIN,
    ANGER_FRESH_SECS,
    DISPLAY,
    HOSTILE_REACTIONS,
    POSITIVE_EVENTS,
    PRON,
    REACTIVE,
    event_phrase,
    mood_phrase,
    reaction_phrase,
)
from eval.sanity_multiday import run_multiday

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "eval" / "judge_multiday"
_L = believable_day_layout()
DAY_TICKS, WAKING, DT = _L["day_ticks"], _L["waking_ticks"], _L["dt"]
DAWN_HOUR = 6
MOOD_EVERY = 60  # a mood read ~every 2 h (60 ticks * 120 s)

# A representative sample: per persona, a couple of indices chosen to cover varied day types.
SAMPLE = {p: (1, 2) for p in DISPLAY}


def _abs_hours(t: int) -> float:
    """Hours since midnight of display-day 1. t=0 is dawn of day 1 (06:00); a sim-day is DAY_TICKS long."""
    return DAWN_HOUR + t * 24.0 / DAY_TICKS


def disp_day(t: int) -> int:
    """The calendar day a tick falls in, ROLLING at midnight (not at dawn). So an agitated persona still
    awake at 00:30 reads as the next day's small hours -- never '00:30' tagged under the previous day after
    a 22:58 line (the out-of-order glitch)."""
    return int(_abs_hours(t) // 24) + 1


def clock(t: int) -> str:
    h = _abs_hours(t) % 24.0
    return f"Day {disp_day(t)}, {int(h):02d}:{int(h % 1 * 60):02d}"


def render(persona: str, index: int) -> tuple[str, list[str]]:
    cfg = load_eval_persona_timescale(persona)
    path = (
        ROOT
        / "eval"
        / "scenarios"
        / "multiday"
        / persona
        / f"{persona}_multi_{index:03d}.yaml"
    )
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    n_days, day_plan = raw["n_days"], raw["day_plan"]
    sc = load_scenario(path)
    return narrate(persona, cfg, sc, n_days), day_plan


def narrate(persona: str, cfg, sc, n_days: int) -> str:
    """The observable, numbers-free record of an n-day run (1 day = the day corpus; the regression
    judge reuses this for BOTH corpora). Extracted from render() unchanged."""
    tr = run_multiday(cfg, sc, n_days)
    ticks = tr.ticks
    name = DISPLAY[persona]
    subj, obj, refl, _ = PRON[persona]
    Subj = subj.capitalize()

    lines = [
        f"# {name} -- {n_days} days",
        "",
        f"What an onlooker would see of {name} over {n_days} days and nights: what happened around {obj},",
        f"how {subj} took it, and how {subj} carried {refl} day to day. (No inner numbers -- only the visible.)",
        "",
    ]
    rained_day = -1  # collapse the day's drizzle to one note (keyed on the DISPLAY day)
    prev_act = "neutral"
    last_win = -1
    last_prov_secs: float | None = None  # game-time of the last visible provocation (M1 recency gate)
    in_sleep = False
    header_day = (
        0  # lazily emit "## Day N" before the first real line of each display-day
    )

    def add(tt: int, body: str) -> None:
        """Emit a timeline line, inserting the day header lazily (so a midnight roll yields a clean new
        '## Day N' and never a dangling empty header)."""
        nonlocal header_day
        dd = disp_day(tt)
        if dd != header_day:
            lines.append(f"\n## Day {dd}")
            header_day = dd
        lines.append(f"- **{clock(tt)}** -- {body}")

    for i, tk in enumerate(ticks):
        t = tk.t
        mode = tk.state_after_post.mode
        # sleep span: announce once
        if mode == Mode.SLEEP and not in_sleep:
            add(t, f"night falls; {name} sleeps.")
            in_sleep = True
            continue
        if mode != Mode.SLEEP and in_sleep:
            add(t, f"{name} wakes with the light.")
            in_sleep = False
        if mode == Mode.SLEEP:
            continue
        # mood heartbeat
        win = t // MOOD_EVERY
        if win != last_win:
            last_win = win
            if t % DAY_TICKS > 2:
                anger_fresh = (
                    last_prov_secs is not None
                    and (t * DT - last_prov_secs) <= ANGER_FRESH_SECS
                )
                add(
                    t,
                    f"{Subj} {mood_phrase(tk.state_after_post.global_state, anger_fresh)}.",
                )
        ev = tk.event
        act = tk.selection.action
        if ev is not None and ev.type == "activity":
            pass
        elif ev is not None and ev.type == "weather":
            if rained_day != disp_day(t):  # one drizzle note per display-day
                add(
                    t,
                    f"a cold rain sets in, and keeps on; {name} is out in it on watch.",
                )
                rained_day = disp_day(t)
            continue
        elif ev is not None and ev.type == "nightfall":
            continue
        elif ev is not None:
            reaction, score = "neutral", 0.0
            for j in range(i, min(i + 4, len(ticks))):
                # Don't reach PAST a later forcing event -- its reaction belongs to IT (Theme A: stops a
                # subsequent insult's outburst being stapled onto an earlier benign soup line).
                if (
                    j > i
                    and ticks[j].event is not None
                    and ticks[j].event.type not in ("activity", "weather", "nightfall")
                ):
                    break
                if ticks[j].selection.action in REACTIVE:
                    reaction, score = (
                        ticks[j].selection.action,
                        ticks[j].selection.score,
                    )
                    break
            # M1 recency: a visible provocation (an insult, or a hostile reaction) refreshes the
            # window in which "still seething" reads as motivated.
            if ev.type == "insult" or reaction in HOSTILE_REACTIONS:
                last_prov_secs = t * DT
            phrase = event_phrase(ev, obj)
            phrase = phrase[0].upper() + phrase[1:]
            tail = reaction_phrase(reaction, score)
            if tail:
                add(t, f"{phrase}. {Subj} {tail.format(r=refl)}.")
            elif ev.type in POSITIVE_EVENTS:
                # M2: a kindness with no hostile reaction is acknowledged, never the slight-style phrase.
                add(t, f"{phrase}. {Subj} takes it without fuss, a small nod.")
            else:
                add(t, f"{phrase}. {Subj} lets it pass, no notable reaction.")
            prev_act = reaction
            continue
        if act != prev_act and act not in REACTIVE:
            plain = ACTION_PLAIN.get(act)
            if plain:
                add(t, f"{Subj} {plain.format(r=refl)}.")
            prev_act = act
    return "\n".join(lines)


RUBRIC = """\
You are checking whether a few simulated days of a character read BELIEVABLY. You are NOT comparing
personalities and NOT proving anything about their traits -- only the GENERAL working of the model: does
this look like a sane stretch of days in a life?

# Who this is
{profile}

# The record (a few days, observable -- only what an onlooker could see)
{narration}

# Judge two things, briefly
(a) DOES IT MAKE SENSE as days in a life? Sane pacing -- he is not starving within minutes, not enraged for
    no reason, he sleeps at night and wakes recovered, the rhythm of days feels like days, hunger/temper
    rise and fall over believable spans, nothing absurd. (OK / CONCERN + one or two sentences.)
(b) IS IT NOT WRONG for this person? Nothing here contradicts the profile (a calm man isn't raging all day;
    a hot one isn't a saint). You are NOT asked to prove he differs from anyone -- only that nothing jars.
    (OK / CONCERN + one or two sentences.)

End with a single line: VERDICT: PASS   or   VERDICT: FLAG -- <the one thing that most needs a look>.
"""


def build_prompt(persona: str, index: int) -> str:
    narration, _ = render(persona, index)
    profile = (ROOT / "eval" / "profiles" / f"{persona}.md").read_text(encoding="utf-8")
    return RUBRIC.format(profile=profile, narration=narration)


def main():
    import sys

    OUT.mkdir(parents=True, exist_ok=True)
    if "--list" in sys.argv:
        for p, idxs in SAMPLE.items():
            for i in idxs:
                _, plan = render(p, i)
                print(f"  {p}_multi_{i:03d}: {plan}")
        return
    n = 0
    for p, idxs in SAMPLE.items():
        for i in idxs:
            prompt = build_prompt(p, i)
            (OUT / f"{p}_multi_{i:03d}.prompt.md").write_text(prompt, encoding="utf-8")
            n += 1
    print(
        f"wrote {n} judge prompts to {OUT.relative_to(ROOT)} (profile + observable multi-day record + rubric)."
    )
    print("Each is meant for a SEPARATE fresh-context agent. Sample day-plans:")
    for p, idxs in SAMPLE.items():
        for i in idxs:
            _, plan = render(p, i)
            print(f"  {p}_multi_{i:03d}: {plan}")


if __name__ == "__main__":
    main()
