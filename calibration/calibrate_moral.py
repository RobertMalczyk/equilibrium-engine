"""calibrate_moral.py -- M-J.4.4 calibration, the DETERMINISTIC pre-filter (no LLM).

Grids over the dominant moral-overlay magnitudes and, for each grid point, runs the engine on the moral
litmus scenarios and scores it WITHOUT any judge:

  HARD GATES (a grid point is discarded unless ALL hold):
    - Jury margin > 0 (the anger<->stress 2-cycle stays stable with the moral edges)
    - every moral state stays bounded in [0,1] and never pins at the ceiling
    - the litmus ORDERINGS hold (guilt-prone confesses earlier; empathic apologizes vs detached confesses;
      habitual liar lies; sensitive blames vs avoidant avoids; discreet confides vs gossip-prone doesn't)

  DETERMINISTIC SUB-SCORE (the parts of the spec section 10 objective computable without a judge, ~0.75):
    action_order (litmus margins) + persona_diff (visible divergence) + relationship_sensitivity
    (trust/resentment/suspicion movement) + no_degenerate_loops (Jury margin, anti-pin). curve_plausibility
    (0.25) is the JUDGE's job -- this pre-filter only narrows the grid so judge tokens are spent on survivors.

Run:  python -m calibration.calibrate_moral
Out:  calibration/moral_calibration_report.md  +  calibration/moral_calibration_survivors.json
"""

from __future__ import annotations

import copy
import itertools
import json
from pathlib import Path

import yaml

from engine.simulation import run_scenario
from engine.stability import jury_margin
from engine.yaml_io import _deep_merge, load_persona, load_scenario
from eval.observe import (
    action_counts,
    first_tick_with_action,
    relation_trajectory,
    trajectory,
)

ROOT = Path(__file__).resolve().parents[1]
DEFAULTS = ROOT / "calibration" / "defaults.yaml"
OVERLAY = ROOT / "calibration" / "moral_overlay.yaml"
HALGRIM = ROOT / "data" / "personas" / "halgrim.yaml"
SC = {
    "probe": ROOT / "data" / "scenarios" / "moral_probe.yaml",
    "confide": ROOT / "data" / "scenarios" / "moral_confide.yaml",
    "accusation": ROOT / "data" / "scenarios" / "moral_accusation.yaml",
}

# --- the grid: dominant magnitudes, a few values each (kept bounded; deterministic eval is cheap) --------
GRID = {
    "gains.guilt.wrongdoing": [0.20, 0.30, 0.40],
    "gains.exposure_anxiety.probe": [0.03, 0.05, 0.08],
    "couplings.stress.guilt": [0.02, 0.03, 0.05],
    "half_lives.guilt": [
        43200,
        64800,
        86400,
    ],  # 12h / 18h / 24h (all >> anger 30s -> dt unchanged)
}

# trait presets for the litmus contrasts (mirror the slice tests)
GUILT_PRONE = {"guilt_proneness": 0.8, "honesty_humility": 0.9}
LOW_GUILT = {"guilt_proneness": 0.1, "honesty_humility": 0.9}
EMPATHIC = {"guilt_proneness": 0.8, "honesty_humility": 0.9, "empathy": 0.9}
DETACHED = {"guilt_proneness": 0.8, "honesty_humility": 0.9, "empathy": 0.05}
LIAR = {"guilt_proneness": 0.2, "honesty_humility": 0.1}
DISCREET = {"guilt_proneness": 0.8, "honesty_humility": 0.9, "gossip_tendency": 0.0}
GOSSIP = {"guilt_proneness": 0.8, "honesty_humility": 0.9, "gossip_tendency": 0.9}
SENSITIVE = {
    "injustice_sensitivity": 0.9,
    "conflict_avoidance": 0.1,
    "guilt_proneness": 0.5,
}
AVOIDANT = {
    "injustice_sensitivity": 0.1,
    "conflict_avoidance": 0.9,
    "guilt_proneness": 0.5,
    "honesty_humility": 0.9,
}


def _base_overlay() -> dict:
    return yaml.safe_load(OVERLAY.read_text(encoding="utf-8")) or {}


def _point_overlay(point: dict, traits: dict) -> dict:
    """Base overlay deep-merged with this grid point's param overrides + the contrast traits."""
    ov = copy.deepcopy(_base_overlay())
    for dotted, val in point.items():
        node = ov
        *parents, leaf = dotted.split(".")
        for p in parents:
            node = node.setdefault(p, {})
        node[leaf] = val
    return _deep_merge(ov, {"traits": {k: float(v) for k, v in traits.items()}})


def _run(point: dict, traits: dict, scenario: str, n: int = 16):
    cfg = load_persona(HALGRIM, DEFAULTS, param_overrides=_point_overlay(point, traits))
    return cfg, run_scenario(cfg, load_scenario(SC[scenario]), n_ticks=n)[1]


def evaluate(point: dict) -> dict:
    """Hard gates + deterministic sub-score for one grid point. Returns a dict with pass/fail + score."""
    reasons: list[str] = []

    # M-J.0 confession-timing litmus
    cfg_gp, tr_gp = _run(point, GUILT_PRONE, "probe")
    _, tr_lg = _run(point, LOW_GUILT, "probe")
    t_gp = first_tick_with_action(tr_gp, "confess")
    t_lg = first_tick_with_action(tr_lg, "confess")
    guilt_prone_confesses = t_gp is not None
    low_guilt_silent_or_later = t_lg is None or (t_gp is not None and t_gp < t_lg)
    if not (guilt_prone_confesses and low_guilt_silent_or_later):
        reasons.append("M-J.0 confession ordering")

    # M-J.2 empathic-apologize vs detached-confess
    emp = action_counts(_run(point, EMPATHIC, "confide")[1])
    det = action_counts(_run(point, DETACHED, "confide")[1])
    if not ("apologize" in emp and "apologize" not in det):
        reasons.append("M-J.2 empathic apologizes")

    # M-J.1 habitual liar lies
    liar = action_counts(_run(point, LIAR, "probe")[1])
    if "lie" not in liar:
        reasons.append("M-J.1 liar lies")

    # M-J.2 discreet confides vs gossip-prone doesn't
    disc = action_counts(_run(point, DISCREET, "confide")[1])
    goss = action_counts(_run(point, GOSSIP, "confide")[1])
    if not ("confide" in disc and "confide" not in goss):
        reasons.append("M-J.2 discreet confides")

    # M-J.3 sensitive blames vs avoidant avoids
    sens = action_counts(_run(point, SENSITIVE, "accusation")[1])
    avoid = action_counts(_run(point, AVOIDANT, "accusation")[1])
    if not ("blame_other" in sens and "avoid" in avoid):
        reasons.append("M-J.3 blame vs avoid")

    # stability + boundedness (on the guilt-prone probe run)
    jm = jury_margin(cfg_gp.decay, cfg_gp.couplings)
    if jm <= 0:
        reasons.append("Jury margin <= 0")
    peak = 0.0
    for s in (
        "guilt",
        "exposure_anxiety",
        "rumination",
        "perceived_injustice",
        "cognitive_load_from_lies",
    ):
        vals = trajectory(tr_gp, s) + trajectory(tr_lg, s)
        if vals:
            peak = max(peak, max(vals))
            if any(v < 0.0 or v > 1.0 for v in vals):
                reasons.append(f"{s} out of [0,1]")
    if peak >= 0.999:
        reasons.append("a moral state pins at the ceiling")

    passed = not reasons

    # deterministic sub-score (only meaningful for survivors; higher = better)
    persona_diff = 0.0
    if t_gp is not None:
        persona_diff = (
            (t_lg - t_gp) if t_lg is not None else 6.0
        )  # earlier-and-clearer separation is better
    # relationship sensitivity: how much suspicion/resentment the accusation run moves
    susp = relation_trajectory(
        _run(point, SENSITIVE, "accusation")[1], "accuser", "suspicion"
    )
    rel_sens = susp[-1] if susp else 0.0
    anti_pin = 1.0 - peak  # reward headroom below the ceiling
    score = round(
        0.45 * min(persona_diff / 6.0, 1.0)
        + 0.20 * min(jm / 0.5, 1.0)
        + 0.20 * min(rel_sens / 0.5, 1.0)
        + 0.15 * max(anti_pin, 0.0),
        4,
    )
    return {
        "point": point,
        "passed": passed,
        "reasons": reasons,
        "jury_margin": round(jm, 5),
        "peak_state": round(peak, 4),
        "persona_diff_ticks": persona_diff,
        "rel_sensitivity": round(rel_sens, 4),
        "det_score": score,
    }


def main() -> None:
    keys = list(GRID)
    combos = [
        dict(zip(keys, vals)) for vals in itertools.product(*(GRID[k] for k in keys))
    ]
    results = [evaluate(p) for p in combos]
    survivors = sorted(
        (r for r in results if r["passed"]), key=lambda r: r["det_score"], reverse=True
    )

    out_json = ROOT / "calibration" / "moral_calibration_survivors.json"
    out_json.write_text(json.dumps(survivors, indent=2), encoding="utf-8")

    lines = [
        "# M-J.4.4 calibration -- deterministic pre-filter",
        "",
        f"Grid: {len(combos)} points over {', '.join(keys)}.",
        f"Survivors (passed ALL hard gates): **{len(survivors)} / {len(combos)}**.",
        "",
        "Hard gates: Jury margin > 0; moral states bounded + no ceiling pin; the five litmus orderings hold.",
        "Deterministic sub-score (~0.75 of the spec section 10 objective; curve_plausibility is the judge's job):",
        "`0.45*persona_diff + 0.20*jury + 0.20*rel_sensitivity + 0.15*anti_pin`.",
        "",
        "## Top survivors",
        "",
        "| rank | det_score | persona_diff | jury | rel_sens | peak | point |",
        "|---|---|---|---|---|---|---|",
    ]
    for i, r in enumerate(survivors[:15], 1):
        pt = ", ".join(f"{k.split('.')[-1]}={v}" for k, v in r["point"].items())
        lines.append(
            f"| {i} | {r['det_score']} | {r['persona_diff_ticks']} | {r['jury_margin']} | "
            f"{r['rel_sensitivity']} | {r['peak_state']} | {pt} |"
        )
    if not survivors:
        # show why points failed (the most common reasons) to guide the next grid
        from collections import Counter

        c = Counter(reason for r in results for reason in r["reasons"])
        lines += ["", "## No survivors -- most common failure reasons", ""]
        lines += [f"- {reason}: {n}" for reason, n in c.most_common()]
    lines += [
        "",
        "## Next step (AWAIT APPROVAL -- budgeted)",
        "Take the top survivors to the LLM blind-judge sample (docs/moral_calibration_plan.md, step 2),",
        "then the full judged 700+700 corpus (step 3). The judge scores curve_plausibility + confirms the",
        "deterministic orderings.",
    ]
    (ROOT / "calibration" / "moral_calibration_report.md").write_text(
        "\n".join(lines), encoding="utf-8"
    )
    print(
        f"{len(survivors)}/{len(combos)} survivors -> calibration/moral_calibration_report.md"
    )


if __name__ == "__main__":
    main()
