"""affinity_field — entity valence as a cosine-blended field over an embedding space (spec section 5).

Stage 1 of the field substrate (design of record: ``Ideas/affinity_field_unification.md``, private
overlay; diagram ``docs/diagrams/affinity_field.md``): entities are coordinates in a small vector
space (FROZEN config — any embedding generation happens offline at the perception seam and is cached
to config, never in the tick), a sparse set of authored anchors carries valences, and an UNKNOWN
entity's valence is a cosine-similarity-weighted blend of the anchors — kernel regression with a
neutral prior::

    w_a        = exp((cos(x_e, x_a) - 1) / tau)        # similarity kernel, tau = temperature
    valence(e) = sum(w_a * v_a) / (sum(w_a) + w_0)     # neutral prior: far from all anchors -> ~0

The EXACT-ENTRY OVERRIDE lives at the seam (``filters.lookup``): an explicitly-authored entity
returns its table value outright and never reaches this blend — the field generalizes to entities
nobody authored individually. Feed-forward only: no state, no loop. Pure arithmetic over frozen
config -> bit-for-bit deterministic. Debuggability: ``explain`` returns the per-anchor
contributions the blend is made of (the same math, exposed).

Coordinate hygiene (validated at build): coordinates are unit-normalized here (config may be
authored unnormalized; two entities on one ray ARE the same direction, by design); a zero vector is
a hard config error (cosine undefined). ``tau``/``w0``/gains come from config — no numeric literal
beyond structural identity constants.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from engine.clamp import clamp_signed

Vector = tuple[float, ...]


@dataclass(frozen=True)
class Anchor:
    name: str
    coord: Vector  # unit-normalized at build
    value: float  # authored valence [-1, 1]


@dataclass(frozen=True)
class AffinityField:
    """Frozen field config: entity coordinates + sparse anchors + kernel params."""

    coordinates: dict[str, Vector]  # entity -> unit coordinate
    anchors: tuple[Anchor, ...]
    tau: float  # kernel temperature (> 0)
    w0: float  # neutral-prior weight (>= 0)


def _normalize(name: str, raw, ctx: str) -> Vector:
    vec = tuple(float(x) for x in raw)
    norm = math.sqrt(sum(x * x for x in vec))
    if norm == 0.0:
        raise ValueError(
            f"{ctx}: coordinate '{name}' is a zero vector (cosine undefined)"
        )
    return tuple(x / norm for x in vec)


def build(raw: dict | None, ctx: str = "affinity_field") -> AffinityField | None:
    """Parse + validate the ``affinity_field:`` config block. ``None``/empty -> no field (identity)."""
    if not raw:
        return None
    coords_raw = dict(raw.get("coordinates", {}))
    anchors_raw = list(raw.get("anchors", []))
    if not coords_raw and not anchors_raw:
        return None

    tau = float(raw.get("tau", 0.0))
    if tau <= 0.0:
        raise ValueError(
            f"{ctx}: tau must be > 0 when the field is populated (got {tau})"
        )
    w0 = float(raw.get("w0", 0.0))
    if w0 < 0.0:
        raise ValueError(f"{ctx}: w0 must be >= 0 (got {w0})")

    coordinates = {str(k): _normalize(str(k), v, ctx) for k, v in coords_raw.items()}

    dims = {len(v) for v in coordinates.values()}
    anchors: list[Anchor] = []
    for i, a in enumerate(anchors_raw):
        a = dict(a)
        name = str(a.get("name", f"anchor_{i}"))
        if "coord" in a:
            coord = _normalize(name, a["coord"], ctx)
        elif name in coordinates:
            coord = coordinates[name]
        else:
            raise ValueError(
                f"{ctx}: anchor '{name}' has no coord and no matching coordinates entry"
            )
        dims.add(len(coord))
        anchors.append(
            Anchor(name=name, coord=coord, value=clamp_signed(float(a["value"])))
        )
    if len(dims) > 1:
        raise ValueError(f"{ctx}: mixed coordinate dimensionalities {sorted(dims)}")
    if not anchors:
        return None  # coordinates without anchors = nothing to blend = identity

    return AffinityField(
        coordinates=coordinates, anchors=tuple(anchors), tau=tau, w0=w0
    )


def explain(entity: str, field: AffinityField) -> list[tuple[str, float, float]]:
    """Per-anchor contributions for ``entity``: (anchor_name, kernel_weight, anchor_value).

    The blend in ``resolve`` is exactly ``sum(w*v) / (sum(w) + w0)`` over this list — the
    debuggability contract: every field judgment is explainable from its parts.
    """
    x = field.coordinates.get(entity)
    if x is None:
        return []
    out: list[tuple[str, float, float]] = []
    for a in field.anchors:
        cos = sum(p * q for p, q in zip(x, a.coord))
        w = math.exp((cos - 1.0) / field.tau)
        out.append((a.name, w, a.value))
    return out


def resolve(entity: str, field: AffinityField, neutral: float = 0.0) -> float:
    """Blend an UNKNOWN entity's valence from the anchors; ``neutral`` when it has no coordinate.

    Callers apply the exact-entry override BEFORE this (``filters.lookup``): an explicitly-authored
    entity never reaches the blend.
    """
    contributions = explain(entity, field)
    if not contributions:
        return neutral
    total_w = sum(w for _, w, _ in contributions)
    if total_w + field.w0 == 0.0:
        return neutral
    blended = sum(w * v for _, w, v in contributions) / (total_w + field.w0)
    return clamp_signed(blended)
