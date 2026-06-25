# M-J Moral Tension / Secrecy Dynamics — master plan

> **STATUS (2026-06-25): IMPLEMENTED + CALIBRATED, merged to `main`.** All slices M-J.0–M-J.4.4 are
> built, opt-in, and byte-identical for legacy personas. Calibration is closed (suspicion 24h &
> serious-guilt ~72h half-lives judge-validated; moral corpus 4.0–4.83/5). Test results:
> [`eval/MORAL_REPORT.md`](../eval/MORAL_REPORT.md). This doc is kept as the historical execution record.

> Single execution plan tying together the four design docs. **Planning only — no engine code written.**
> - `moral_tension_review.md` — concept review (engine/logic/relation/outcome)
> - `moral_tension_impl_spec.md` — detailed implementation spec (states/ledger/equations/coupling/trace)
> - `moral_tension_test_plan.md` — scope-expansion test strategy
> - this file — the phased execution plan + engine-verification record + risk register
>
> Branch: `feature/m-j-moral-tension` (off `main` @ `d84b7c6`).

---

## 1. Goal & non-goals

**Goal:** a deterministic, config-backed engine layer for secrets, lies, guilt, exposure anxiety,
suspicion, repair/confession/confiding, and false accusation — where visible behavior **emerges from
internal state dynamics**, coupled into the existing states, never scripted.

**Non-goals:** no LLM in the loop; no RNG; no Inn/quest logic (engine-only — §9 boundary); no new corpus
on top of the existing budget; no same-tick ledger mutation.

---

## 2. Engine-verification record (claims checked against code, 2026-06-23)

| Spec claim | Verified against | Result |
|---|---|---|
| moral states append to `GLOBAL_STATES` | `engine/schema.py:17` (10-tuple) | ✅ code-tuple edit; `duty`/`sleep_pressure` already follow the "decoupled, long half-life, dt-unchanged" pattern |
| `suspicion` appends to `RELATION_DIMS` | `engine/schema.py:32` `("trust","respect","resentment")` | ✅ one-line tuple edit |
| moral traits append to `TRAIT_NAMES` | `engine/schema.py:34` (10-tuple) | ✅ tuple edit |
| moral actions append to `POTENTIAL_NAMES` | `engine/schema.py:48` (6-tuple) | ✅ tuple edit |
| gains/couplings are pure data | `PersonaConfig.gains/couplings : dict[str,dict]` (schema.py) | ✅ **moral weights = config only, no code** |
| ledger frozen into snapshot | `Snapshot` is `@dataclass(frozen=True){global_state,relations,mode}` (schema.py:193) | ⚠ needs **append-only field + `freeze()` edit** (default-empty) — covered by §8.1 |
| moral events via mapper | `engine/mapper.py` `if event.type==...`, unknown→no-op (mapper.py:173) | ✅ append handler blocks; existing scenarios unaffected |
| two mutation sites | `_commit` (simulation.py:39) in `update` + `post_effects` | ✅ ledger writes only in `post_effects` |
| canonical trace ordering | `engine/debug.py:18` orders by the 4 tuples | ✅ append-only keeps determinism |

**Conclusion:** topology is implementable on the existing architecture. Code edits are confined to:
(a) the four canonical tuples, (b) one `Snapshot` field + `freeze()`, (c) mapper handler blocks,
(d) the `update`/`potentials` reads of moral state, (e) ledger write in `post_effects`, (f) `trace_v2`
serialization. Everything else (all magnitudes/edges) is config.

---

## 3. Architecture decisions (locked)

1. Moral states = integrators-with-decay, default-inert, appended to `GLOBAL_STATES`.
2. `suspicion` = 4th `RELATION_DIMS` entry, default 0, filtered per source.
3. `MoralLedger` (Secret + LieRecord + `rumor_by`) read-only in `update`, mutated only in `post_effects`,
   emits cues as events; serialized into the trace.
4. **One-tick moral latency** (impl spec §1.1): cue booked at T, ledger written `post_effects`(T),
   observed at T+1. Same-tick reflexes only via existing global-state couplings.
5. Lie/confession are **deterministic potentials + thresholds**, never sampled probabilities.
6. `empathy` is a **separate** trait (not aliased to gratitude); `anxiety→threat_sensitivity`.
7. Outburst stays gated by the existing burst latch; moral states only feed anger/stress/frustration.
8. Three compatibility/validation gates (A legacy byte-identical / B zero-gain equivalence / C overlay
   invariants) — impl spec §9.1.
9. Knowledge model: `known_by` (truth) vs `rumor_by` (partial) vs `suspicion` (pressure) — never auto-promote.
10. `trace_v2` / moral feature flag; legacy trace omits moral fields; new fields have deterministic defaults.

---

## 4. Phased execution (vertical slices; each ships a synced diagram — CLAUDE.md directive)

Each slice: **spec delta → `docs/diagrams/moral_tension.md` (both forms) → config keys → code →
property/contrast tests → Jury stability check → Gates A/B green → DoD checklist.**

- **M-J.0 — Guilt core.** One config-seeded secret (no ledger objects yet). States `guilt`,
  `exposure_anxiety`. Couplings → stress(+), anger(− empathy-gated), trust. Actions `confess`,
  `remain_silent`. Trait adds: `empathy`, `guilt_proneness`, `shame_sensitivity`, `honesty_humility`.
  **Litmus:** guilt-prone confesses earlier than low-guilt, same scenario. First `trace_v2`.
- **M-J.1 — Lie loop.** `LieRecord` + ledger infra, `cognitive_load_from_lies`, `consistency_debt`.
  Actions `lie`, `deflect`. Couple → fatigue/stress. `lie_detected` → target anger/resentment/−trust.
  Traits: `machiavellianism`, `lie_skill`. Lifecycle rules (impl spec §3.5).
- **M-J.2 — Repair & confiding.** `repair_drive`, `rumination`, `avoidance_drive`. Actions `confide`,
  `apologize`, `repair`. Safe vs gossip-prone confiding (`gossip_tendency`/`rumor_by`). Secret
  lifecycle/inactivation (§3.4).
- **M-J.3 — Accusation/scapegoat.** `perceived_injustice`, `suspicion` dim. Events `accusation`,
  `false_accusation`, `suspicion_raised`, `blame_shift`. Trait `injustice_sensitivity`,
  `conflict_avoidance`. **Multi-agent witness fan-out blocked on M-MEM (spec §13.1)** — sequence M-MEM
  first or model accused+accuser only.
- **M-J.4 — Full ledger + calibration grid + scoped corpus.** Calibration runner (§10), the
  `M-J-MORAL-OVERLAY-*` slice, the four labeled categories within the 1400+1400 budget.

**Stability gate before any calibration:** linearize and Jury-test the two loops —
salience↔guilt↔exposure_risk and rumination↔stress↔fatigue (poles in unit circle or saturating /
extinction treatment).

---

## 5. Test strategy (bounded; impl spec §9)

Total generated corpus stays **1400 one-day + 1400 multi-day** — M-J is an overlay axis *within* it,
partitioned into labeled categories (not added on top):

| Label | Judged by |
|---|---|
| `M-J-LEGACY-COMPATIBILITY` | Gate A — byte-identical legacy hashes |
| `M-J-ZERO-GAIN-EQUIVALENCE` | Gate B — non-moral behavioral equivalence |
| `M-J-MORAL-OVERLAY-ONE-DAY` (700, within budget) | Gate C — moral invariants + trace explainability |
| `M-J-MORAL-OVERLAY-MULTI-DAY` (700, within budget) | Gate C — moral invariants + trace explainability |

Plus a small isolated micro-suite (tens of cases) for mechanism unit-proofs, counted inside the budget.
Invariants & stability tests: impl spec §9.2–9.3.

---

## 6. Risk register (carried from review; mitigations locked)

| # | Risk | Mitigation |
|---|---|---|
| R1 | golden drift from schema change | `trace_v2`; legacy mode omits moral fields → Gate A byte-identical |
| R2 | ledger as parallel hidden state | read-only in `update`, written only in `post_effects`, traced |
| R3 | non-determinism via probability | deterministic potentials + thresholds, no RNG |
| R4 | salience self-amplification loop | saturating `f_guilt`/`f_expo`; Jury check |
| R5 | rumination↔stress↔fatigue runaway | net loop gain < 1; idle_recovery on moral states; Jury |
| R6 | multiplicative impulses → dead system | `Σ gain·∏term` form; sanity gate asserts moral movement |
| R7 | multi-agent witness gap | propagation in world driver; **blocked on M-MEM**; sequence first |
| R8 | scope creep vs "less is more" | ship M-J.0 first; topology decided now, built in slices |
| R9 | trait duplication | de-dup map; `empathy` separate, `anxiety→threat_sensitivity` |
| R10 | overlay confounds attribution | labeled probe windows + moral trace fields + micro-suite |
| R11 | judge-model confound | hold judge model constant; prefer deterministic narration-diff |

---

## 7. Definition of Done (per slice)

Architecture: no LLM ✦ no literals in code ✦ all tunables in config ✦ synchronous single-commit ✦ no
event→action scripting ✦ moral coupled to existing states ✦ trace explains outcomes ✦ ledger
read-only in `update` / written only in `post_effects` ✦ no RNG ✦ Jury-stable ✦ diagram synced.
Compatibility: Gate A byte-identical, Gate B equivalent, `trace_v2` explicit, deterministic defaults.
Latency: one-tick documented, no mid-tick ledger mutation.
Corpus: overlay within 1400+1400, reproducible seeds/IDs, existing corpora intact.
Knowledge: known_by/rumor_by/suspicion separated, lifecycle correct, inactive secrets/stale lies inert.
Traits: empathy separate, de-dup map documented.

---

## 8. Open decisions (to confirm before M-J.0 code)
- `rumor_by` shape: `map[AgentId,float]` (chosen) vs plain list.
- `suspicion` as 4th relation dim (chosen) vs parallel per-source map.
- conscientiousness/norm_rigidity: folded vs separated (defer to contrast tests).
- micro-suite exact size and source split.
- `responsibility`/`justification` as authored Secret constants (chosen) vs partly emergent.

## 9. Engine / Inn boundary
Engine-only. `equilibrium-inn` consumes the public surface, configures profiles/scenarios, renders
traces — **no moral equations in the Inn**; handled separately after a stable public surface + commit pin.

## 10. Immediate next step (post-approval)
Author `docs/diagrams/moral_tension.md` (control + functional forms) for **M-J.0** and the spec delta to
`rpg_persona_dynamics_spec_v1.md` (new states + `suspicion` dim + ledger seam + traits), get sign-off,
then implement M-J.0 as a vertical slice.

## 11. Progress log & the M-MEM detour (2026-06-24)

Implemented and pushed on `feature/m-j-moral-tension` (17 commits over `main`, HEAD `fd95191`):
M-J.0 guilt core · M-J.1 lie loop (internal cognitive-load) · M-J.2 repair/rumination + the `confide`
safe-vs-gossip split + `apologize` relational reparation · M-J.3.0 plumbing (opt-in `suspicion` relation
dim + accusation vocab, byte-identical) · M-J.3.1 accusation core (grievance switch
`perceived_injustice→anger(+)`/`→guilt(−)`, `blame_other`/`avoid`) · M-J.3.2 `suspicion_cue`
(pressure-without-truth). Suite 333 passed; goldens byte-identical; Jury-stable.

**Why we branched off to M-MEM (do NOT lose this):** the *remaining* M-J.3 work is not deferrable by
effort — it is **architecturally blocked** (risk **R7**, spec §5.6 / §13.1). Specifically:
- **multi-agent witness fan-out** — when an accusation/exposure happens, every witness must receive a
  per-witness event *on the same tick* (trust loss, suspicion, rumor spread). The mapper today maps
  **exactly one `RawEvent` per tick**, so simultaneous fan-out is unrepresentable.
- **`false_accusation` accuser-after-discovery guilt** — needs the accuser's runtime to receive a
  discovery event *while* witnesses receive theirs (same multi-event tick).

Both need a **multi-event mapper / per-tick event list** = the **M-MEM** capability. M-MEM is foundational
and reusable (not moral-specific), so it is being built on its own branch **`feature/m-mem-multi-event`**
(cut from `main`, NOT from this branch) so it can be reviewed and merged to `main` independently. The
moral overlay stays focused here.

**Re-entry plan after M-MEM lands on `main`:** rebase this branch on the updated `main` (or merge `main`
in), then build **M-J.3.3 witness fan-out + false-accusation discovery** as a vertical slice on top of
both. The single-runtime accused/accuser/suspicion mechanics already implemented here are the building
blocks; M-MEM only supplies the simultaneous-delivery seam. Still also pending: **M-J.4** (full `LieRecord`
ledger + lie detection + `blame_shift` lie_type + calibration grid + scoped corpus) — that one is
self-contained and does NOT need M-MEM, so it can proceed in parallel if desired.
