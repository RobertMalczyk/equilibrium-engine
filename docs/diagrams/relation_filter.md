# Block diagram — relation_filter (M4a) + affinity_filter (M4b): the filter pipeline

> Pure, combinational (no dynamics, updates NO state) — an **I/O contract + signal schematic**, one
> stage per channel class in a **uniform pipeline of identity stages** (the dispatch from spec §5 is its
> form: a non-matching channel passes through an identity stage, it is NOT a special-cased `if`).
> Synchronized with `engine/relation_filter.py` + `engine/affinity_filter.py`. The per-entity
> modulation (`amp` / valence factor below) is computed by the shared kernel `engine/filters.py`
> (`factor` + `lookup`); see [`filters.md`](filters.md) for that kernel and its FIELD/hierarchy seam.

## Pipeline order (per channel)

```
SemanticInputVector ─► relation_filter ─► affinity_filter ─► (per-event) ─┐ M-MEM merge in simulation.tick:
                       (touches source-tagged)  (touches target-tagged)    └─► EffectiveInputVector
                                                                               (channel → LIST of inputs)
```
A channel can carry both source and target ("forced to eat a spider") → both stages, relational→affinity.
**M-MEM:** the filters run **per event** (unchanged); `simulation.tick` merges each event's filtered output
into the `EffectiveInputVector`, where a channel may hold several inputs (one per source firing it this tick).

## relation_filter (channels with a `source`)

```
   for each relational channel k (source=src):
       amp = 1 + bias_gain · polarity_sign(k) · affective_bias[src]      (liked src damps negatives, etc.)
       amp = max(0, amp) · social                                        social = 1 + social_exposure_gain  (if context.public)
       k.value ← k.value · amp                                           (NOT clamped: it is an input, not a state)
   BETRAYAL EXCEPTION: keys on trust (spec §5) — betrayal lands HARDER when trust is high,
                       instead of being damped by positive bias.
   non-source channels ─► identity (pass through)
```
Inputs: affective_bias[src] from derived_pre (= 0.50·trust + 0.40·respect − 0.70·resentment).

## affinity_filter (channels with a `target`)

```
   for each affinity channel k (target=obj):
       k.value ← clamp_signed( k.value · (1 + valence_gain · affinity[obj]) )
   MVP: valence_gain = 0  → IDENTITY (the valence already rides in preference_match=affinity[item] from the
   mapper). Hook kept so the stage is part of the uniform pipeline. Phobias (preference→fear) = stage 2.
   non-target channels ─► identity
```

## Invariants
- Each stage touches ONLY channels with its tag; everything else is identity. Updates no state.
- Channel values are inputs, not states — relation_filter does not clamp (gains scale them; the state
  commit in `update` clamps). So an amplified insult can exceed 1.0 as an input.
