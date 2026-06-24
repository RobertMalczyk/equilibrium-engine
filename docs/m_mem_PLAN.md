# M-MEM — multi-event-per-tick mapper — plan

> Branch: `feature/m-mem-multi-event` (off `main` @ `d84b7c6`). Engine-only, reusable; NOT moral-specific.
> Unblocks the moral M-J.3.3 witness fan-out + false-accusation discovery (review R7), and any future
> mechanic where several cues land on the SAME tick.

## 1. The constraint being lifted

Today the engine delivers **exactly one `RawEvent` per tick**:
- `simulation.run_scenario` builds `events_by_t: dict[int, RawEvent] = {ev.t: ev for ev in events}` —
  two events sharing a `t` **silently collide; the last one wins** (`engine/simulation.py`).
- `simulation.tick(runtime, t, event: RawEvent | None)` takes a single event, and every per-tick signal
  is derived from that one event: `event_source`, the mapped channel vector, `is_provocation`,
  `kindness_pressure`, `bystander_pressure`, `refractory_pressure`, `is_stressor`, `reaction_target`,
  the SEEKING→activity engage, and the bookkeeping (`history_log.append`, `last_provocation_*`,
  `last_stressor_t`).

Goal: a tick may carry **0, 1, or many** events, each mapped and merged, with deterministic multi-source
arbitration — while a scenario with **≤1 event per tick stays byte-identical** (all existing goldens hold).

## 2. Design

- **Grouping.** `run_scenario` → `events_by_t: dict[int, list[RawEvent]]` (stable order = scenario order).
- **`tick(runtime, t, events: list[RawEvent])`.** Empty list = idle tick (today's `None`).
- **Map + merge.** Map each event → `SemanticInputVector`; MERGE into one effective vector. Each
  `SemanticInput` already carries its own `source`, so channels from different sources stay correctly
  attributed; the relation_filter / update already key deposits by `si.source`. Collision rule on the SAME
  channel name (e.g. two `probe`s): deterministic additive combine (sum of values; document the rule).
- **Per-source arbitration (the subtle part).** The scalar signals that assume one source become
  aggregations over the tick's events:
  - `is_provocation` = ANY event is a provocation; the **primary provoking source** = the provocation with
    the max anger/frustration contribution (ties → scenario order) → drives `reaction_target`,
    `last_provocation_source`, refractory/bystander policy.
  - `kindness_pressure` = the appraised kindness aggregate (a provocation on the tick suppresses it, as today).
  - `is_stressor` = ANY sourceless stressor present.
  - These reduce to the single-event values when the list has length ≤ 1 (the byte-identical invariant).
- **Trace.** `TickTrace.event` keeps the **primary** event (the only event when len ≤ 1) so single-event
  goldens are byte-identical; a new `events` field is emitted ONLY when len > 1 (opt-in, like the moral
  fields), so single/none-event traces gain no field.
- **Bookkeeping.** `history_log` appends all events (order preserved); `last_provocation_*` keyed on the
  primary provoker; `last_stressor_t` if any stressor.

## 3. Slices (vertical; each ships tests + byte-identical goldens)

- **M-MEM.0 — plumbing + merge (byte-identical for ≤1 event/tick).** events list, map+merge, primary-event
  arbitration, opt-in `events` trace field. Property test: two events on one tick BOTH land (today one is
  dropped); golden suite unchanged.
- **M-MEM.1 — multi-source provocation/target arbitration.** Nail the primary-provoker policy under
  genuinely conflicting sources (two provokers, provoker+gesture, provoker+bystander). Contrast tests.
- **M-MEM.2 — fan-out helper for the world driver.** A scenario/driver convenience to emit per-recipient
  events on one tick (the witness fan-out seam the moral layer will consume). No moral logic here.

## 4. Invariants / DoD (per slice)
No LLM ✦ no RNG ✦ deterministic merge + arbitration (sorted/explicit order, never dict-iteration order) ✦
≤1 event/tick byte-identical (Gate A: existing goldens) ✦ multi-event trace is opt-in (single-event traces
unchanged) ✦ synchronous discipline preserved (map/merge before update; one commit) ✦ each per-source
signal documented as "reduces to the single-event value at length ≤ 1".

## 5. Boundary
Engine-only. The moral M-J.3.3 slice (witness fan-out + false-accusation discovery) consumes M-MEM AFTER it
lands on `main`; no moral equations here.
