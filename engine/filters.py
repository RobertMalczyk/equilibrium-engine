"""filters — the shared per-entity modulation kernel (spec section 5/14).

The input-channel filter stages (`relation_filter` M4a, `affinity_filter` M4b) both compute the SAME
shape: *scale a signal by a per-entity value, identity unless populated*. That shape lives here, once,
as two pure functions:

  * ``lookup(entity, table)`` — entity -> scalar, ``neutral`` (0.0) when the entity is ``None`` or absent.
    This is the **seam**: today a flat-dict ``.get``; the deferred category->specific (IS-A) hierarchy or
    the cosine affinity FIELD over an embedding space (spec section 13; ``Ideas/affinity_field_unification.md``)
    replaces these internals WITHOUT moving a call site. An empty table -> neutral everywhere -> identity.
  * ``factor(value, gain, sign)`` — the modulation ``1 + gain*sign*value``. ``gain == 0`` (the neutral
    config default) or ``value == 0`` -> ``1.0`` (identity). ``sign`` is the CALLER's per-channel polarity
    (relational channels flip it by ``polarity_sign``); it is not a per-entity property.

Updates NO state, holds NO numeric literal beyond the structural identity constants (``1.0`` factor base,
``0.0`` neutral) — every gain and table value comes from config / the caller. Owns the per-entity gain
ONLY, never the appraisal gates (``command/kindness/bystander_pressure``). Diagram:
``docs/diagrams/filters.md``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Mapping

from engine import affinity_field as _field

if TYPE_CHECKING:  # pragma: no cover
    from engine.affinity_field import AffinityField


def lookup(
    entity: str | None,
    table: Mapping[str, float],
    neutral: float = 0.0,
    field: "AffinityField | None" = None,
) -> float:
    """Resolve an entity to its per-entity scalar; ``neutral`` when unknown.

    The single seam for entity generalization. Resolution order (spec section 5):

    1. **Exact-entry override** — an explicitly-authored entity returns its table value outright
       ("k=1 / most-specific wins": a specific authored judgment beats the generalized landscape).
       This is also what makes the field migration byte-exact: authored entries never ride the blend.
    2. **Affinity FIELD** (when configured) — an UNKNOWN entity with a coordinate gets a
       cosine-blended valence from the sparse anchors (``engine.affinity_field``).
    3. ``neutral`` — no entity / not authored / no field / no coordinate.

    ``field=None`` (the default) is bit-identical to the historical flat lookup.
    """
    if entity is None:
        return neutral
    if entity in table:
        return table[entity]
    if field is not None:
        return _field.resolve(entity, field, neutral)
    return neutral


def factor(value: float, gain: float, sign: float = 1.0) -> float:
    """The per-entity modulation factor ``1 + gain*sign*value``; identity (``1.0``) by default.

    Identity when ``gain == 0`` (neutral config default) or ``value == 0`` (unknown/neutral entity).
    """
    return 1.0 + gain * sign * value
