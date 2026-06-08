# Block diagram — mapper (M3, the front seam: event → channels)

> Pure, combinational (no dynamics) — so this is an **I/O contract + a routing schematic**, not an
> integrator diagram; the channel→state wiring lives in `wiring.md`. Synchronized with `engine/mapper.py`.
> **Responsibility:** decompose one `RawEvent` into many **tagged** `SemanticInput` channels; set
> `source`/`target`/`cls`/`polarity`; read `affinity[item]` into `preference_match` and history into
> `repetition`/`novelty`. **Does NOT** apply relational/affinity weights ("semantic and dumb") — that's the
> filters.

## I/O
`In:` RawEvent + PersonaConfig + HistoryFeatures. `Out:` SemanticInputVector (base, tagged).

## Routing (event → channels, with class tag that drives the filter dispatch)

```
food_given ─┬─► food_nutrition   (self,    value=intensity)
            ├─► preference_match  (AFFINITY, target=item, value=affinity[item])   ──► affinity_filter
            ├─► repetition        (self,    value=history.repetition_score)
            └─► novelty           (self,    value=history.novelty_score)

insult ────► insult  (RELATIONAL, source=event.source, polarity=NEGATIVE)         ──► relation_filter
help ──────► help    (RELATIONAL, source=event.source, polarity=POSITIVE)         ──► relation_filter

<unknown event> ─► ∅   (no guessed channels in MVP)
```

Class → downstream routing (the dispatch realized by the filter stages): `relational` (has source) →
`relation_filter`; `affinity` (has target) → `affinity_filter`; `self` (neither) → identity.
**Deferred (stage 2):** `command`/`praise`/`promise_kept`/`promise_broken`/`apology`/`threat` event types.
