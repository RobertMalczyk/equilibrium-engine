# RPG Persona Dynamics

**A deterministic, debuggable engine for NPC character tension, modeled as a control system.**
Visible behaviour *emerges from the dynamics of internal states* — it is not driven by scripts or by a
language model in the decision loop.

**Website:** **[equilibrium-engine.dev](https://equilibrium-engine.dev/)** — interactive demos, the trace explorer, and the [white paper](https://equilibrium-engine.dev/whitepaper.pdf).

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

## License

[Apache License 2.0](LICENSE) — © 2026 Robert Malczyk.
