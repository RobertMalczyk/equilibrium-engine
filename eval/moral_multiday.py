"""eval/moral_multiday.py -- M-J.4.4 full-corpus stage: the MULTI-DAY moral runner.

The short litmus scenarios cannot discriminate the moral HALF-LIVES (over ~48s a 12h vs 72h half-life barely
differ). The half-life calibration only shows over MULTI-DAY arcs at the believable timescale (does a serious
wrong still weigh on a man days later?). This runner builds a multi-day moral arc on the believable day
layout (eval.calibrated) and reports the lingering trajectory of a moral state -- the signal the blind judge
(and the §10 objective) score for curve_plausibility.

Verified finding (see docs/moral_calibration_plan.md): with PRIVATE wrongdoing-reminders (no interrogation,
so no confession resolves it), the evening-guilt trajectory cleanly separates by half-life --
6h ~ [0.04, 0.05, 0.05] (forgotten by evening), 18h ~ [0.15, 0.21, 0.23], 72h ~ [0.23, 0.42, 0.56] (a
deepening burden). That separation IS the multi-day calibration signal.
"""

from __future__ import annotations

from pathlib import Path

from engine.schema import RawEvent, Scenario
from engine.simulation import run_scenario
from engine.yaml_io import _deep_merge, load_persona
from eval.calibrated import _merge, believable_day_layout, timescale_overrides
from eval.moral import moral_overrides

ROOT = Path(__file__).resolve().parents[1]
DEFAULTS = ROOT / "calibration" / "defaults.yaml"
HALGRIM = ROOT / "data" / "personas" / "halgrim.yaml"
_L = believable_day_layout()
DAY_TICKS, WAKING = _L["day_ticks"], _L["waking_ticks"]


def _cfg(traits: dict, half_life_overrides: dict | None = None):
    ov = _merge(timescale_overrides(), moral_overrides(traits))
    if half_life_overrides:
        ov = _deep_merge(ov, {"half_lives": half_life_overrides})
    return load_persona(HALGRIM, DEFAULTS, param_overrides=ov)


def single_wrong_arc(traits: dict, half_lives: dict, n_days: int = 4):
    """A multi-day arc: ONE serious wrong on the morning of day 1 (a SELF cue -- raises guilt, opens no reply
    window, so nothing resolves it), then nightfall each evening. The cleanest half-life persistence test:
    how the single wrong's guilt fades (or doesn't) over the following days/nights. Returns (cfg, trace)."""
    ev: list[RawEvent] = [
        RawEvent(type="wrongdoing", t=8, intensity=1.0),
        RawEvent(type="wrongdoing", t=9, intensity=1.0),
    ]
    for d in range(n_days):
        ev.append(RawEvent(type="nightfall", t=d * DAY_TICKS + WAKING, intensity=1.0))
    cfg = _cfg(traits, half_lives)
    sc = Scenario(
        id="md_moral", persona="halgrim", initial_overrides={}, events=tuple(ev)
    )
    return cfg, run_scenario(cfg, sc, n_ticks=n_days * DAY_TICKS)[1]


def waking_guilt(traits: dict, guilt_half_life: int, n_days: int = 4) -> list[float]:
    """The persistence signal: guilt read each morning ON WAKING (day 1 = evening, after the wrong) -- does a
    single serious wrong still sit on him the next morning, and the one after?"""
    _, tr = single_wrong_arc(traits, {"guilt": guilt_half_life}, n_days)
    out = [
        round(tr.ticks[WAKING - 30].state_after_post.global_state["guilt"], 3)
    ]  # day 1 evening
    out += [
        round(tr.ticks[d * DAY_TICKS + 5].state_after_post.global_state["guilt"], 3)
        for d in range(1, n_days)
    ]
    return out


def _burden(g: dict) -> str:
    """OBSERVABLE read of how heavily the (unconfessed) wrong still sits on him -- keyed on GUILT, the
    half-life-calibrated moral memory (NOT rumination, which accumulates and would mask the decay, and NOT
    the incidental boredom/mood of a long idle day). A bystander's words."""
    weight = g.get("guilt", 0.0)
    if weight > 0.40:
        return "it still weighs heavily on him, plain in how he holds himself"
    if weight > 0.20:
        return "it still sits with him -- a shadow that hasn't lifted"
    if weight > 0.08:
        return "only a faint trace of it seems left on him"
    return "he carries himself as a man with nothing on his conscience"


def render_multiday(traits: dict, guilt_half_life: int, n_days: int = 4) -> str:
    """A plain-language, OBSERVABLE multi-day vignette of a man who did ONE serious wrong and confessed it to
    no one -- the evening he did it, then each following morning ON WAKING -- for the blind believability
    judge. Surfaces only the lingering moral burden (the half-life signal)."""
    _, tr = single_wrong_arc(traits, {"guilt": guilt_half_life}, n_days)
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


def _wary(s: float) -> str:
    """OBSERVABLE read of how wary he still is of the man who watched him (the suspicion relation dim)."""
    if s > 0.40:
        return "he is plainly still wary of the man -- keeps his distance, watches him back"
    if s > 0.20:
        return "a residual wariness toward the man lingers in how he holds himself near him"
    if s > 0.08:
        return "only a faint guardedness toward him is left"
    return "he seems easy around the man again, his guard down"


def render_suspicion_multiday(suspicion_half_life: int, n_days: int = 4) -> str:
    """Multi-day SUSPICION persistence: a man WATCHED with suspicion on day 1 (he did nothing), then the days
    pass -- how long does he stay wary of that man? Reads the suspicion relation dim each morning."""
    from eval.observe import relation_trajectory

    ev = [
        RawEvent(type="suspicion_raised", t=t, source="watcher", intensity=1.0)
        for t in range(8, 12)
    ]
    for d in range(n_days):
        ev.append(RawEvent(type="nightfall", t=d * DAY_TICKS + WAKING, intensity=1.0))
    cfg = _cfg({"conflict_avoidance": 0.5}, {"suspicion": suspicion_half_life})
    sc = Scenario(id="susp", persona="halgrim", initial_overrides={}, events=tuple(ev))
    _, tr = run_scenario(cfg, sc, n_ticks=n_days * DAY_TICKS)
    susp = relation_trajectory(tr, "watcher", "suspicion")
    lines = [
        "On the first day a man watched him with open suspicion, though he had done nothing. "
        "This is how warily he holds himself toward that man over the days that follow."
    ]
    for d in range(1, n_days):
        lines.append(f"- The morning of day {d + 1}: {_wary(susp[d * DAY_TICKS + 5])}.")
    return "\n".join(lines)


if __name__ == "__main__":
    traits = {"guilt_proneness": 0.9, "honesty_humility": 0.9}
    for hl, lbl in [(21600, "6h"), (64800, "18h"), (259200, "72h")]:
        print(f"{lbl:>4}: waking guilt by day = {waking_guilt(traits, hl)}")
