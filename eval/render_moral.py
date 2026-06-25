"""eval/render_moral.py -- render a moral litmus run as a PLAIN-LANGUAGE, OBSERVABLE vignette for the blind
believability judge (M-J.4.4 calibration). Like render_narration, it emits ONLY what a bystander could see
-- demeanor + actions -- never engine vocabulary or numbers. The judge rates a CHARACTER, not an engine.
"""

from __future__ import annotations

from pathlib import Path

from engine.simulation import run_scenario
from engine.yaml_io import load_persona, load_scenario
from eval.moral import moral_overrides

ROOT = Path(__file__).resolve().parents[1]
DEFAULTS = ROOT / "calibration" / "defaults.yaml"
HALGRIM = ROOT / "data" / "personas" / "halgrim.yaml"

# Observable phrasing for the moral resolution actions (a bystander's words, no engine terms).
ACT = {
    "confess": "he owns up to it -- admits plainly what he did",
    "remain_silent": "he holds his tongue, gives nothing away",
    "lie": "he denies it flatly, looks you in the eye and lies",
    "deflect": "he dodges -- turns the question aside, won't answer straight",
    "apologize": "he owns up to it and makes his apologies, tries to set it right",
    "blame_other": "he turns it back on his accuser, points the finger elsewhere",
    "avoid": "he withdraws -- avoids the man, won't be drawn in",
    "confide": "he unburdens himself to his friend, tells them the whole of it",
    # base reactions (so betrayal/accusation runs render their visible reply too)
    "outburst": "he flares up and snaps, temper boiling over",
    "cold_response": "he answers curtly and coldly, shutting down",
    "complain": "he grumbles and protests",
    "refuse": "he flatly refuses",
}

# Scenario frames (the observable situation a bystander would already know).
FRAME = {
    "moral_probe": "He had done something he was not proud of. Now he is being questioned about it.",
    "moral_confide": "He has been carrying a wrong he did. A trusted friend is here with him now.",
    "moral_accusation": "He is being accused -- pressed, in front of others, over something.",
    "moral_suspicion": "Someone has taken to watching him, suspicious, though he has done nothing.",
    "moral_betrayal": "He has just learned that a man he trusted lied to him.",
    "moral_secret": "He is carrying a secret he must keep -- something the guards must not learn.",
}


def _demeanor(g: dict) -> str:
    """A coarse bystander read of how he is carrying himself, from visible signs only."""
    burden = g.get("guilt", 0.0) + 0.5 * g.get("rumination", 0.0) + 0.4 * g.get("stress", 0.0)
    unease = g.get("exposure_anxiety", 0.0) + 0.7 * g.get("avoidance_drive", 0.0)
    grievance = g.get("perceived_injustice", 0.0)
    anger = g.get("anger", 0.0)
    if anger > 0.40:
        return "his temper is plainly up, the warmth gone out of him"
    if grievance > 0.35:
        return "he bristles -- this strikes him as unfair, and it shows"
    if unease > 0.35:
        return "he grows visibly uneasy, shifts, won't quite meet your eye"
    if burden > 0.35:
        return "he carries himself like a man with something weighing on him"
    if burden > 0.12 or unease > 0.12:
        return "a flicker of something troubled crosses him"
    return "he seems composed enough"


def vignette(traits: dict, scenario: str, n: int = 16) -> str:
    cfg = load_persona(HALGRIM, DEFAULTS, param_overrides=moral_overrides(traits))
    _, tr = run_scenario(
        cfg, load_scenario(ROOT / "data" / "scenarios" / f"{scenario}.yaml"), n_ticks=n
    )
    lines = [FRAME.get(scenario, "")]
    for tk in tr.ticks:
        act = tk.selection.action
        g = tk.state_after_post.global_state
        if act in ACT:
            line = f"- Then, {ACT[act]}."
        else:
            d = _demeanor(g)
            line = f"- {d[0].upper() + d[1:]}."
        if (
            line != lines[-1]
        ):  # collapse consecutive identical lines (a bystander doesn't repeat himself)
            lines.append(line)
    return "\n".join(line for line in lines if line)
