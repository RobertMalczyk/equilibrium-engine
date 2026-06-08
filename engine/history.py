"""history.analyze (M2).

In: log + current event + t. Out: HistoryFeatures. Pure, deterministic; mutates nothing;
interprets NO semantics (counts and recency only -- the mapper turns these into channels).
Window sizes and normalizers come from config (history_params), never literals here.
"""

from __future__ import annotations

from engine.clamp import clamp01
from engine.schema import HistoryFeatures, PersonaConfig, RawEvent


def analyze(
    log: list[RawEvent], event: RawEvent, t: int, config: PersonaConfig
) -> HistoryFeatures:
    hp = config.history_params
    recent_window = hp.get("recent_window", 0.0)
    repetition_norm = hp.get("repetition_norm", 1.0)

    same_event_recent = same_event_long = 0
    same_item_recent = same_item_long = 0
    last_same_t: int | None = None

    for past in log:
        same_type = past.type == event.type
        same_item = event.item is not None and past.item == event.item
        in_recent = (t - past.t) <= recent_window

        if same_type:
            same_event_long += 1
            if in_recent:
                same_event_recent += 1
            if last_same_t is None or past.t > last_same_t:
                last_same_t = past.t
        if same_item:
            same_item_long += 1
            if in_recent:
                same_item_recent += 1

    time_since = (t - last_same_t) if last_same_t is not None else None

    # Repetition rises with recent same-item occurrences; novelty is its complement.
    repetition_score = (
        clamp01(same_item_recent / repetition_norm) if repetition_norm > 0 else 0.0
    )
    novelty_score = clamp01(1.0 - repetition_score)

    return HistoryFeatures(
        repetition_score=repetition_score,
        novelty_score=novelty_score,
        same_event_count_recent=same_event_recent,
        same_event_count_long=same_event_long,
        same_item_count_recent=same_item_recent,
        same_item_count_long=same_item_long,
        time_since_last_same_event=time_since,
        recent_positive_contact=0.0,
        recent_negative_contact=0.0,
    )
