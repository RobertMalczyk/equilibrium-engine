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


def _zero_numeric_leaves(node):
    """Recursively set every numeric leaf to 0.0 (in place), leaving structure/strings intact."""
    if isinstance(node, dict):
        for k, v in node.items():
            if isinstance(v, (int, float)) and not isinstance(v, bool):
                node[k] = 0.0
            else:
                _zero_numeric_leaves(v)
    elif isinstance(node, list):
        for v in node:
            _zero_numeric_leaves(v)
    return node


def zero_gain_overrides(traits: dict[str, float] | None = None) -> dict:
    """Gate B (impl spec section 9.1): the moral overlay ENABLED (states/dims/actions present, half_lives
    supplied) but with every moral GAIN zeroed -- so the moral states never rise, no moral action is ever
    selected, and the ledger stays empty. Behavior on a non-moral scenario must then be EQUIVALENT to the
    legacy persona (the moral topology is inert at zero gain). Couplings/weights are left intact: they read
    states that stay 0, so they contribute nothing -- exactly the equivalence the gate asserts."""
    overlay = moral_overrides(traits)
    if "gains" in overlay:
        _zero_numeric_leaves(overlay["gains"])
    overlay.pop(
        "gain_modulators", None
    )  # modulators scale gains that are now 0 -> irrelevant
    return overlay
