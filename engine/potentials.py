"""potentials.compute (M7).

In: state' + relations' + traits + derived_post. Out: reactive PotentialVector, clamp[0,1]
(shared scale with thresholds). Knows NO thresholds and selects nothing.

The engine computes only ``potential = clamp( Sum weight[term] * value[term] )``. Each
*term* is a DECLARATIVE product of factors from ``config.potential_terms`` (like the
coupling topology: an explicit list, not a formula baked in code). A factor is a
state/derived/relation_agg/trait, optionally complemented ((1 - x)). Invariant (validated
at load, spec section 8): every term carries at least one state/derived/relation_agg factor,
so a trait alone (e.g. high stoicism) can never fire a reaction at zero emotion -- traits
only MODULATE. The suppression split emerges from which term each action weights:
``anger*stoicism`` -> cold_response, ``anger*(1-effective_self_control)`` -> outburst.
``cooperate`` has no active term in MVP (no command channel -> command_pressure absent).
"""

from __future__ import annotations

from engine.clamp import clamp01
from engine.schema import (
    MORAL_POTENTIALS,
    POTENTIAL_NAMES,
    DerivedSnapshot,
    GlobalStateMap,
    PersonaConfig,
    PotentialVector,
    Relations,
)


def _relation_aggregates(relations: Relations) -> dict[str, float]:
    if not relations:
        return {"trust_max": 0.0, "respect_max": 0.0, "resentment_max": 0.0}
    srcs = sorted(relations)
    return {
        "trust_max": max(relations[s].get("trust", 0.0) for s in srcs),
        "respect_max": max(relations[s].get("respect", 0.0) for s in srcs),
        "resentment_max": max(relations[s].get("resentment", 0.0) for s in srcs),
    }


def _factor_value(
    factor: dict,
    global_state: GlobalStateMap,
    derived_post: DerivedSnapshot,
    config: PersonaConfig,
    rel_aggs: dict[str, float],
    command_pressure: float,
    kindness_pressure: float,
    bystander_pressure: float,
    refractory_pressure: float,
    event_source: str | None,
    relations: Relations,
) -> float:
    kind = factor["kind"]
    name = factor.get("name")
    if kind == "state":
        v = global_state[name]
    elif kind == "derived":
        v = getattr(derived_post, name)
    elif kind == "trait":
        v = config.traits[name]
    elif kind == "relation_agg":
        v = rel_aggs[name]
    elif kind == "command_pressure":
        v = command_pressure  # transient gating factor (0 if no order)
    elif kind == "kindness_pressure":
        v = kindness_pressure  # transient gating factor (0 if no appraised kindness)
    elif kind == "bystander_pressure":
        v = bystander_pressure  # transient gating factor (0 if the source isn't a bystander)
    elif kind == "refractory_pressure":
        v = refractory_pressure  # transient gating factor (0 unless latched + same-source re-provocation)
    else:  # relation_source (validated at load): relation to the CURRENT event's source, per-dim
        v = (
            relations.get(event_source, {}).get(name, 0.0)
            if event_source is not None
            else 0.0
        )
    return (1.0 - v) if factor.get("complement", False) else v


def compute(
    global_state: GlobalStateMap,
    relations: Relations,
    config: PersonaConfig,
    derived_post: DerivedSnapshot,
    command_pressure: float = 0.0,
    event_source: str | None = None,
    kindness_pressure: float = 0.0,
    bystander_pressure: float = 0.0,
    refractory_pressure: float = 0.0,
) -> PotentialVector:
    """command_pressure (transient, this tick's command channel; 0 if no order), kindness_pressure
    (transient, this tick's appraised kindness; 0 if none) and event_source (the current event's source,
    for the per-source `relation_source` factor) are passed by the caller -- potentials stays a pure
    function of its arguments. command_pressure gates the obedience potentials (cooperate/refuse) and
    kindness_pressure gates positive_response AND inhibits the hostile potentials (signed edge); no
    order/gesture -> pressure 0 -> those terms 0 -> dormant (spec section 8)."""
    rel_aggs = _relation_aggregates(relations)

    # Evaluate each declared term once (product of its factors).
    term_values: dict[str, float] = {}
    for term_name, factors in config.potential_terms.items():
        product = 1.0
        for f in factors:
            product *= _factor_value(
                f,
                global_state,
                derived_post,
                config,
                rel_aggs,
                command_pressure,
                kindness_pressure,
                bystander_pressure,
                refractory_pressure,
                event_source,
                relations,
            )
        term_values[term_name] = product

    out: PotentialVector = {}
    for action in POTENTIAL_NAMES:
        weights = config.potential_weights.get(action, {})
        # OPT-IN moral actions are emitted ONLY when the persona configures weights for them (the moral
        # overlay). Absent -> not in the output -> `_potentials_map` omits them -> goldens byte-identical.
        # (The original actions are always emitted, even at 0.0, exactly as before.)
        if action in MORAL_POTENTIALS and not weights:
            continue
        acc = 0.0
        for term in sorted(weights):  # sorted keys: order-invariant sum
            acc += weights[term] * term_values[term]
        out[action] = clamp01(acc)
    return out
