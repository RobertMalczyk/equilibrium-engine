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

    if event.type == "cold_reply":
        # Social Event Mapper Pack: a restrained negative reply -- colder than neutral, but not an
        # attack. Relational (source = the speaker), negative; the WEAKEST of the negative social
        # events. Expresses social distance / mild irritation / relational cooling. Like every
        # relational channel it routes through the relation_filter (per-source bias + public exposure)
        # and its state/relation deposits live in config (gains.*.cold_reply) -- the mapper stays dumb.
        out["cold_reply"] = SemanticInput(
            name="cold_reply",
            value=event.intensity,
            cls=InputClass.RELATIONAL,
            source=event.source,
            polarity=Polarity.NEGATIVE,
        )
        return out

    if event.type == "refusal":
        # Social Event Mapper Pack: a rejection of a request/order/invitation -- social friction, not
        # automatically an insult. Relational, negative; distinct from `command` (an order) and
        # `insult` (an attack). Friction + frustration, with a little respect/trust erosion (gains in
        # config). Magnitudes owned by calibration.
        out["refusal"] = SemanticInput(
            name="refusal",
            value=event.intensity,
            cls=InputClass.RELATIONAL,
            source=event.source,
            polarity=Polarity.NEGATIVE,
        )
        return out

    if event.type == "complaint":
        # Social Event Mapper Pack: verbalized dissatisfaction / negative social pressure -- not
        # necessarily an attack. Relational, negative; milder than `insult`, and weighted (in config)
        # toward the frustration/resentment paths more than raw anger.
        out["complaint"] = SemanticInput(
            name="complaint",
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

    if event.type == "wrongdoing":
        # M-J.0 moral cue: the persona did (or is reminded of) a wrong it is responsible for -- a lie,
        # a harm, a kept secret. SELF channel (no source): it deposits GUILT, scaled in config by the
        # `guilt_proneness` trait (gain_modulator) so a guilt-prone persona feels it more. A finite
        # single-tick deposit into the leaky `guilt` integrator -- NOT a Dirac spike. Inert unless the
        # moral overlay supplies `gains.guilt.wrongdoing` (legacy personas have no such gain).
        out["wrongdoing"] = SemanticInput(
            name="wrongdoing",
            value=event.intensity,
            cls=InputClass.SELF,
            polarity=Polarity.NEGATIVE,
        )
        return out

    if event.type == "probe":
        # M-J.0 moral cue: being questioned / accused by SOMEONE (source = the questioner). It deposits
        # EXPOSURE_ANXIETY (afraid of being revealed) and a little frustration (interrogation pressure) --
        # the small sourced provocation is what OPENS the reactive reply window (a confession is a reply
        # to being probed; cf. _event_is_provocation). RELATIONAL, so it routes through the relation_filter
        # like any sourced event. Inert unless the overlay supplies its gains.
        out["probe"] = SemanticInput(
            name="probe",
            value=event.intensity,
            cls=InputClass.RELATIONAL,
            source=event.source,
            polarity=Polarity.NEGATIVE,
        )
        return out

    if event.type == "confide_opportunity":
        # M-J.2 moral cue: a TRUSTED confidant is privately present (source = the confidant). BENIGN and
        # RELATIONAL -- it deposits NO negative state (not a provocation, not a stressor); it only marks
        # WHO is here this tick so the per-source `relation_source` trust factor can let `confide` fire to a
        # trusted ear. It does not itself open the reactive window (a confide is a reply made WHILE the
        # interrogation window from a recent `probe` is still open, spec reactive_window_ticks). Inert unless
        # the moral overlay configures the `confide` action.
        out["confide_opportunity"] = SemanticInput(
            name="confide_opportunity",
            value=event.intensity,
            cls=InputClass.RELATIONAL,
            source=event.source,
            polarity=Polarity.POSITIVE,
        )
        return out

    if event.type == "accusation":
        # M-J.3 moral cue: SOMEONE accuses the persona of a wrong (source = the accuser). RELATIONAL and a
        # PROVOCATION -- via the overlay it deposits perceived_injustice ("this is unfair", scaled by
        # injustice_sensitivity), avoidance_drive (scaled by conflict_avoidance), a little stress and
        # frustration (the frustration is the sourced provocation that OPENS the reactive reply window, so
        # avoid/blame_other can be selected), and resentment toward the accuser. Whether it lands as guilt
        # (a TRUE accusation, the persona already carries guilt) or pure grievance (a FALSE one, no prior
        # guilt -> perceived_injustice dominates and the injustice->guilt(-) switch keeps guilt low) emerges
        # from state, not the event. Inert unless the moral overlay supplies its gains.
        out["accusation"] = SemanticInput(
            name="accusation",
            value=event.intensity,
            cls=InputClass.RELATIONAL,
            source=event.source,
            polarity=Polarity.NEGATIVE,
        )
        return out

    # Unknown event types decompose to nothing in MVP (no guessed channels).
    return out
