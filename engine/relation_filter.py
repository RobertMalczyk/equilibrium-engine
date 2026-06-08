"""relation_filter (M4a).

In: SemanticInputVector + Relations(snapshot) + derived_pre + context. Out: channels with
the same tags, source-tagged channels scaled by ``affective_bias[source]`` and (when
public) by ``social_exposure``. Touches ONLY channels carrying a ``source`` (relational
class); everything else passes through unchanged (identity stage of the uniform filter
pipeline, spec section 14). Updates NO state. The betrayal exception keys on ``trust``
(spec section 5): betrayal lands harder when trust is high, instead of being damped by
positive bias.

Channel values are NOT clamped here -- they are inputs, not states; gains scale them and
the state commit (M9) does the clamping. So an amplified insult can exceed 1.0 as an input.

Sign convention: ``amp = (1 + bias_gain*polarity_sign*affective_bias[source]) * social``.
  * disliked source (bias<0) amplifies negative channels, damps positive ones;
  * liked source (bias>0) does the reverse;
  * ``social`` = 1 + social_exposure_gain when context is public (spec section 5).
"""

from __future__ import annotations

from engine import filters
from engine.schema import (
    DerivedSnapshot,
    EffectiveInputVector,
    PersonaConfig,
    Polarity,
    Relations,
    SemanticInput,
    SemanticInputVector,
)

# Channels that route onto trust and must NOT be damped by positive bias (betrayal hurts
# more with trust). Frozen vocabulary, not a tunable; the gain is still from config.
BETRAYAL_CHANNELS = frozenset({"promise_broken"})


def _polarity_sign(p: Polarity) -> float:
    if p == Polarity.POSITIVE:
        return 1.0
    if p == Polarity.NEGATIVE:
        return -1.0
    return 0.0


def apply(
    inputs: SemanticInputVector,
    relations: Relations,
    derived_pre: DerivedSnapshot,
    config: PersonaConfig,
    context: dict,
) -> EffectiveInputVector:
    w = config.filter_weights.get("relation", {})
    bias_gain = w.get("bias_gain", 0.0)
    social_exposure_gain = w.get("social_exposure_gain", 0.0)
    social = 1.0 + social_exposure_gain if context.get("public") else 1.0

    out: EffectiveInputVector = {}
    for name, si in inputs.items():
        if si.source is None:
            out[name] = si  # identity: not a relational channel
            continue

        if name in BETRAYAL_CHANNELS:
            # nested relation dim, not the flat lookup seam (the one structural exception; see
            # docs/diagrams/filters.md) -- fetch the scalar inline, share only the factor formula.
            trust = relations.get(si.source, {}).get("trust", 0.0)
            amp = filters.factor(trust, bias_gain)
        else:
            bias = filters.lookup(
                si.source, derived_pre.affective_bias
            )  # seam (FIELD later)
            amp = filters.factor(bias, bias_gain, sign=_polarity_sign(si.polarity))

        amp = max(0.0, amp) * social
        out[name] = SemanticInput(
            name=si.name,
            value=si.value * amp,
            cls=si.cls,
            source=si.source,
            target=si.target,
            polarity=si.polarity,
        )
    return out
