# Multi-day scenarios (generated)

**100 per persona × 7 = 700 files**, each a stretch of **3–6 days** at the believable per-dimension
timescale (`believable_day_layout()`: ~717 ticks/day, dt ≈ 120 s). Companion to the single-day corpus
(`../day/`); run via **`load_eval_persona_timescale`** for `n_days × DAY_TICKS` ticks.

Each day is a Sapkowski/Witcher-keep-flavoured **day type** that reshapes the event mix (still only the
engine's verbs + `nightfall` + the new `weather`): `ordinary`, `feast`, `drill`, `bad_blood`,
`short_rations`, `visitors`, `quiet`, `foul_weather` (a sustained rain stressor). Day types are restricted
per persona to lore-appropriate ones (a prisoner gets no feast; a merchant gets visitors/short-rations).
The `day_plan` is stored in each file as metadata (for the judge).

## Purpose — GENERAL model sanity, not persona contrast
This corpus is forcing input for a **general working-sanity** check over many days: does the NPC behave
sensibly at the believable timescale — *not starving in minutes*, not saturating, sleeping each night,
recovering overnight, reacting in a way that fits (not contradicts) the persona? It is **NOT** a test of
persona *differences* (that is proven elsewhere). Two layers consume it:

- **`eval/sanity_multiday.py`** — automated, deterministic sanity metrics (the hard "makes sense" gate).
- a **per-scenario fresh-agent judge** — reads the rendered multi-day run + the persona profile and judges
  (a) does it make sense as days in a life, (b) is it not *wrong* for this personality.

Generator: [`eval/generate_multiday_scenarios.py`](../../generate_multiday_scenarios.py). Deterministic:
`seed = sha256(MULTI_SEED:persona:index)`; re-running reproduces byte-identical files. 700/700 parse
cleanly via `engine.yaml_io.load_scenario`.
