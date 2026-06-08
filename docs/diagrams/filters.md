# Block diagram — the per-entity FILTER resolver (`engine/filters.py`)

> Pure, combinational (no dynamics, updates NO state). The **shared kernel** the input-channel filter
> stages call: the per-entity modulation *factor* and the entity→scalar *lookup* seam. Synchronized with
> `engine/filters.py`, and used by `engine/relation_filter.py` (M4a) + `engine/affinity_filter.py` (M4b).
> The filter **pipeline** (stage order, which stage touches which channel class) lives in
> [`relation_filter.md`](relation_filter.md); THIS file documents the kernel both stages share.

## Why this exists (the unification)

The same modulation shape — *scale a signal by a per-entity value, identity unless populated* — was
written out by hand in two separate filter modules (`relation_filter`, `affinity_filter`) and, inside
the first, a betrayal branch. They are now ONE formula + ONE lookup seam, called from both stages. The
already-data-driven potential edges (`*_x_respect_src`, `kindness_x_*`, evaluated by
[`potentials.md`](potentials.md)) are NOT folded in — they were never duplicated code — and the two
**trait**-keyed modulators (`gain_modulators`, `idle_recovery_modulator`) stay separate (a different
axis: persona-intrinsic, not entity-keyed). The resolver owns the per-entity gain ONLY, never the
appraisal gates (`command/kindness/bystander_pressure`).

## Functional form (domain language)

```
"How much does WHO/WHAT this event is about bend my reaction?"

  lookup(entity)  →  a scalar valence/bias for that entity      (0 = neutral / unknown)
  factor(value)   →  1 + gain · value                           (1.0 = leave the signal unchanged)
  signal          →  signal · factor                            (the channel value is scaled)

Neutral by default: an unlisted entity (lookup → 0) or a zero gain → factor 1.0 → identity.
A populated entry bends the reaction; nothing else changes.
```

## Control form (signal schematic)

```
              entity ─►┌─────────────────┐
                       │   lookup(seam)   │   table.get(entity, neutral)
   table (e→scalar) ─► │  e → scalar v    │──► v ───┐
                       └─────────────────┘          │
                                                     ▼
   sign (±1, caller) ───────────────────────►  (×)  ·  gain ───►  (1 + ·) ──► factor
                                                                              │
                       channel value  ───────────────────────────► (×) ◄─────┘
                                                                     │
                                                                     ▼
                                                          modulated channel value
```

- `lookup(entity, table, neutral=0.0)` — entity → scalar, `neutral` (0.0) when the entity is `None` or
  absent. **This is the seam**: today a flat dict `.get`; the discrete category→specific (IS-A)
  hierarchy or the cosine **affinity FIELD** (`Ideas/affinity_field_unification.md`) replaces the
  *internals* here without moving any call site. Empty table = neutral everywhere = identity.
- `factor(value, gain, sign=1.0)` — the modulation `1 + gain · sign · value`. `gain = 0` (the neutral
  config default) or `value = 0` → `1.0` (identity). `sign` is the **caller's** per-channel polarity
  (relational channels flip it by `polarity_sign`); it is not a per-entity property.

## Who calls it (the migrated stages)

| Stage | entity | table | sign | post |
|---|---|---|---|---|
| `affinity_filter` (M4b) | `target` (object) | `affinities` | +1 | `clamp_signed` the result |
| `relation_filter` (M4a) | `source` (agent) | `affective_bias` (derived_pre) | `polarity_sign(channel)` | `max(0,·) · social` |
| `relation_filter` betrayal | `source` | `trust` (per-source relation dim) | +1 | `max(0,·) · social` |

The betrayal value comes from a **nested** relation dimension (`relations[src].trust`), not a flat
`entity→scalar` map, so its caller fetches the scalar directly and uses `factor` for the formula — the
one structural exception to the `lookup` seam, and a natural thing the affinity FIELD would later absorb.

## Invariants
- **Identity by default** — unpopulated table or zero gain ⇒ factor 1.0 ⇒ the channel passes through.
  Every migration onto this kernel is **bit-identical by construction** (same arithmetic).
- **No state, no clamp here** — channel values are inputs, not states; the resolver returns a bare
  factor. Any clamping is the calling stage's choice (affinity clamps; relation does not — gains may
  push an input past 1.0, the state commit in `update` clamps).
- **No numeric literal** — `gain`, table values, `neutral` all come from config / the caller.
- **Feed-forward** — no integrator, no loop; introduces nothing for the pole/stability discipline.
