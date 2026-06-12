"""affinity_filter (M4b).

In: EffectiveInputVector (post relation_filter) + AffinityMap + context. Out: target-tagged
channels adjusted for object valence. Touches ONLY channels carrying a ``target``
(affinity class). In MVP the valence already rides in ``preference_match = affinity[item]``
(set by the mapper), so this stage is a neutral identity by default (phobias = stage 2,
spec section 13). The hook stays so the stage is part of the uniform pipeline, not a
special-cased ``if``. Updates NO state.
"""

from __future__ import annotations

from engine import filters
from engine.clamp import clamp_signed
from engine.schema import (
    AffinityMap,
    EffectiveInputVector,
    PersonaConfig,
    SemanticInput,
)


def apply(
    inputs: EffectiveInputVector,
    affinities: AffinityMap,
    config: PersonaConfig,
    context: dict,
) -> EffectiveInputVector:
    w = config.filter_weights.get("affinity", {})
    valence_gain = w.get("valence_gain", 0.0)  # 0 => identity

    out: EffectiveInputVector = {}
    for name, si in inputs.items():
        if si.target is None or valence_gain == 0.0:
            out[name] = si  # identity: not an affinity channel, or neutral default
            continue
        valence = filters.lookup(
            si.target, affinities, field=config.affinity_field
        )  # seam: exact entry wins; unknown entities blend through the FIELD (spec section 5)
        adjusted = clamp_signed(si.value * filters.factor(valence, valence_gain))
        out[name] = SemanticInput(
            name=si.name,
            value=adjusted,
            cls=si.cls,
            source=si.source,
            target=si.target,
            polarity=si.polarity,
        )
    return out
