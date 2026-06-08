"""DebugTrace contract (Mpom) + clamp re-export.

CONTRACT -- single source of truth for the trace format. The serialized field set and
order below are FROZEN; changing them invalidates every golden trace and is a conscious
RITUAL: bump ``TRACE_VERSION`` and re-baseline goldens with GOLDEN_REGEN=1 in the same
change. Never edit the field roster ad hoc.

TRACE_VERSION = 1.

Per-tick field roster (FROZEN order; exactly the intermediate results of spec section 7):
    t, event, snapshot, derived_pre, eff_inputs, delta, state_after_commit, derived_post,
    potentials, urges, selection, state_after_post.
Whole-scenario wrapper: trace_version, persona, scenario, dt, ticks[].

Serialization rules (determinism, bit-for-bit):
  * Field order is the insertion order of ``to_dict`` below -- NOT alphabetical.
  * Nested maps over states/relations/potentials are emitted in canonical order
    (GLOBAL_STATES, RELATION_DIMS, POTENTIAL_NAMES) so dict ordering never leaks in.
  * EVERY float is rounded via ``round(x, FLOAT_NDIGITS)`` at emit time -- not only when
    comparing. ``to_dict`` is the one rounding gate and ``to_json``/``to_markdown`` both go
    through it, so every emitted form (JSON, Markdown) is uniformly rounded. The engine
    itself never rounds; rounding is a serialization concern only.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Optional

from engine.schema import (
    GLOBAL_STATES,
    POTENTIAL_NAMES,
    RELATION_DIMS,
    ActionSelection,
    DerivedSnapshot,
    EffectiveInputVector,
    RawEvent,
    Snapshot,
    StateDelta,
)

# Number of decimal digits kept in serialized traces. This is a *serialization*
# precision knob, not an engine equation parameter; the engine itself never rounds.
FLOAT_NDIGITS = 9

# Trace format version: bump only with a conscious golden-trace re-baseline.
TRACE_VERSION = 1


def _round(x: float) -> float:
    return round(float(x), FLOAT_NDIGITS)


def _global_map(m: dict[str, float]) -> dict[str, float]:
    return {k: _round(m[k]) for k in GLOBAL_STATES if k in m}


def _relations_map(rel: dict[str, dict[str, float]]) -> dict[str, dict[str, float]]:
    out: dict[str, dict[str, float]] = {}
    for src in sorted(rel):
        out[src] = {d: _round(rel[src][d]) for d in RELATION_DIMS if d in rel[src]}
    return out


def _potentials_map(p: dict[str, float]) -> dict[str, float]:
    return {k: _round(p[k]) for k in POTENTIAL_NAMES if k in p}


def _event_dict(ev: Optional[RawEvent]) -> Optional[dict]:
    if ev is None:
        return None
    return {
        "type": ev.type,
        "t": ev.t,
        "source": ev.source,
        "target": ev.target,
        "item": ev.item,
        "topic": ev.topic,
        "faction": ev.faction,
        "intensity": _round(ev.intensity),
        "context": dict(sorted(ev.context.items())),
    }


def _inputs_dict(eff: EffectiveInputVector) -> dict[str, dict]:
    out: dict[str, dict] = {}
    for name in sorted(eff):
        si = eff[name]
        out[name] = {
            "value": _round(si.value),
            "cls": si.cls.value,
            "source": si.source,
            "target": si.target,
            "polarity": si.polarity.value,
        }
    return out


def _derived_dict(d: DerivedSnapshot) -> dict:
    return {
        "affective_bias": {k: _round(v) for k, v in sorted(d.affective_bias.items())},
        "negative_bias": {k: _round(v) for k, v in sorted(d.negative_bias.items())},
        "irritability": _round(d.irritability),
        "effective_self_control": _round(d.effective_self_control),
        "dissatisfaction": _round(d.dissatisfaction),
        "urge_boredom": _round(d.urge_boredom),
        "urge_fatigue": _round(d.urge_fatigue),
    }


def _delta_dict(delta: StateDelta) -> dict:
    return {
        "global": {k: _round(v) for k, v in sorted(delta.global_.items())},
        "relations": {
            src: {d: _round(v) for d, v in sorted(dims.items())}
            for src, dims in sorted(delta.relations.items())
        },
    }


def _selection_dict(sel: ActionSelection) -> dict:
    return {
        "action": sel.action,
        "score": _round(sel.score),
        "kind": sel.kind.value,
        "interrupted": sel.interrupted,
        "post_effects": _delta_dict(sel.post_effects),
        "explanation": sel.explanation,
    }


@dataclass
class TickTrace:
    """All intermediate results of one tick (spec section 7). FROZEN field order."""

    t: int
    event: Optional[RawEvent]
    snapshot: Snapshot
    derived_pre: DerivedSnapshot
    eff_inputs: EffectiveInputVector
    delta: StateDelta
    state_after_commit: Snapshot
    derived_post: DerivedSnapshot
    potentials: dict[str, float]
    urges: dict[str, float]
    selection: ActionSelection
    state_after_post: Snapshot

    def to_dict(self) -> dict:
        return {
            "t": self.t,
            "event": _event_dict(self.event),
            "snapshot": {
                "global": _global_map(self.snapshot.global_state),
                "relations": _relations_map(self.snapshot.relations),
                "mode": self.snapshot.mode.value,
            },
            "derived_pre": _derived_dict(self.derived_pre),
            "eff_inputs": _inputs_dict(self.eff_inputs),
            "delta": _delta_dict(self.delta),
            "state_after_commit": {
                "global": _global_map(self.state_after_commit.global_state),
                "relations": _relations_map(self.state_after_commit.relations),
            },
            "derived_post": _derived_dict(self.derived_post),
            "potentials": _potentials_map(self.potentials),
            "urges": {k: _round(v) for k, v in sorted(self.urges.items())},
            "selection": _selection_dict(self.selection),
            "state_after_post": {
                "global": _global_map(self.state_after_post.global_state),
                "relations": _relations_map(self.state_after_post.relations),
                "mode": self.state_after_post.mode.value,
            },
        }


@dataclass
class DebugTrace:
    """A whole-scenario trace: ordered ticks. Golden trace = ``to_json`` of this."""

    persona: str
    scenario: str
    dt: float
    ticks: list[TickTrace] = field(default_factory=list)

    def emit(self, tick: TickTrace) -> None:
        self.ticks.append(tick)

    def to_dict(self) -> dict:
        return {
            "trace_version": TRACE_VERSION,
            "persona": self.persona,
            "scenario": self.scenario,
            "dt": _round(self.dt),
            "ticks": [t.to_dict() for t in self.ticks],
        }

    def to_json(self) -> str:
        # sort_keys=False: we rely on our explicit, frozen field order above.
        return json.dumps(self.to_dict(), indent=2, ensure_ascii=False, sort_keys=False)

    def to_markdown(self) -> str:
        lines = [
            f"# DebugTrace {self.persona} / {self.scenario} (dt={_round(self.dt)})",
            "",
        ]
        for tk in self.ticks:
            d = tk.to_dict()
            sel = d["selection"]
            lines.append(f"## tick t={d['t']}  ->  {sel['action']} ({sel['kind']})")
            lines.append("```json")
            lines.append(json.dumps(d, indent=2, ensure_ascii=False))
            lines.append("```")
            lines.append("")
        return "\n".join(lines)
