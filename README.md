# RPG Persona Dynamics

**A deterministic, debuggable engine for NPC character tension, modeled as a control system.**
Visible behaviour *emerges from the dynamics of internal states* — it is not driven by scripts or by a
language model in the decision loop.

**Website:** **[equilibrium-engine.dev](https://equilibrium-engine.dev/)** — interactive demos, the trace explorer, and the [white paper](https://equilibrium-engine.dev/whitepaper.pdf).
**YouTube:** **[@equilibrium-engine](https://www.youtube.com/@equilibrium-engine)** — teaser & explainer films.
**Wiki:** **[project wiki](https://github.com/RobertMalczyk/equilibrium-engine/wiki)** — architecture, believability testing, and how to contribute.
**Reports:** [believability results](eval/hourly_runs/FINAL_report.md) (2,800 blind-judged scenarios, 97.6% pass) · [full per-test report](eval/hourly_runs/TEST_REPORT.md) · [moral-tension (M-J) report](eval/MORAL_REPORT.md) (opt-in moral overlay, judged 1–5).

> ⚠️ **Work in progress (research-grade).** The MVP thesis is proven and the core is stable and
> tested, but the engine is under **active development** — APIs, the spec, and config layouts can
> change without notice, and several subsystems are mid-calibration. See
> [**Project status & current work**](#project-status--current-work) below for what is settled and
> what is open.

---

## The idea in one paragraph

An NPC's interior is a small set of internal states — anger, fatigue, boredom, resentment toward a
particular person, and so on — where **each state is a generic integrator with decay**: it remembers a
little of its past, drifts toward a resting level, and adds what is pouring in from the world and from
the other states this tick. The states are wired sparsely into stable coupled loops. Visible actions
are **selected from the state**, never from an `if insulted then get angry` rule. The magnitudes are not
hand-picked: the *topology* (what connects to what) is fixed first, and the *constants* (gains,
half-lives, thresholds) come out of an offline calibration harness. You tune the *shape*, and the
behaviour falls out.

The litmus test: the **same** input event produces **different visible actions** from different personas
using configuration alone — one bursts, another suppresses it, a third shrugs — and re-running an
identical scenario yields a **byte-identical** result.

## What this engine is (and is not)

- **Behaviour from dynamics, not scripts.** No event-to-action table anywhere in the tick path.
- **Bit-for-bit deterministic & auditable.** All state equations live in one place; the update reads one
  frozen start-of-tick snapshot; every tick emits a complete trace. Determinism is regression-tested
  against golden traces.
- **Cheap.** A single-persona tick is roughly tens of microseconds on one core, pure Python, no GPU and
  no per-tick network call.
- **The LLM is optional and lives only at the *seams*.** If used at all, a language model sits at
  *perception* (text → events) and *expression* (trace → text) — never in the decision loop, never
  mutating state, with a deterministic fallback when absent.

This is a research-grade MVP, deliberately small ("less is more" — only what does something is built;
the rest is named and deferred).

## Repository layout

| Path | What |
|---|---|
| `engine/` | The engine: types, mapper, filters, update, potentials, action selector, simulation loop. **No numeric literals — everything comes from config.** |
| `data/personas/`, `data/scenarios/` | The cast (traits + relation graph) and hand-authored scenarios. |
| `calibration/` | Calibrated parameter layers (`*.yaml`) + the offline calibration/loss tooling. |
| `tests/` | Property, persona-contrast, order-invariance, stability, and golden-trace tests. |
| `docs/` | The full spec (`docs/rpg_persona_dynamics_spec_v1.md` — **source of truth**), the block diagrams (`docs/diagrams/`), the cast/scenario calibration companions, and the timescale design note. |
| `eval/` | Believability layer: a deterministic multi-day scenario corpus, an automated sanity gate, a blind LLM-judge harness, and the expression seam (deterministic trace → prose). |

> **The spec is the source of truth.** On any conflict between code, diagrams, and
> `docs/rpg_persona_dynamics_spec_v1.md` — the spec wins.

## Quickstart

Requires Python ≥ 3.11. The engine itself depends only on `PyYAML`.

```bash
# install (engine + dev/test extras)
pip install -e ".[dev]"

# run the test suite (property + contrast + golden-trace determinism)
python -m pytest
```

Use it as a library — load a persona and a scenario, run the deterministic tick loop:

```python
from pathlib import Path
from engine.yaml_io import load_persona, load_scenario
from engine.simulation import run_scenario

root = Path(".")
cfg = load_persona(root / "data" / "personas" / "wojslaw.yaml",
                   root / "calibration" / "defaults.yaml")
scenario = load_scenario(root / "data" / "scenarios" / "insult_public.yaml")

result = run_scenario(cfg, scenario)   # pure function: same inputs -> byte-identical trace
for tick in result.trace:
    print(tick)                        # full per-tick debug record
```

### The believability harness

The `eval/` layer validates that runs read believably across whole simulated days (run from the repo
root with `PYTHONPATH=.`):

```bash
# automated multi-day sanity gate over the generated corpus
PYTHONPATH=. python eval/sanity_multiday.py --all
```

The 700-scenario multi-day corpus under `eval/scenarios/` is checked in (deterministic, numpy-seeded) so
the sanity gate runs on a fresh clone; the generators (`eval/generate_*_scenarios.py`) can recreate it.

## Read more

- **The spec** — `docs/rpg_persona_dynamics_spec_v1.md`: the canonical types, member contracts, tick
  order, channels, action catalog, arbitration, and calibration approach.
- **Block diagrams** — `docs/diagrams/`: each subsystem in both control (summing junctions, integrators,
  signed feedback) and functional (the cycle in domain language) form.

## Project status & current work

**Stable / proven.** The MVP thesis holds: same input → different visible actions per persona,
byte-identical re-runs, behaviour from dynamics rather than scripts. The tick path, calibration
harness (Layer 1/2), determinism goldens, and the believability eval (700-day + 700-multiday
corpora, blind-judge) are in place and green.

**Moral-tension (M-J) overlay — merged, calibrated.** An **opt-in** layer adding guilt, secrets, lies,
accusation, suspicion, and betrayal dynamics (with a `MoralLedger` of secrets + lie records). It is
strictly opt-in: with no moral config a persona is **byte-identical** to before, and the base
believability corpus is unchanged across the whole merge. Calibration is closed (deterministic
pre-filter → paced blind judge): the moral corpus scores **4.0–4.83/5** post-calibration, the
serious-guilt (~72h) and suspicion (24h) half-lives are judge-validated. Because moral behaviour is
graded on a fuzzy 1–5 quality scale rather than PASS/FAIL, it has a dedicated
[moral-tension report](eval/MORAL_REPORT.md). Plan + spec: `docs/moral_tension_PLAN.md`,
`docs/moral_tension_impl_spec.md`.

**In progress / known open issues:**

- **Burst / outburst calibration (M20.1).** The burst-saturation subsystem (escalation, latch,
  extinction, displaced aggression) is structurally complete and **ships inert** — every magnitude
  is a neutral placeholder, so it has no effect until calibrated. Calibrating the numbers under a
  boundedness gate is open work (`docs/burst_calibration_plan.md`).
- **Blind-judge residuals.** A handful of corpus scenarios still read slightly off (e.g.
  fury-on-waking, dense-refusal cadence); the full-corpus pass rate is ~99% but not 100%.
- **Affinity-field generalisation.** A generic cosine-blended valence field (places/objects, and
  optionally people-seeding) is being developed behind the input-filter seam.
- **Stage-2 social dynamics.** Authority↔resentment back-edges, chains of command, mood contagion,
  and leveled grievance are designed but not yet built.
- **M-MEM (multi-event per tick) — merged.** A tick can carry several events: each is mapped+filtered and
  merged into the effective input (a channel → list of inputs, summed by `update`), with the per-source
  reactive signals keyed on the strongest provoker. A ≤1-event tick stays byte-identical. This is the
  seam for simultaneous multi-agent fan-out, and the M-J moral overlay (witness fan-out) builds on it —
  see `docs/m_mem_PLAN.md`.

Because of the above, **treat the spec, config schema, and calibrated constants as moving targets.**
Contributions and issue reports are welcome, but expect churn.

## AI-Assisted Development

This repository uses AI-assisted coding tools, including Claude Code, openly and as a normal part of the
implementation workflow. AI may help draft implementation code, tests, refactors, and documentation, but
it is treated as an *untrusted implementation draft* — reviewed, tested, and checked against the spec
before it lands. The conceptual model, architecture decisions, validation, and final responsibility
remain human-owned, and every change is held to the same spec-driven, deterministic, test-validated bar
as the rest of the project. See [AI_USAGE.md](AI_USAGE.md) for the full policy.

## License

[Apache License 2.0](LICENSE) — © 2026 Robert Malczyk. A permissive license: use, modify, and
redistribute freely, including commercially, provided the license and copyright notice are retained.
