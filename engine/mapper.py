"""mapper.map (M3).

In: RawEvent + PersonaConfig + HistoryFeatures. Out: SemanticInputVector (tagged base
channels). Decomposes one event into many channels, tags source/target/class, sets
``preference_match = affinity[item]`` and repetition/novelty from history. "Semantic and
dumb": applies NO relational/affinity weighting (that is the filters' job, M4) and uses
no numeric literals -- channel values come from the event, history, and affinities.
"""

from __future__ import annotations

from engine.schema import (
    HistoryFeatures,
    InputClass,
    PersonaConfig,
    Polarity,
    RawEvent,
    SemanticInput,
    SemanticInputVector,
)


def _polarity(value: float) -> Polarity:
    if value > 0.0:
        return Polarity.POSITIVE
    if value < 0.0:
        return Polarity.NEGATIVE
    return Polarity.NEUTRAL


def map_event(
    event: RawEvent, config: PersonaConfig, feats: HistoryFeatures
) -> SemanticInputVector:
    out: SemanticInputVector = {}

    if event.type == "food_given":
        # Physiological (self, no filter): satiation reduces hunger.
        out["food_nutrition"] = SemanticInput(
            name="food_nutrition",
            value=event.intensity,
            cls=InputClass.SELF,
            polarity=Polarity.POSITIVE,
        )
        # Affinity (target = the food item): object valence -> satisfaction/frustration.
        pref = config.affinities.get(event.item, 0.0) if event.item is not None else 0.0
        out["preference_match"] = SemanticInput(
            name="preference_match",
            value=pref,
            cls=InputClass.AFFINITY,
            target=event.item,
            polarity=_polarity(pref),
        )
        # Repetition/novelty (self, from history): repetition bores, novelty relieves.
        out["repetition"] = SemanticInput(
            name="repetition",
            value=feats.repetition_score,
            cls=InputClass.SELF,
            polarity=Polarity.NEGATIVE,
        )
        out["novelty"] = SemanticInput(
            name="novelty",
            value=feats.novelty_score,
            cls=InputClass.SELF,
            polarity=Polarity.POSITIVE,
        )
        return out

    if event.type == "insult":
        # Relational (source = the insulter): one channel feeding anger/frustration
        # (global) + resentment (relational dim), routed by the relation_filter.
        out["insult"] = SemanticInput(
            name="insult",
            value=event.intensity,
            cls=InputClass.RELATIONAL,
            source=event.source,
            polarity=Polarity.NEGATIVE,
        )
        return out

    if event.type == "help":
        # Relational positive: builds trust, eases resentment.
        out["help"] = SemanticInput(
            name="help",
            value=event.intensity,
            cls=InputClass.RELATIONAL,
            source=event.source,
            polarity=Polarity.POSITIVE,
        )
        return out

    if event.type == "command":
        # Relational (source = the commander). Drives frustration↑ (NEGATIVE polarity -> the relation_filter
        # amplifies it for a DISRESPECTED source -> "frustration↑ at low respect", §5) AND carries the
        # transient command_pressure (= this value, read by cooperate/refuse, §8). No content (whether to
        # obey, not what to do); authority lives in context.
        out["command"] = SemanticInput(
            name="command",
            value=event.intensity,
            cls=InputClass.RELATIONAL,
            source=event.source,
            polarity=Polarity.NEGATIVE,
        )
        return out

    if event.type == "nightfall":
        # M7.5 Part B: the day/night signal (self, no source). Raises sleep_pressure; the sleep drive then
        # fires the SLEEP mode. A world/runner mode-control signal, like `activity` -- "the loop closes in
        # the world". Not a provocation (feeds no anger/frustration), so it opens no reactive reply.
        out["night"] = SemanticInput(
            name="night",
            value=event.intensity,
            cls=InputClass.SELF,
            polarity=Polarity.POSITIVE,
        )
        return out

    if event.type == "weather":
        # An environmental STRESSOR (e.g. a cold rain on a long watch): self, NO source. Wears at the
        # temper -- raises frustration and a little stress (the stress erodes effective_self_control). Like
        # `night`, a self signal, NOT a provocation from a person, so it opens no reactive reply; it just
        # sours the baseline mood, so the SAME later provocation can tip a rain-worn persona that a dry one
        # would shrug (displaced aggression from an unrelated cause). intensity = how bad the weather is.
        out["weather"] = SemanticInput(
            name="weather",
            value=event.intensity,
            cls=InputClass.SELF,
            polarity=Polarity.NEGATIVE,
        )
        return out

    # Unknown event types decompose to nothing in MVP (no guessed channels).
    return out
