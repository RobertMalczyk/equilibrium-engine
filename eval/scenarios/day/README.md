# "Normal day" scenarios (generated)

Seeded, per-persona "normal day" scenarios for the persona-dynamics engine. **100 files
per persona × 7 personas = 700 files.** Each file is one believable **24 h day** for that
persona — events across the ~17 h **waking** day (meals at meal-times, sparse triggers), then a
`nightfall` that runs the night/sleep reset — with events drawn from a **per-persona distribution**
that reflects the persona's social role.

Run each through **`load_eval_persona_timescale`** (the believable per-dimension time constants;
see [`calibration/calibrated_timescale.yaml`](../../../calibration/calibrated_timescale.yaml) and
`eval/timescale_keeper.py`) for `DAY_TICKS` (~717) ticks at dt ≈ 120 s. The corpus runner is
[`eval/judge_corpus.py`](../../judge_corpus.py).

Generator: [`eval/generate_day_scenarios.py`](../../generate_day_scenarios.py).
Re-run it to regenerate byte-identical files.

---

## Event-vocabulary mapping (the four engine verbs)

The engine (`engine/mapper.py`) accepts **exactly four** event types and rejects anything
else. There is **no** neutral "social"/"meeting" event, so a day's activities are mapped
onto these four verbs. The persona is always the **subject**; each event is something done
**to** it by a `source`.

| Verb         | Day meaning here                              | Key fields |
|--------------|-----------------------------------------------|------------|
| `food_given` | a meal / feeding (routine)                    | `item: cabbage_soup`, `intensity` ~1.0, `context.public: false` |
| `command`    | someone orders the persona                    | `source` = a commander, `context.has_authority: true` |
| `help`       | someone assists the persona (benign contact)  | `intensity`, empty `context` |
| `insult`     | a slight / friction                           | `context.public: true|false` |

Mapping limitation: benign social contact (chatting, trading, standing watch together) has
no dedicated verb, so it is expressed as `help` (assistance) where plausible, and otherwise
left as **idle time** (most ticks carry no event). Neutral co-presence cannot be encoded
without overloading one of the four verbs, so we do **not** encode it.

---

## Sources rule (relations only)

An event `source` must be someone the persona actually **has a relation with**
(`initial_relations` in `data/personas/<persona>.yaml`) — the engine reads
`relation[source]`. Valid sources used per persona:

| Persona  | Valid sources used                |
|----------|-----------------------------------|
| halgrim  | marta, player, edda, wojslaw      |
| wojslaw  | marta, player                     |
| cichy    | player, **guard** (via override)  |
| branic   | halgrim, marta, player            |
| lutek    | player, marta                     |
| welf     | player                            |
| edda     | halgrim, marta, player            |

`cichy` is the only persona that introduces a **new** source: a `guard`, added through a
minimal `initial_overrides.relations` block exactly as `data/scenarios/prisoner_bias_resentful.yaml`
does (a resented guard: trust 0.05 / respect 0.10 / resentment 0.85). This is the prisoner's
day-to-day counterpart, so the guard is a valid related source.

---

## Per-persona day profiles

Role and relation directions come from `docs/rpg_persona_dynamics_persony.md`. **Meals** use
a roughly scheduled count (Normal around a routine baseline, jittered around fixed day-fraction
slots). **Slights / help / commands** are sparse, bursty **triggers**: Poisson counts (or a
Normal count for Wojslaw's frequent slights) layered **on top of** the routine, with timing
spread uniformly across the day.

- **cichy** (prisoner) — mostly **nothing**; long idle stretches. ~2–3 guard meals, an
  occasional guard slight (Poisson), rare player help. Baseline mood: mild boredom/frustration.
- **wojslaw** (proud noble) — **social all day**: frequent help + commands + meals, with
  insults under a Normal-count baseline (easily slighted; ~half public).
- **halgrim** (watch sergeant) — **duty rhythm**: commands from **both Edda (respected, ~2/3)
  and Wojslaw (resented, ~1/3)** so the obedience contrast is visible across the 100 days
  (cooperate days AND refuse days), some friction from Wojslaw, routine meals, a little help.
- **edda** (castellan / authority) — **runs the fort**: frequent help/consultation, routine
  meals, she rarely *receives* commands, rare friction.
- **branic** (recruit) — **mentored on watch**: frequent commands from Halgrim, help, meals,
  occasional sharp word from Halgrim; mild boredom baseline.
- **lutek** (poet) — **light, warm day**: meals + help, rare slights (in MVP he does not burst);
  mild boredom baseline (bores fastest).
- **welf** (merchant) — **sparse, idle day** (only `player` as a relation): a few meals,
  occasional help (**floored at ≥1/day** so no pure-drift days), rare slight; elevated boredom baseline.

### Distribution design notes (QA forcing — so a reviewer can SEE each persona's defining behavior)

This corpus is **QA forcing input** for judging persona character by review, **not** engine tests — the
files carry **no assertions** (the assertion is the reviewer's judgment over the trajectory). Three
deliberate distribution choices make the defining behaviors observable:

1. **Obedience contrast is present.** Halgrim is commanded by a **respected** source (Edda) AND a
   **resented** one (Wojslaw, ~1/3 of his commands), so both `cooperate` days and `refuse` days appear —
   the second litmus is visible. (Only Halgrim has a respected-vs-resented commander *pair* in the
   relation graph; the others' command sources are role-appropriately single-valued.)
2. **Command and help intensity VARY** (drawn from a clamped Normal, not a constant), so a reviewer sees
   how each persona responds to a **weak vs forceful** command (the axis that interacts with
   `respect[source]` for the obedience personas) and gentle vs strong help. `food_given` is left constant
   (the "same soup" boredom theme exercises only the repetition→boredom axis, by design).
3. **No pure-drift days.** Every persona has ≥2 events/day (Welf's help is floored at ≥1) so there is
   always something to react TO.

### Observed event mix (100 files each)

Realized totals from the current generated set (sampling, so they track the profile means, not equal them):

| Persona  | avg events/day | food_given | help | command | insult |
|----------|:--------------:|:----------:|:----:|:-------:|:------:|
| cichy    | 4.2  | 240 | 44  | —   | 132 |
| wojslaw  | 11.1 | 290 | 370 | 191 | 263 |
| halgrim  | 7.5  | 251 | 159 | 227 | 114 |
| edda     | 7.2  | 309 | 287 | 71  | 56  |
| branic   | 8.9  | 251 | 208 | 301 | 127 |
| lutek    | 6.0  | 246 | 273 | —   | 79  |
| welf     | 4.8  | 255 | 182 | —   | 42  |

(Counts exclude the per-day `nightfall`.) Intensity spread (across personas): `command` 0.07–1.0,
`help` 0.19–1.0, `insult` 0.12–1.0; `food_given` constant 1.0. Halgrim is still commanded by both a
respected source (Edda, ~2/3) and a resented one (Wojsław, ~1/3) so cooperate-days AND refuse-days appear.

---

## Time scale

Run on the **believable per-dimension time constants** (`load_eval_persona_timescale`): `dt ≈ 120`
game-seconds/tick, so a **24 h day ≈ 717 ticks**. Events live in the **waking** window `[0, ~508]`
(≈ 06:00 → 23:00); meals sit at meal-fractions of the waking day, other triggers are spread across
it; a single `nightfall` at the end of the waking day drives the ~7 h night/sleep reset. Event `t`
is an **integer** tick index (one event per tick — the runner keys events by tick), sorted by `t`.
Why ≈120 s and not the raw `dt = 3 s`: the fast emotions are scaled into "tens of minutes" while the
accumulators get their own rise-rates, so a day *feels* like a day (anger ~20 min, boredom→restless
~2 h, hunger ~5 h) — see `calibration/timescale_ground_truth.yaml` + the keeper. **Vocabulary now
includes `nightfall`** (the day-closing night signal) alongside the four content verbs.

---

## Determinism (a project pillar)

Every `(persona, index)` pair derives its own seed:

```
seed = first 8 bytes of sha256("<GLOBAL_SEED>:<persona>:<index>")
```

with `GLOBAL_SEED = 20260605`. All sampling goes through `numpy.random.default_rng(seed)`,
so the stream for one file is independent of generation order and **byte-identical** across
re-runs and machines. Verified — re-running the generator reproduces an identical content hash
over all 700 files:

```
sha256(concat of all 700 sorted .yaml) = a78f0b4aa21a3e3058402b9f7bdf2e1176630896a84f1d1f4ed0d8a7162ed14d
```

---

## Validation

The generator validates **every** file with `engine.yaml_io.load_scenario` (**parse only** —
it never calls `run_scenario`). Current result: **700 / 700 parsed cleanly.**

## Layout

```
eval/scenarios/day/
  README.md
  <persona>/<persona>_day_<NNN>.yaml      # NNN = 001..100; id = "<persona>_day_<NNN>"
```
