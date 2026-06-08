# RPG Persona Dynamics — calibration scenarios and expectation schema

> Scenarios are **executable data** (they map onto the `Scenario` type from spec §3): persona +
> `initial_overrides` + a list of `RawEvent`s on integer `t`. Each carries a **machine-checkable
> expectation**. The loop that runs and evaluates them is in `spec_v1.md` §16 (Calibration harness).
>
> A human steps in **once, offline**: curator of the set (an LLM generates candidates → the human
> picks 30–50) and of the acceptance thresholds. Below is the **manual seed** (11 scenarios), grouped
> by the mechanism they validate. Expectations are **comparative** wherever possible (safer than numbers).

## Expectation schema (predicate DSL over the trace)

Each predicate → a contribution to the loss: **0 when satisfied, penalty ∝ margin of violation** when not.

- **boolean:** `metric == value` — e.g. `outburst_fired == true`.
- **comparative (persona contrast):** `metric[personaA] > metric[personaB]` — same scene, different personas.
- **ordering (after a sweep):** `metric[low] < metric[mid] < metric[high]` — e.g. by `patience`.
- **threshold:** `metric > v` / `metric < v` — e.g. `resentment_delta < 0`.
- **shape (curve shape):** `monotonic_up/down`, `peak`, `converges_to(v, within=T)` — the shape of the
  state trajectory, not the endpoint.

Comparative/ordering predicates require running **several personas through the same scenario** — the
community cast provides ready contrast pairs.

## Metric library (extractor `trace → metrics`)

Reusable, one per project: `outburst_fired`, `action_sequence`, `peak_<state>` (e.g. `peak_anger`),
`<state>_delta` / `<relation>_delta`, `time_to_interrupt`, `drive_switch_tick`, `proactive_start_count`,
`<state>_curve` (a series for shape predicates), `final_action`, `interrupt_count`. Adding a metric =
adding a pure function over the trace.

## The set (manual seed)

### A. Accumulation and state modulation — the flagship
- **`same_soup_good_day`** — Marta serves the same soup N× to one recipient; recipient: well-fed,
  rested, trusting. → grumbling/neutral. `outburst_fired == false`; `boredom_curve = monotonic_up`.
- **`same_soup_bad_day`** — the same recipient, but tired, bored, resentful. → a burst.
  `outburst_fired == true`. **Paired with good_day:** same persona, different starting state → different action.
- **persona contrast (same N):** `N_to_burst[Branic] < N_to_burst[Halgrim]`.

### B. Proactive path (integrate-and-fire)
- **`idle_watch`** — a watch with no events. `boredom_curve = monotonic_up` until `urge ≥ theta_start` →
  `proactive_start_count ≥ 1` (`seek_stimulus`); after the start satisfaction↑, boredom↓. **Contrast:**
  `start_tick[Welf] < start_tick[Halgrim]`.
- **`long_shift_switch`** — a long shift; both boredom and fatigue rise. **Switch of the winning drive:**
  early `seek_stimulus`, late `rest`. `action_sequence` contains `seek_stimulus` **before** `rest`;
  `drive_switch_tick` exists.
- **`boredom_cycle_rapid`** (Lutek) — a long idle stretch. A dense, regular series of starts without
  runaway: `proactive_start_count` high, intervals ~regular, `peak_<state>` without monotonic
  escalation. **Frequency contrast:** `start_count[Lutek] ≫ start_count[Welf] > … > start_count[Halgrim]`.

### C. Selector arbitration
- **`pestering_interrupts`** — an NPC mid-activity (BUSY); a series of small, low-impact pokes. Early
  "in passing" (the activity continues), the accumulated state eventually crosses `theta_interrupt` →
  interrupt + reaction. `interrupt_count == 1`; the interrupt happens **after** several pokes (not the
  first); state rises despite the absence of interrupts (the invariant "state always counts").
  **Contrast:** `pokes_to_interrupt[Branic] < [Halgrim]`.

### D. Relational evaluation
- **`public_vs_private_insult`** — a public vs a private insult. `outburst_potential[public] >
  [private]` (the `social_exposure` modifier). **Three points on the insult axis:** Wojslaw → `outburst`;
  Halgrim → `cold_response`; Lutek → a light/`neutral` reaction, `outburst_fired == false`.
- **`repeated_command`** — repeated orders from an authority (Wojslaw/Edda). A loyal one (respect↑ toward
  the source) → `cooperate`; an independent one (respect↓, nfc↑) → rising frustration →
  `refuse`/`cold_response`. **Contrast:** `final_action[Halgrim] == cooperate` vs `refuse ∈ action_sequence[Branic]`.
- **`prisoner_bias`** — Cichy starts from deep resentment. **Asymmetry:** a guard's positive lands
  weakly, the negative strongly. `trust_delta(help) [Cichy] < trust_delta(help) [neutral_persona]`;
  `anger_delta(insult) [Cichy] > [neutral]`. **Visible action (the litmus bar — not just numbers):** the
  resented guard's overture is received **coldly** → `cold_response ∈ action_sequence[resentful]`, while
  the neutral guard draws no visible reaction → `action_sequence[neutral] == {neutral}`. The carrier is
  `cold_response`, **not** `refuse`: `refuse` means "I won't obey an **order**" and is command-gated (§8) —
  there is no order here, so resentment surfaces as a **cold reception**. The relational filter already
  carries it (`resentment[guard]` amplifies the insult → `anger↑` → `cold_response↑`): resentful Cichy's
  cold_response (≈0.28) exceeds neutral's (≈0.20). What it doesn't clear is the shared `react.cold_response
  = 0.50`, and a single shared threshold can't (the **Lutek collision**: stoic Lutek at ≈0.40 must read
  NEUTRAL while resentful Cichy at ≈0.28 must CROSS — `0.28 < 0.40` inverts the order; a `resentment[src]`
  term was rejected because `potentials` read state′, so the insult's same-tick deposit lifts Lutek too). So
  GATE 3 gives Cichy a **TEMPORARY per-persona `react.cold_response ≈ 0.24`** — a private threshold that
  **decouples the prisoner from the burst litmus by construction** (the global `0.50` is untouched). *Gate
  (min-margin): resentful Cichy reads cold_response EVERY tick from the overture to window-end; neutral Cichy
  + Lutek + the burst contrast are unchanged (regression guards, slack by construction). The per-persona
  threshold is a STOPGAP for an undifferentiated `insult→anger` (Lutek doesn't shrug a fresh insult); the real
  fix (`pride→insult-anger`) is a deferred milestone re-validating Layer 2.*

### E. Recovery / anti-runaway
- **`betrayal_after_trust`** — building trust, then `promise_broken`. `trust_delta < 0` **and**
  amplified anger (the betrayal exception on trust). **Contrast:** `peak_anger[high_trust] >
  [low_trust]` (betrayal hurts **more** when trust is high).
- **`apology_after_betrayal`** — after a betrayal, a series of `apology`+`help`+`promise_kept`.
  `resentment_curve = converges_to(low, within=T)` (it genuinely comes down in finite time).
  **Contrast:** faster recovery with high `gratitude`.

### F. Community (scripted cross-influence)
- **`observed_insult`** — Wojslaw publicly criticizes Marta's cooking. **Multi-target:** Marta's reaction
  (`resentment_delta[Marta→Wojslaw] > 0`) **and** the witnesses' (`respect_delta[Halgrim→Wojslaw] < 0`).
  Validation of multi-target events (perpetrator/target/witness) on the relation graph.

## Note on `t`

Decay is per tick, so the **spacing of `t`** in the timeline matters (e.g. `same_soup` on `t: 0,10,20`
gives a different result than `0,1,2`). The intervals are part of the scenario and are calibrated along
with the rest.
