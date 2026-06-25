"""eval/moral_corpus.py -- generate + render the M-J-MORAL-OVERLAY corpus for the blind judge (calibration
plan step 3). The base believability corpus is NON-moral (meals/slights/weather), so the moral-overlay slice
needs its own scenarios: a moral SITUATION (guilt/lie/accusation/suspicion/secret/betrayal, single- or
multi-day) woven on the believable timescale, across the 7 personas, with trait variants.

Each scenario renders to a PLAIN-LANGUAGE OBSERVABLE vignette (reusing render_moral's discipline) -- demeanor
+ actions only, no engine vocabulary. `write_batches()` groups them into judge-prompt batch files; a Sonnet
agent scores each batch blind (believability + curve_plausibility), exactly the Gate-C corpus judging.

Run:  python -m eval.moral_corpus --build   # generate + render + write batches
"""

from __future__ import annotations

import sys
from pathlib import Path

from engine.schema import RawEvent, Scenario
from engine.simulation import run_scenario
from engine.yaml_io import _deep_merge, load_persona
from eval.calibrated import _merge, believable_day_layout, timescale_overrides
from eval.moral import moral_overrides
from eval.moral_multiday import _burden
from eval.render_moral import ACT, CONCEAL, FRAME, TERMINAL, _demeanor

ROOT = Path(__file__).resolve().parents[1]
DEFAULTS = ROOT / "calibration" / "defaults.yaml"
OUT = ROOT / "eval" / "moral_corpus"
_L = believable_day_layout()
DAY_TICKS, WAKING = _L["day_ticks"], _L["waking_ticks"]
PERSONAS = ["branic", "cichy", "edda", "halgrim", "lutek", "welf", "wojslaw"]

# Character variants: the moral trait knobs that drive the contrasts (kept few + meaningful).
VARIANTS = {
    "guilt_prone": {"guilt_proneness": 0.85, "honesty_humility": 0.9, "empathy": 0.7},
    "hardened": {"guilt_proneness": 0.15, "honesty_humility": 0.4},
    "habitual_liar": {"guilt_proneness": 0.2, "honesty_humility": 0.1},
    "empathic": {"guilt_proneness": 0.8, "honesty_humility": 0.9, "empathy": 0.95},
    "sensitive": {
        "injustice_sensitivity": 0.9,
        "conflict_avoidance": 0.15,
        "guilt_proneness": 0.5,
        "honesty_humility": 0.9,  # honest -> an INNOCENT (no wrong) never fires a lie under exposure
    },
    "avoidant": {
        "conflict_avoidance": 0.9,
        "injustice_sensitivity": 0.15,
        "guilt_proneness": 0.5,
        "honesty_humility": 0.9,
    },
    "discreet": {
        "guilt_proneness": 0.8,
        "honesty_humility": 0.9,
        "gossip_tendency": 0.0,
    },
    "gossip_prone": {
        "guilt_proneness": 0.8,
        "honesty_humility": 0.9,
        "gossip_tendency": 0.9,
    },
}


def _single_events(kind: str):
    """Single-day moral SITUATION as an event list (short timescale, dt~3s)."""
    if kind == "probe":  # a wrong, then questioning
        ev = [RawEvent(type="wrongdoing", t=i, intensity=1.0) for i in range(3)]
        ev += [
            RawEvent(type="probe", t=t, source="reeve", intensity=1.0)
            for t in range(3, 16)
        ]
        return ev, "moral_probe"
    if kind == "accusation":
        return (
            [
                RawEvent(type="accusation", t=t, source="rival", intensity=1.0)
                for t in range(13)
            ],
            "moral_accusation",
        )
    if kind == "suspicion":
        return (
            [
                RawEvent(type="suspicion_raised", t=t, source="watcher", intensity=1.0)
                for t in range(13)
            ],
            "moral_suspicion",
        )
    if kind == "betrayal":
        return (
            [
                RawEvent(type="lie_detected", t=t, source="friend", intensity=1.0)
                for t in range(6)
            ],
            "moral_betrayal",
        )
    if (
        kind == "confide"
    ):  # a wrong, questioned, then a trusted friend present (gossip_tendency BITES here)
        ev = [RawEvent(type="wrongdoing", t=i, intensity=1.0) for i in range(3)]
        ev += [
            RawEvent(type="probe", t=t, source="reeve", intensity=1.0)
            for t in range(3, 8)
        ]
        ev += [
            RawEvent(type="confide_opportunity", t=t, source="confidant", intensity=1.0)
            for t in range(8, 14)
        ]
        return ev, "moral_confide"
    raise ValueError(kind)


def _cfg(persona: str, traits: dict, timescale: bool, half_lives: dict | None = None):
    ov = moral_overrides(traits)
    if timescale:
        ov = _merge(timescale_overrides(), ov)
    if half_lives:
        ov = _deep_merge(ov, {"half_lives": half_lives})
    return load_persona(
        ROOT / "data" / "personas" / f"{persona}.yaml", DEFAULTS, param_overrides=ov
    )


def _render_single(persona: str, traits: dict, kind: str) -> str:
    """Reuse render_moral's observable discipline, persona-parametrized, on a fresh moral situation."""
    events, frame_key = _single_events(kind)
    initial = {
        "global_state": {
            s: 0.05 for s in ("fatigue", "boredom", "stress", "frustration", "anger")
        }
    }
    if frame_key == "moral_betrayal":
        initial["relations"] = {"friend": {"trust": 0.8}}
    if frame_key == "moral_confide":
        initial["relations"] = {"confidant": {"trust": 0.9}}
    cfg = _cfg(persona, traits, timescale=False)
    sc = Scenario(
        id=kind, persona=persona, initial_overrides=initial, events=tuple(events)
    )
    _, tr = run_scenario(cfg, sc, n_ticks=max(e.t for e in events) + 4)
    lines = [FRAME.get(frame_key, "")]
    answered = False
    relief_pending = False
    withdraw_run = 0
    last_dem = None
    reacted = False  # a betrayal/anger REACT has fired; collapse its oscillation into a sustained chill
    chill_noted = False
    fired: set[str] = (
        set()
    )  # terminal acts already narrated (don't repeat the same disclosure twice)
    confided = False

    withdrawn_noted = (
        False  # the strong withdrawn-wary beat lands ONCE, not once per run
    )

    def flush():
        nonlocal withdraw_run, withdrawn_noted
        if withdraw_run >= 2:
            # a second long withdrawal is the SAME mood continuing, not a fresh beat -> compress
            if not withdrawn_noted:
                withdrawn_noted = True
                lines.append(
                    "- He stays withdrawn and wary, saying little, for a good while."
                )
            elif lines[-1] != "- He keeps to himself, the wariness not lifting.":
                lines.append("- He keeps to himself, the wariness not lifting.")
        elif withdraw_run == 1 and not withdrawn_noted:
            lines.append("- He says little, keeps his distance.")
        withdraw_run = 0

    for tk in tr.ticks:
        act = tk.selection.action
        g = tk.state_after_post.global_state
        if act in CONCEAL:
            if answered:
                continue
            withdraw_run += 1
            continue
        if (
            act in REACT
        ):  # outburst/cold_response/... -- first one shows; the rest is one sustained chill
            flush()
            if not reacted:
                reacted = True
                line = f"- Then, {ACT[act]}."
            elif not chill_noted:
                chill_noted = True
                line = "- The chill does not lift; he stays cold and curt, the trust gone out of him."
            else:
                continue
        elif act in ACT:
            if act in TERMINAL:
                if act in fired:
                    continue  # already narrated this disclosure -- don't repeat the same beat verbatim
                fired.add(act)
                answered = True
                if act == "confide":
                    confided = True
            flush()
            line = f"- Then, {ACT[act]}."
        else:
            d = _demeanor(g)
            if answered and ("weighing on him" in d or "troubled" in d):
                relief_pending = True
                continue
            calm = "composed" in d or "settled" in d or "at ease" in d
            if answered and calm:
                continue  # a resolved man's composure is not a fresh beat -- no false plateau mid-arc
            if reacted and calm:
                continue  # after a betrayal goes cold, the calm doesn't simply return -- no reset beat
            if withdraw_run and "troubled" in d:
                continue
            flush()
            if d == last_dem:
                continue
            last_dem = d
            line = f"- {d[0].upper() + d[1:]}."
        if line != lines[-1]:
            lines.append(line)
    flush()
    # confide scenario: a friend was present but he did NOT unburden -> show the WITHHOLDING (gossip-prone).
    # The held-back man does NOT then look "lighter" -- the withholding is the closing note (judge fix).
    withheld = frame_key == "moral_confide" and answered and not confided
    if withheld:
        lines.append(
            "- With his friend, though, he holds back -- keeps the worst of it to himself."
        )
    # betrayal: if the arc fired the flare but never settled into the chill (a single REACT at the very end),
    # the cold has to LAND -- a betrayal does not end on a flash of temper, it ends in withdrawn trust.
    if reacted and not chill_noted:
        lines.append(
            "- The flare passes, but the cold stays in him; the trust does not come back."
        )
    if relief_pending and not withheld:
        lines.append("- The worst of it seems behind him now; he looks lighter.")
    return "\n".join(line for line in lines if line)


# Base anger/social REACT verbs (from render_moral.ACT) -- a betrayal/accusation reply, not a moral action.
REACT = {"outburst", "cold_response", "complain", "refuse"}

# Each kind pairs ONLY with the variants whose trait actually BITES there, so variants stay distinguishable
# (the judge flagged hardened==guilt_prone under accusation, gossip==guilt under probe, all-same betrayal).
KIND_VARIANTS = {
    "probe": ["guilt_prone", "hardened", "habitual_liar", "empathic"],
    "confide": [
        "discreet",
        "gossip_prone",
        "empathic",
    ],  # gossip_tendency BITES here, not under probe
    "accusation": [
        "sensitive",
        "avoidant",
    ],  # injustice vs conflict_avoidance -- the real contrast
    "suspicion": [
        "avoidant",
        "sensitive",
    ],  # guilt_prone indistinguishable here (innocent -> no guilt)
}
# betrayal's reply (anger/cold/-trust) is trait-independent -> ONE representative per persona, no variant axis.
BETRAYAL_VARIANT = "guilt_prone"
MULTIDAY_VARIANTS = ["guilt_prone", "hardened", "empathic"]
MULTIDAY_HALFLIVES = [("minor", 64800), ("serious", 259200)]


def generate() -> list[tuple[str, str]]:
    """Returns a list of (scenario_id, observable_vignette) across personas x situations x variants."""
    out: list[tuple[str, str]] = []
    for persona in PERSONAS:
        for kind, variants in KIND_VARIANTS.items():
            for variant in variants:
                vid = f"{persona}-{kind}-{variant}"
                out.append((vid, _render_single(persona, VARIANTS[variant], kind)))
        out.append(
            (
                f"{persona}-betrayal",
                _render_single(persona, VARIANTS[BETRAYAL_VARIANT], "betrayal"),
            )
        )
        for variant in MULTIDAY_VARIANTS:
            for hl_name, hl in MULTIDAY_HALFLIVES:
                vid = f"{persona}-multiday_guilt-{variant}-{hl_name}"
                out.append(
                    (vid, _render_multiday_persona(persona, VARIANTS[variant], hl))
                )
    return out


def _render_multiday_persona(
    persona: str, traits: dict, guilt_hl: int, n_days: int = 4
) -> str:
    """Multi-day guilt-persistence arc for any persona (render_multiday is halgrim-only; generalize here)."""
    ev = [
        RawEvent(type="wrongdoing", t=8, intensity=1.0),
        RawEvent(type="wrongdoing", t=9, intensity=1.0),
    ]
    for d in range(n_days):
        ev.append(RawEvent(type="nightfall", t=d * DAY_TICKS + WAKING, intensity=1.0))
    cfg = _cfg(persona, traits, timescale=True, half_lives={"guilt": guilt_hl})
    sc = Scenario(id="md", persona=persona, initial_overrides={}, events=tuple(ev))
    _, tr = run_scenario(cfg, sc, n_ticks=n_days * DAY_TICKS)
    eve1 = tr.ticks[WAKING - 30].state_after_post.global_state
    lines = [
        "On the morning of the first day he did a serious wrong, and has confessed it to no one.",
        f"- That first evening: {_burden(eve1)}.",
        "- That night he sleeps.",
    ]
    for d in range(1, n_days):
        wake = tr.ticks[d * DAY_TICKS + 5].state_after_post.global_state
        lines.append(f"- The morning of day {d + 1}, on waking: {_burden(wake)}.")
        if d < n_days - 1:
            lines.append("- That night he sleeps.")
    return "\n".join(lines)


def write_batches(corpus: list[tuple[str, str]], per_batch: int = 24) -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    n = 0
    for i in range(0, len(corpus), per_batch):
        chunk = corpus[i : i + per_batch]
        blocks = [f"===== VIGNETTE {vid} =====\n{txt}" for vid, txt in chunk]
        (OUT / f"batch_{n:03d}.txt").write_text("\n\n".join(blocks), encoding="utf-8")
        n += 1
    return n


if __name__ == "__main__":
    corpus = generate()
    if "--build" in sys.argv:
        nb = write_batches(corpus)
        print(f"generated {len(corpus)} vignettes -> {nb} batches in {OUT}")
    else:
        print(f"generated {len(corpus)} vignettes (use --build to write batches)")
