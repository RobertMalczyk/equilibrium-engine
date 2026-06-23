"""eval/moral.py -- the M-J.0 moral overlay loader (opt-in).

`moral_overrides()` reads calibration/moral_overlay.yaml and returns it as a param_overrides dict to be
deep-merged onto a persona (the burst-overlay pattern, eval/calibrated.py). Passing it to
`load_persona(..., param_overrides=moral_overrides(...))` ENABLES the guilt core for that load; omitting it
leaves the persona byte-identical to a legacy run. Optional per-call trait values (e.g. guilt_proneness)
are merged in so a contrast can vary one moral trait while sharing the same topology.

Deterministic, no LLM. Reads only static config.
"""

from __future__ import annotations

import copy
from pathlib import Path

import yaml

from engine.yaml_io import _deep_merge

ROOT = Path(__file__).resolve().parents[1]
MORAL_OVERLAY = ROOT / "calibration" / "moral_overlay.yaml"


def moral_overrides(traits: dict[str, float] | None = None) -> dict:
    """The moral overlay as a param_overrides dict. `traits` (e.g. {"guilt_proneness": 0.8}) is merged
    into the `traits` block so a litmus contrast can vary one moral knob over a shared topology."""
    overlay = yaml.safe_load(MORAL_OVERLAY.read_text(encoding="utf-8")) or {}
    overlay = copy.deepcopy(overlay)
    if traits:
        overlay = _deep_merge(
            overlay, {"traits": {k: float(v) for k, v in traits.items()}}
        )
    return overlay
